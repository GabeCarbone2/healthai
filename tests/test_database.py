import sqlite3
from datetime import date, time

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import InvalidRequestError, SQLAlchemyError

from backend import database
from backend.app import local_date_to_utc
from backend.database import (
    ReadOnlySession,
    _configure_sqlite_connection,
    _create_database_engine,
    _read_database_urls,
)
from backend.models import User


def test_sqlite_enables_integrity_and_write_resilience(tmp_path) -> None:
    connection = sqlite3.connect(tmp_path / "configured.db")
    _configure_sqlite_connection(connection, None)

    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    connection.close()


def test_local_dates_are_converted_to_utc(monkeypatch) -> None:
    monkeypatch.setenv("HEALTHAI_TIMEZONE", "America/Sao_Paulo")

    boundary = local_date_to_utc(date(2026, 7, 11), time.min)

    assert boundary.isoformat() == "2026-07-11T03:00:00+00:00"


def test_database_pool_uses_configured_limits(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HEALTHAI_DB_POOL_SIZE", "7")
    monkeypatch.setenv("HEALTHAI_DB_MAX_OVERFLOW", "3")
    monkeypatch.setenv("HEALTHAI_DB_POOL_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("HEALTHAI_DB_POOL_RECYCLE_SECONDS", "600")

    database_engine = _create_database_engine(
        f"sqlite:///{tmp_path / 'pooled.db'}"
    )

    assert database_engine.pool.size() == 7
    assert database_engine.pool._max_overflow == 3
    assert database_engine.pool.timeout() == 12
    assert database_engine.pool._recycle == 600
    database_engine.dispose()


def test_in_memory_sqlite_uses_one_shared_connection() -> None:
    database_engine = _create_database_engine("sqlite://")

    assert database_engine.pool.__class__.__name__ == "StaticPool"
    database_engine.dispose()


def test_read_replica_configuration_requires_compatible_database() -> None:
    primary = "postgresql+psycopg://app:secret@primary/healthai"
    replicas = _read_database_urls(
        primary,
        "postgresql+psycopg://app:secret@replica-a/healthai,"
        "postgresql+psycopg://app:secret@replica-b/healthai",
    )

    assert replicas == (
        "postgresql+psycopg://app:secret@replica-a/healthai",
        "postgresql+psycopg://app:secret@replica-b/healthai",
    )
    with pytest.raises(RuntimeError, match="SQLite"):
        _read_database_urls("sqlite:///primary.db", "sqlite:///replica.db")
    with pytest.raises(RuntimeError, match="mesmo SGBD"):
        _read_database_urls(primary, "mysql+pymysql://app:secret@replica/healthai")


def test_read_only_session_rejects_writes() -> None:
    session = ReadOnlySession()

    with pytest.raises(InvalidRequestError, match="apenas leituras"):
        session.execute(delete(User))
    with pytest.raises(InvalidRequestError, match="apenas leituras"):
        session.execute(text("DELETE FROM users"))
    with pytest.raises(InvalidRequestError, match="não permite commit"):
        session.commit()

    session.close()


def test_read_replicas_are_selected_in_round_robin(monkeypatch) -> None:
    replica_a = object()
    replica_b = object()
    monkeypatch.setattr(database, "ReadSessionLocals", (replica_a, replica_b))
    monkeypatch.setattr(database, "_read_replica_cursor", 0)

    assert database._next_read_session_factory() == (replica_a, 0)
    assert database._next_read_session_factory() == (replica_b, 1)
    assert database._next_read_session_factory() == (replica_a, 0)


def test_unavailable_read_replica_falls_back_to_primary(monkeypatch) -> None:
    class FakeSession:
        def __init__(self, *, available: bool) -> None:
            self.available = available
            self.closed = False

        def connection(self) -> None:
            if not self.available:
                raise SQLAlchemyError("replica indisponível")

        def close(self) -> None:
            self.closed = True

    replica_session = FakeSession(available=False)
    primary_session = FakeSession(available=True)
    monkeypatch.setattr(
        database,
        "_next_read_session_factory",
        lambda: (lambda: replica_session, 0),
    )
    monkeypatch.setattr(
        database,
        "PrimaryReadSessionLocal",
        lambda: primary_session,
    )
    monkeypatch.setattr(database, "READ_REPLICA_FALLBACK", True)

    dependency = database.get_read_db()
    assert next(dependency) is primary_session
    dependency.close()

    assert replica_session.closed is True
    assert primary_session.closed is True
