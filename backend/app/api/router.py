from typing import Annotated, Literal
from uuid import UUID, uuid4
from fastapi import (
    APIRouter,
    Depends,
    Request,
    UploadFile,
    File,
    Form,
    Query,
    Header,
    Response,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from app.models import (
    Recording,
    Reference,
    Rubric,
    Analysis,
    ContrastiveGroup,
    Variant,
    Annotation,
    Transcription,
)
from app.schemas.contracts import (
    Page,
    RecordingOut,
    RecordingPatch,
    ReferenceWrite,
    ReferenceOut,
    RubricWrite,
    RubricOut,
    AnalysisCreate,
    AnalysisOut,
    AnalysisResult,
    GroupWrite,
    GroupOut,
    VariantWrite,
    VariantOut,
    AnnotationWrite,
    AnnotationOut,
    TranscriptionOut,
)
from app.ml.registry import get_provider
from app.repositories.database import get, page
from app.services import (
    recording_service as recordings,
    analysis_service as analyses,
    dataset_service as datasets,
)
from app.services.report_service import flaws_csv, report_pdf
from app.services.reference_service import update_reference
from app.core.exceptions import AppError
from app.models.entities import now

router = APIRouter(prefix="/api/v1")


def session(request: Request):
    with request.app.state.sessions() as value:
        yield value


DB = Annotated[object, Depends(session)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


def write(session, row, data):
    for name, value in data.model_dump(mode="json", exclude_unset=True).items():
        setattr(row, name, value)
    session.add(row)
    session.commit()
    return row


@router.get("/health")
def health(request: Request, db: DB):
    db.execute(select(1))
    try:
        provider = get_provider(request.app.state.settings)
        ready, message = True, provider.health_check().message
    except AppError as exc:
        ready, message = False, exc.message
    return {
        "status": "ok",
        "database": "ok",
        "provider_ready": ready,
        "message": message,
        "version": request.app.state.settings.app_version,
    }


@router.get("/providers")
def providers(request: Request):
    settings = request.app.state.settings
    try:
        caps = get_provider(settings).get_capabilities()
        return {
            "configured_provider": settings.analysis_provider,
            "ready": caps.ready,
            "execution_mode": caps.execution_mode,
            "provider_version": caps.provider_version,
            "message": caps.message,
            "app_version": settings.app_version,
            "max_upload_mb": settings.max_upload_mb,
            "single_user": True,
        }
    except AppError as exc:
        return {
            "configured_provider": settings.analysis_provider,
            "ready": False,
            "execution_mode": None,
            "message": exc.message,
            "app_version": settings.app_version,
            "max_upload_mb": settings.max_upload_mb,
            "single_user": True,
        }


@router.get("/providers/capabilities")
def capabilities(request: Request):
    return get_provider(request.app.state.settings).get_capabilities()


@router.post("/recordings", response_model=RecordingOut, status_code=201)
def upload_recording(
    request: Request,
    db: DB,
    file: UploadFile = File(...),
    category: Literal["participant", "reference", "variant"] = Form("participant"),
):
    return recordings.upload(
        db,
        request.app.state.storage,
        file,
        request.app.state.settings.max_upload_mb,
        category,
    )


@router.get("/recordings", response_model=Page[RecordingOut])
def list_recordings(
    db: DB,
    offset: Offset = 0,
    limit: Limit = 20,
    search: str = "",
    category: str | None = None,
):
    filters = [
        Recording.original_filename.ilike("%" + search + "%")
        | Recording.title.ilike("%" + search + "%")
    ]
    if category:
        filters.append(Recording.category == category)
    return page(db, Recording, offset, limit, filters)


@router.get("/recordings/{recording_id}", response_model=RecordingOut)
def recording(recording_id: UUID, db: DB):
    return get(db, Recording, recording_id)


@router.get("/recordings/{recording_id}/audio")
def audio(recording_id: UUID, request: Request, db: DB):
    row = get(db, Recording, recording_id)
    path = request.app.state.storage.path(row.storage_key)
    if not path.is_file():
        raise AppError("FILE_NOT_FOUND", "The managed audio file is unavailable.", 404)
    return FileResponse(
        path,
        media_type=row.mime_type,
        filename=row.original_filename,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post(
    "/recordings/{recording_id}/transcriptions",
    response_model=TranscriptionOut,
    status_code=202,
)
def transcribe_recording(recording_id: UUID, request: Request, db: DB):
    recording = get(db, Recording, recording_id)
    if (
        recording.duration_seconds is not None
        and not 0.5 <= recording.duration_seconds <= 180
    ):
        raise AppError(
            "AUDIO_DURATION",
            "Choose a speech excerpt between half a second and three minutes.",
        )
    settings = request.app.state.settings
    if settings.analysis_provider not in ["evaluator", "custom"]:
        raise AppError(
            "UNSUPPORTED_INPUT",
            "Local transcription requires the real speech evaluator.",
        )
    get_provider(settings)
    existing = db.scalar(
        select(Transcription).where(
            Transcription.recording_id == str(recording_id),
            Transcription.status.in_(["queued", "processing"]),
        )
    )
    if existing:
        return existing
    row = Transcription(
        recording_id=str(recording_id),
        model_name=settings.transcription_model,
        language=settings.evaluator_language,
    )
    db.add(row)
    db.commit()
    request.app.state.transcriptions.submit(row.id)
    return row


@router.get("/transcriptions/{transcription_id}", response_model=TranscriptionOut)
def transcription(transcription_id: UUID, db: DB):
    return get(db, Transcription, transcription_id)


@router.post(
    "/transcriptions/{transcription_id}/cancel", response_model=TranscriptionOut
)
def cancel_transcription(transcription_id: UUID, request: Request, db: DB):
    request.app.state.transcriptions.cancel(str(transcription_id))
    return get(db, Transcription, transcription_id)


@router.patch("/recordings/{recording_id}", response_model=RecordingOut)
def patch_recording(recording_id: UUID, data: RecordingPatch, db: DB):
    return write(db, get(db, Recording, recording_id), data)


@router.delete("/recordings/{recording_id}", status_code=204)
def delete_recording(recording_id: UUID, request: Request, db: DB):
    recordings.delete_recording(db, request.app.state.storage, recording_id)


@router.post("/references", response_model=ReferenceOut, status_code=201)
def create_reference(data: ReferenceWrite, db: DB):
    get(db, Recording, data.recording_id)
    return write(db, Reference(), data)


@router.get("/references", response_model=Page[ReferenceOut])
def list_references(
    db: DB,
    offset: Offset = 0,
    limit: Limit = 20,
    search: str = "",
    eligible: bool | None = None,
):
    filters = [Reference.title.ilike("%" + search + "%")]
    if eligible is not None:
        filters.append(Reference.eligible == eligible)
    return page(db, Reference, offset, limit, filters)


@router.get("/references/{reference_id}", response_model=ReferenceOut)
def reference(reference_id: UUID, db: DB):
    return get(db, Reference, reference_id)


@router.patch("/references/{reference_id}", response_model=ReferenceOut)
def patch_reference(reference_id: UUID, data: ReferenceWrite, db: DB):
    return update_reference(db, reference_id, data)


@router.delete("/references/{reference_id}", status_code=204)
def delete_reference(reference_id: UUID, db: DB):
    db.delete(get(db, Reference, reference_id))
    db.commit()


@router.get("/rubrics", response_model=Page[RubricOut])
def list_rubrics(db: DB, offset: Offset = 0, limit: Limit = 20):
    return page(db, Rubric, offset, limit)


@router.post("/rubrics", response_model=RubricOut, status_code=201)
def create_rubric(data: RubricWrite, db: DB):
    return write(db, Rubric(), data)


@router.get("/rubrics/{rubric_id}", response_model=RubricOut)
def rubric(rubric_id: UUID, db: DB):
    return get(db, Rubric, rubric_id)


@router.patch("/rubrics/{rubric_id}", response_model=RubricOut)
def patch_rubric(rubric_id: UUID, data: RubricWrite, db: DB):
    row = get(db, Rubric, rubric_id)
    row.version += 1
    return write(db, row, data)


@router.delete("/rubrics/{rubric_id}", status_code=204)
def delete_rubric(rubric_id: UUID, db: DB):
    db.delete(get(db, Rubric, rubric_id))
    db.commit()


@router.post("/analyses", response_model=AnalysisOut, status_code=202)
def create_analysis(
    data: AnalysisCreate,
    request: Request,
    db: DB,
    idempotency_key: Annotated[str | None, Header(max_length=100)] = None,
):
    provider = get_provider(request.app.state.settings)
    row, created = analyses.create_analysis(
        db, data, provider, idempotency_key or str(uuid4())
    )
    if created:
        request.app.state.runner.submit(row.id)
    return analyses.analysis_out(db, row)


@router.get("/analyses", response_model=Page[AnalysisOut])
def list_analyses(
    db: DB,
    offset: Offset = 0,
    limit: Limit = 20,
    search: str = "",
    status: str | None = None,
):
    filters = [
        Analysis.participant_recording_id.in_(
            select(Recording.id).where(
                Recording.original_filename.ilike("%" + search + "%")
            )
        )
        | Analysis.id.ilike("%" + search + "%")
    ]
    if status:
        filters.append(Analysis.status == status)
    result = page(db, Analysis, offset, limit, filters)
    result["items"] = [analyses.analysis_out(db, row) for row in result["items"]]
    return result


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def analysis(analysis_id: UUID, db: DB):
    return analyses.analysis_out(db, get(db, Analysis, analysis_id))


@router.get("/analyses/{analysis_id}/result", response_model=AnalysisResult)
def result(analysis_id: UUID, request: Request, db: DB):
    return analyses.result_for(db, request.app.state.storage, analysis_id)


@router.post("/analyses/{analysis_id}/cancel", response_model=AnalysisOut)
def cancel(analysis_id: UUID, request: Request, db: DB):
    if (
        not get_provider(request.app.state.settings)
        .get_capabilities()
        .supports_cancellation
    ):
        raise AppError(
            "CANCELLATION_UNSUPPORTED",
            "This provider does not support cancellation.",
            409,
        )
    request.app.state.runner.cancel(str(analysis_id))
    return analyses.analysis_out(db, get(db, Analysis, analysis_id))


@router.post(
    "/analyses/{analysis_id}/retry", response_model=AnalysisOut, status_code=202
)
def retry(analysis_id: UUID, request: Request, db: DB):
    request.app.state.runner.retry(str(analysis_id))
    return analyses.analysis_out(db, get(db, Analysis, analysis_id))


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: UUID, request: Request, db: DB):
    analyses.delete_analysis(db, request.app.state.storage, analysis_id)


@router.get("/analyses/{analysis_id}/export/json")
def export_json(analysis_id: UUID, request: Request, db: DB):
    result = analyses.result_for(db, request.app.state.storage, analysis_id)
    return Response(
        result.model_dump_json(indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="vocalis-{analysis_id}.json"'
        },
    )


@router.get("/analyses/{analysis_id}/export/csv")
def export_csv(analysis_id: UUID, request: Request, db: DB):
    return Response(
        flaws_csv(analyses.result_for(db, request.app.state.storage, analysis_id)),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="vocalis-{analysis_id}-flaws.csv"'
        },
    )


@router.get("/analyses/{analysis_id}/export/pdf")
def export_pdf(analysis_id: UUID, request: Request, db: DB):
    result = analyses.result_for(db, request.app.state.storage, analysis_id)
    job = analyses.analysis_out(db, get(db, Analysis, analysis_id))
    return Response(
        report_pdf(result, job),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="vocalis-{analysis_id}.pdf"'
        },
    )


