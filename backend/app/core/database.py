from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


class Base(DeclarativeBase):
    pass


options = (
    {}
    if settings.database_url.startswith("sqlite")
    else dict(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
    )
)
if settings.database_url.startswith("postgresql"):
    options["connect_args"] = {
        "options": "-c statement_timeout=15000 -c lock_timeout=10000"
    }
engine = create_engine(
    settings.database_url, pool_pre_ping=True, hide_parameters=True, **options
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.rollback()
