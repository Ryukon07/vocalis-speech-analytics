from pathlib import Path
from contextvars import ContextVar
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.orm import sessionmaker
from app.core.exceptions import AppError

# Unset for the local application. The temporary demo scopes lists before
# counting/pagination so another session cannot displace visible page entries.
visible_record_ids: ContextVar[frozenset[str] | None] = ContextVar(
    "visible_record_ids", default=None
)


def database(url: str):
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        connect_args=(
            {"check_same_thread": False, "timeout": 30}
            if url.startswith("sqlite")
            else {}
        ),
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def pragmas(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine, sessionmaker(engine, expire_on_commit=False)


def get(session, model, identifier):
    value = session.get(model, str(identifier))
    if value is None:
        raise AppError("NOT_FOUND", "The requested record does not exist.", 404)
    return value


def page(session, model, offset=0, limit=20, filters=()):
    visible = visible_record_ids.get()
    if visible is not None:
        filters = (*filters, model.id.in_(visible))
    count = session.scalar(select(func.count()).select_from(model).where(*filters))
    items = session.scalars(
        select(model)
        .where(*filters)
        .order_by(model.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {"items": items, "total": count, "offset": offset, "limit": limit}