@router.post("/datasets/groups", response_model=GroupOut, status_code=201)
def create_group(data: GroupWrite, db: DB):
    datasets.validate_group(db, data)
    return datasets.group_out(db, write(db, ContrastiveGroup(), data))


@router.get("/datasets/groups", response_model=Page[GroupOut])
def list_groups(
    db: DB,
    offset: Offset = 0,
    limit: Limit = 20,
    search: str = "",
    split: str | None = None,
):
    filters = [ContrastiveGroup.title.ilike("%" + search + "%")]
    if split:
        filters.append(ContrastiveGroup.split == split)
    result = page(db, ContrastiveGroup, offset, limit, filters)
    result["items"] = [datasets.group_out(db, row) for row in result["items"]]
    return result


@router.get("/datasets/groups/{group_id}", response_model=GroupOut)
def group(group_id: UUID, db: DB):
    return datasets.group_out(db, get(db, ContrastiveGroup, group_id))


@router.patch("/datasets/groups/{group_id}", response_model=GroupOut)
def patch_group(group_id: UUID, data: GroupWrite, db: DB):
    datasets.validate_group(db, data, str(group_id))
    row = get(db, ContrastiveGroup, group_id)
    if row.split != data.split:
        variant_ids = list(
            db.scalars(select(Variant.recording_id).where(Variant.group_id == row.id))
        )
        others = db.scalars(
            select(ContrastiveGroup)
            .join(Variant)
            .where(Variant.recording_id.in_(variant_ids), ContrastiveGroup.id != row.id)
        ).all()
        if any(g.split != data.split for g in others):
            raise AppError(
                "SPLIT_CONFLICT",
                "Linked variants already belong to another split.",
                409,
            )
    return datasets.group_out(db, write(db, row, data))


