import logging
import threading
import time
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select
from app.models import Analysis, Recording, Reference
from app.models.entities import now
from app.schemas.contracts import AnalysisSettings, RubricOut, AnalysisResult
from app.ml.schemas import ProviderRequest
from app.ml.registry import get_provider
from app.services.analysis_service import persist_result
from app.repositories.database import get
from app.core.exceptions import AppError
from .runner import JobRunner

log = logging.getLogger("vocalis.jobs")


class JobStopped(Exception):
    pass


class LocalRunner(JobRunner):
    """Single-process prototype. Cancellation/timeout discard late output; providers cooperate via callbacks."""

    def __init__(self, sessions, storage, settings):
        self.sessions, self.storage, self.settings = sessions, storage, settings
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vocalis")
        self.lock = threading.RLock()
        self.attempts = {}
        self.stop = threading.Event()
        with sessions() as session:
            for job in session.scalars(
                select(Analysis).where(Analysis.status.in_(["queued", "processing"]))
            ):
                job.status, job.error_code, job.error_summary = (
                    "failed",
                    "RUNNER_RESTARTED",
                    "The local worker restarted. Retry this analysis.",
                )
                job.completed_at = now()
            session.commit()
        self.monitor = threading.Thread(target=self.watchdog, daemon=True)
        self.monitor.start()

    def submit(self, job_id):
        with self.lock:
            token = uuid4().hex
            self.attempts[job_id] = (token, time.monotonic())
            self.pool.submit(self.run, job_id, token)

    def check(self, job_id, token):
        entry = self.attempts.get(job_id)
        if self.stop.is_set() or not entry or entry[0] != token:
            raise JobStopped()

    def progress(self, job_id, token, stage, percent):
        with self.lock, self.sessions() as session:
            self.check(job_id, token)
            job = get(session, Analysis, job_id)
            if job.status not in ["queued", "processing"]:
                raise JobStopped()
            if not isinstance(percent, (int, float)) or not 0 <= percent <= 100:
                raise ValueError("Invalid progress")
            job.status, job.progress_stage, job.progress_percent = (
                "processing",
                str(stage)[:255],
                percent,
            )
            job.started_at = job.started_at or now()
            session.commit()

    def run(self, job_id, token):
        try:
            self.progress(job_id, token, "Input validation", 1)
            provider = get_provider(self.settings)
            with self.sessions() as session:
                job = get(session, Analysis, job_id)
                participant = get(session, Recording, job.participant_recording_id)
                reference = (
                    get(session, Reference, job.reference_id)
                    if job.reference_id
                    else None
                )
                reference_recording = (
                    get(session, Recording, reference.recording_id)
                    if reference
                    else None
                )
                request = ProviderRequest(
                    job_id=job_id,
                    participant_path=self.storage.path(participant.storage_key),
                    participant_duration_seconds=participant.duration_seconds,
                    reference_path=(
                        self.storage.path(reference_recording.storage_key)
                        if reference_recording
                        else None
                    ),
                    reference_duration_seconds=(
                        reference_recording.duration_seconds
                        if reference_recording
                        else None
                    ),
                    reference_profile=reference.profile if reference else None,
                    transcript=job.transcript,
                    reference_transcript=reference.transcript if reference else "",
                    rubric=RubricOut.model_validate(job.rubric_snapshot),
                    settings=AnalysisSettings.model_validate(job.settings),
                )
            result = AnalysisResult.model_validate(
                provider.analyze(
                    request,
                    lambda stage, percent: self.progress(job_id, token, stage, percent),
                )
            )
            with self.lock, self.sessions() as session:
                self.check(job_id, token)
                job = get(session, Analysis, job_id)
                if job.status != "processing":
                    raise JobStopped()
                persist_result(session, self.storage, job, result)
        except JobStopped:
            pass
        except Exception as exc:
            # Never put user data, filesystem paths or arbitrary provider error text in logs or HTTP responses.
            log.error("Job %s failed (%s)", job_id, type(exc).__name__)
            with self.lock, self.sessions() as session:
                entry = self.attempts.get(job_id)
                job = session.get(Analysis, job_id)
                if (
                    entry
                    and entry[0] == token
                    and job
                    and job.status in ["queued", "processing"]
                ):
                    job.status, job.error_code, job.error_summary = (
                        "failed",
                        exc.code if isinstance(exc, AppError) else "PROVIDER_FAILURE",
                        (
                            exc.message
                            if isinstance(exc, AppError)
                            else "The analysis provider failed or returned invalid data. Retry after checking the provider."
                        ),
                    )
                    job.completed_at = now()
                    session.commit()
        finally:
            with self.lock:
                entry = self.attempts.get(job_id)
                if entry and entry[0] == token:
                    self.attempts.pop(job_id, None)

    def watchdog(self):
        while not self.stop.wait(0.25):
            with self.lock, self.sessions() as session:
                for job_id, (_, submitted) in list(self.attempts.items()):
                    if time.monotonic() - submitted > self.settings.job_timeout_seconds:
                        job = session.get(Analysis, job_id)
                        if job and job.status in ["queued", "processing"]:
                            job.status, job.error_code, job.error_summary = (
                                "failed",
                                "JOB_TIMEOUT",
                                "The analysis exceeded the time limit. Retry or configure a worker with a longer limit.",
                            )
                            job.completed_at = now()
                        self.attempts.pop(job_id, None)
                session.commit()

    def cancel(self, job_id):
        with self.lock, self.sessions() as session:
            job = get(session, Analysis, job_id)
            if job.status not in ["queued", "processing"]:
                raise AppError(
                    "JOB_NOT_ACTIVE",
                    "Only queued or processing jobs can be cancelled.",
                    409,
                )
            job.status, job.progress_stage, job.completed_at = (
                "cancelled",
                "Cancelled",
                now(),
            )
            session.commit()
            self.attempts.pop(job_id, None)

    def retry(self, job_id):
        with self.lock, self.sessions() as session:
            job = get(session, Analysis, job_id)
            if job.status != "failed":
                raise AppError(
                    "JOB_NOT_FAILED", "Only failed jobs can be retried.", 409
                )
            caps = get_provider(self.settings).get_capabilities()
            if (
                caps.provider_name != job.provider_name
                or caps.provider_version != job.provider_version
                or caps.execution_mode != job.execution_mode
            ):
                raise AppError(
                    "PROVIDER_CHANGED",
                    "Provider changed. Submit a new analysis instead.",
                    409,
                )
            job.status, job.progress_stage, job.progress_percent = "queued", "Queued", 0
            job.error_code = job.error_summary = job.completed_at = job.started_at = (
                None
            )
            session.commit()
            self.submit(job.id)

    def shutdown(self):
        self.stop.set()
        with self.lock, self.sessions() as session:
            for job_id in self.attempts:
                job = session.get(Analysis, job_id)
                if job and job.status in ["queued", "processing"]:
                    job.status, job.error_code, job.error_summary = (
                        "failed",
                        "RUNNER_STOPPED",
                        "The local worker stopped. Retry this analysis.",
                    )
                    job.completed_at = now()
            session.commit()
            self.attempts.clear()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.monitor.join(timeout=1)
