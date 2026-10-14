from alembic import context
from sqlalchemy import create_engine, pool
from pathlib import Path
from app.core.config import Settings
from app.models import Base

url = Settings().database_url
if url.startswith("sqlite:///"):
    Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            render_as_batch=url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()
