import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from app.core.config import Settings
from app.core.exceptions import AppError
from app.repositories.database import database
from app.storage.local_storage import LocalStorage
from app.workers.local_runner import LocalRunner
from app.workers.transcription_runner import TranscriptionRunner
from app.api.router import router


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    engine, sessions = database(settings.database_url)
    storage = LocalStorage(settings.storage_root)

    @asynccontextmanager
    async def lifespan(app):
        if not inspect(engine).has_table("analyses"):
            raise RuntimeError(
                "Database is not initialized. Run: python -m alembic upgrade head"
            )
        app.state.runner = LocalRunner(sessions, storage, settings)
        app.state.transcriptions = TranscriptionRunner(sessions, storage, settings)
        yield
        app.state.transcriptions.shutdown()
        app.state.runner.shutdown()
        engine.dispose()

    app = FastAPI(title="Vocalis API", version=settings.app_version, lifespan=lifespan)
    app.state.settings, app.state.sessions, app.state.storage, app.state.engine = (
        settings,
        sessions,
        storage,
        engine,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )

    @app.exception_handler(AppError)
    async def app_error(request, error):
        return JSONResponse(
            status_code=error.status,
            content={"error": {"code": error.code, "message": error.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation(request, error):
        details = [
            {"field": ".".join(map(str, e["loc"])), "message": e["msg"]}
            for e in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Check the supplied fields.",
                    "details": details,
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity(request, error):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "RECORD_CONFLICT",
                    "message": "This record is linked or already exists. Remove its dependencies first.",
                }
            },
        )

    @app.exception_handler(Exception)
    async def unexpected(request, error):
        logging.getLogger("vocalis.api").error(
            "Request failed (%s)", type(error).__name__
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected server error occurred.",
                }
            },
        )

    app.include_router(router)
    return app


app = create_app()