@router.delete("/datasets/groups/{group_id}", status_code=204)
def delete_group(group_id: UUID, db: DB):
    db.delete(get(db, ContrastiveGroup, group_id))
    db.commit()


@router.post(
    "/datasets/groups/{group_id}/variants", response_model=VariantOut, status_code=201
)
def add_variant(group_id: UUID, data: VariantWrite, db: DB):
    return datasets.add_variant(db, group_id, data)


@router.delete("/datasets/groups/{group_id}/variants/{variant_id}", status_code=204)
def delete_variant(group_id: UUID, variant_id: UUID, db: DB):
    row = get(db, Variant, variant_id)
    if row.group_id != str(group_id):
        raise AppError("NOT_FOUND", "Variant does not belong to this group.", 404)
    db.delete(row)
    db.commit()


@router.get("/datasets/annotations", response_model=Page[AnnotationOut])
def annotations(
    db: DB, offset: Offset = 0, limit: Limit = 20, recording_id: UUID | None = None
):
    return page(
        db,
        Annotation,
        offset,
        limit,
        [Annotation.recording_id == str(recording_id)] if recording_id else [],
    )


@router.post("/datasets/annotations", response_model=AnnotationOut, status_code=201)
def add_annotation(data: AnnotationWrite, db: DB):
    datasets.validate_annotation(db, data)
    return write(db, Annotation(), data)


