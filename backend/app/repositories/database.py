from pathlib import Path
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.orm import sessionmaker
from app.core.exceptions import AppError


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
    count = session.scalar(select(func.count()).select_from(model).where(*filters))
    items = session.scalars(
        select(model)
        .where(*filters)
        .order_by(model.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {"items": items, "total": count, "offset": offset, "limit": limit}
