"""Database configuration for identity and account-owned application state."""

from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_data_dir


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    configured = os.getenv("MNE_DATABASE_URL")
    if configured:
        return configured
    return f"sqlite:///{get_data_dir() / 'accounts.sqlite3'}"


def build_engine(url: str | None = None):
    selected = url or database_url()
    kwargs = {"future": True, "pool_pre_ping": True}
    if selected.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(selected, **kwargs)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def configure_database(url: str) -> None:
    """Rebind the process database (primarily for isolated tests/commands)."""
    global engine
    engine.dispose()
    engine = build_engine(url)
    SessionLocal.configure(bind=engine)