@router.patch("/datasets/annotations/{annotation_id}", response_model=AnnotationOut)
def patch_annotation(annotation_id: UUID, data: AnnotationWrite, db: DB):
    datasets.validate_annotation(db, data)
    return write(db, get(db, Annotation, annotation_id), data)


@router.delete("/datasets/annotations/{annotation_id}", status_code=204)
def delete_annotation(annotation_id: UUID, db: DB):
    db.delete(get(db, Annotation, annotation_id))
    db.commit()


@router.get("/dashboard")
def dashboard(db: DB):
    from sqlalchemy import func
    from app.models import DetectedFlaw

    total = db.scalar(select(func.count()).select_from(Analysis))
    completed = db.scalar(
        select(func.count()).select_from(Analysis).where(Analysis.status == "completed")
    )
    real = db.scalar(
        select(func.count())
        .select_from(Analysis)
        .where(Analysis.status == "completed", Analysis.execution_mode == "real")
    )
    average = db.scalar(
        select(func.avg(Analysis.overall_score)).where(
            Analysis.status == "completed", Analysis.execution_mode == "real"
        )
    )
    flaws = db.execute(
        select(DetectedFlaw.type, func.count())
        .join(Analysis)
        .where(Analysis.execution_mode == "real", Analysis.status == "completed")
        .group_by(DetectedFlaw.type)
    ).all()
    return {
        "total": total,
        "completed": completed,
        "real_completed": real,
        "average_score": average,
        "frequent_flaws": [{"type": name, "count": count} for name, count in flaws],
        "references": db.scalar(select(func.count()).select_from(Reference)),
        "groups": db.scalar(select(func.count()).select_from(ContrastiveGroup)),
        "recent": [
            analyses.analysis_out(db, a)
            for a in db.scalars(
                select(Analysis).order_by(Analysis.created_at.desc()).limit(5)
            )
        ],
    }
