"""Persisted, CPU-friendly transcription; late cancelled/timed-out output is discarded."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select
from app.models import Recording, Transcription
from app.repositories.database import get
from app.core.exceptions import AppError
from app.ml.custom_provider import _load_engine, _EVALUATION_LOCK


class TranscriptionRunner:
    def __init__(self, sessions, storage, settings):
        self.sessions, self.storage, self.settings = sessions, storage, settings
        self.pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="transcription"
        )
        self.lock = threading.RLock()
        self.active = {}
        self.stop = threading.Event()
        with sessions() as db:
            for job in db.scalars(
                select(Transcription).where(
                    Transcription.status.in_(["queued", "processing"])
                )
            ):
                job.status = "failed"
                job.error_summary = "Transcription was interrupted by a restart. Start a new transcription."
            db.commit()
        self.monitor = threading.Thread(target=self.watchdog, daemon=True)
        self.monitor.start()

    def submit(self, identifier):
        with self.lock:
            self.active[identifier] = time.monotonic()
            self.pool.submit(self.run, identifier)

    def run(self, identifier):
        try:
            # Share the inference lock with evaluation to bound laptop memory use.
            with _EVALUATION_LOCK:
                with self.lock, self.sessions() as db:
                    job = db.get(Transcription, identifier)
                    if (
                        self.stop.is_set()
                        or identifier not in self.active
                        or not job
                        or job.status != "queued"
                    ):
                        return
                    recording = get(db, Recording, job.recording_id)
                    path = str(self.storage.path(recording.storage_key))
                    job.status = "processing"
                    language, model = job.language, job.model_name
                    db.commit()
                engine = _load_engine()
                parameters = dict(
                    device=self.settings.evaluator_device,
                    language=language,
                    cache_dir=str(self.settings.model_cache_root.resolve()),
                    cpu_threads=self.settings.cpu_threads,
                )
                try:
                    text = engine.transcribe_audio(path, model_name=model, **parameters)
                except Exception as exc:
                    if getattr(exc, "code", None) != "UNRELIABLE_TRANSCRIPT":
                        raise
                    fallback = self.settings.transcription_fallback_model
                    if not fallback or fallback == model:
                        raise
                    text = ""
                if not text.strip():
                    fallback = self.settings.transcription_fallback_model
                    if fallback and fallback != model:
                        # Do not start a second expensive pass after cancellation
                        # or timeout. The final persistence check also rejects
                        # output arriving after either event.
                        with self.lock, self.sessions() as db:
                            current = db.get(Transcription, identifier)
                            if (identifier not in self.active or not current
                                    or current.status != "processing"):
                                return
                        text = engine.transcribe_audio(path, model_name=fallback, **parameters)
                        model = fallback
                if not text.strip():
                    raise AppError(
                        "EMPTY_TRANSCRIPT",
                        "No speech was recognized. Check the recording and try again.",
                    )
                with self.lock, self.sessions() as db:
                    job = db.get(Transcription, identifier)
                    if job and identifier in self.active and job.status == "processing":
                        job.transcript, job.status = text.strip(), "completed"
                        job.model_name = model
                        db.commit()
        except Exception as exc:
            with self.lock, self.sessions() as db:
                job = db.get(Transcription, identifier)
                if (
                    job
                    and identifier in self.active
                    and job.status in ["queued", "processing"]
                ):
                    job.status = "failed"
                    job.error_summary = (
                        exc.message
                        if isinstance(exc, AppError)
                        else (
                            "Speech recognition produced unreliable repeated text. Record a shorter clip in a quiet setting and check the microphone, or enter a reviewed transcript manually."
                            if getattr(exc, "code", None) == "UNRELIABLE_TRANSCRIPT"
                            else "Transcription failed. Check local model availability and audio quality, then try again."
                        )
                    )[:255]
                    db.commit()
        finally:
            with self.lock:
                self.active.pop(identifier, None)

    def cancel(self, identifier):
        with self.lock, self.sessions() as db:
            job = get(db, Transcription, identifier)
            if job.status not in ["queued", "processing"]:
                raise AppError(
                    "JOB_NOT_ACTIVE",
                    "Only an active transcription can be cancelled.",
                    409,
                )
            job.status = "cancelled"
            db.commit()
            self.active.pop(identifier, None)

    def watchdog(self):
        while not self.stop.wait(0.5):
            with self.lock, self.sessions() as db:
                for identifier, started in list(self.active.items()):
                    if time.monotonic() - started > self.settings.job_timeout_seconds:
                        job = db.get(Transcription, identifier)
                        if job and job.status in ["queued", "processing"]:
                            job.status = "failed"
                            job.error_summary = "Transcription exceeded the local processing limit. Try a shorter recording."
                        self.active.pop(identifier, None)
                db.commit()

    def shutdown(self):
        self.stop.set()
        with self.lock, self.sessions() as db:
            for identifier in self.active:
                job = db.get(Transcription, identifier)
                if job and job.status in ["queued", "processing"]:
                    job.status = "failed"
                    job.error_summary = (
                        "Local processing stopped. Start a new transcription."
                    )
            db.commit()
            self.active.clear()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.monitor.join(timeout=1)
