"""Database layer.

WHAT: SQLAlchemy engine + session + Base for all models.
WHY:  SQLite is enough for the MVP, but the business may grow. If every
      query goes through SQLAlchemy, switching to PostgreSQL later is
      only a DATABASE_URL change - no code rewrite.
HOW:  Engine is built from settings.database_url. SQLite needs
      check_same_thread=False for FastAPI's threaded TestClient/uvicorn.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one DB session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they do not exist (MVP approach).

    NOTE: Production migrations with Alembic are a Phase 8 hardening item.
    create_all is honest for an MVP - it never drops or alters data.
    """
    from app import models  # noqa: F401  (importing registers all models)
    Base.metadata.create_all(bind=engine)
