"""Conexões, pools e roteamento de leitura do banco de dados."""

import logging
from collections.abc import Generator
from pathlib import Path
from threading import Lock
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.elements import TextClause

from backend.settings import setting

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'data' / 'healthai.db'}"
DATABASE_URL = setting("HEALTHAI_DATABASE_URL", DEFAULT_DATABASE_URL)
logger = logging.getLogger("healthai.database")


def _integer_setting(name: str, default: int, minimum: int) -> int:
    raw_value = setting(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} deve ser um número inteiro.") from error
    if value < minimum:
        raise RuntimeError(f"{name} deve ser maior ou igual a {minimum}.")
    return value


def _boolean_setting(name: str, default: bool) -> bool:
    raw_value = setting(name, "true" if default else "false").strip().lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} deve ser true ou false.")


def _database_backend(database_url: str) -> str:
    try:
        return make_url(database_url).get_backend_name()
    except Exception as error:
        raise RuntimeError("URL de banco de dados inválida.") from error


def _read_database_urls(primary_url: str, raw_urls: str) -> tuple[str, ...]:
    """Valida e normaliza as URLs das réplicas configuradas."""
    urls = tuple(
        dict.fromkeys(url.strip() for url in raw_urls.split(",") if url.strip())
    )
    if not urls:
        return ()

    primary_backend = _database_backend(primary_url)
    if primary_backend == "sqlite":
        raise RuntimeError(
            "Read replicas exigem um banco com replicação, como PostgreSQL; "
            "SQLite não oferece esse recurso."
        )
    for replica_url in urls:
        if replica_url == primary_url:
            raise RuntimeError(
                "Uma read replica não pode usar a mesma URL do banco primário."
            )
        if _database_backend(replica_url) != primary_backend:
            raise RuntimeError(
                "O banco primário e as read replicas devem usar o mesmo SGBD."
            )
    return urls


def _engine_options(database_url: str) -> dict[str, Any]:
    """Monta um pool limitado e reutilizável para cada processo da API."""
    parsed_url = make_url(database_url)
    is_sqlite = parsed_url.get_backend_name() == "sqlite"
    is_memory_sqlite = is_sqlite and parsed_url.database in {None, "", ":memory:"}
    options: dict[str, Any] = {"pool_pre_ping": True}
    if is_memory_sqlite:
        options["poolclass"] = StaticPool
    else:
        options.update(
            {
                "pool_recycle": _integer_setting(
                    "HEALTHAI_DB_POOL_RECYCLE_SECONDS", 1800, 1
                ),
                "pool_size": _integer_setting("HEALTHAI_DB_POOL_SIZE", 5, 1),
                "max_overflow": _integer_setting(
                    "HEALTHAI_DB_MAX_OVERFLOW", 10, 0
                ),
                "pool_timeout": _integer_setting(
                    "HEALTHAI_DB_POOL_TIMEOUT_SECONDS", 30, 1
                ),
                "pool_use_lifo": True,
            }
        )
    if is_sqlite:
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
    return options


def _configure_sqlite_connection(dbapi_connection, _) -> None:
    """Ativa integridade e tolerância básica a concorrência no SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def _create_database_engine(database_url: str) -> Engine:
    database_engine = create_engine(database_url, **_engine_options(database_url))
    if _database_backend(database_url) == "sqlite":
        event.listen(database_engine, "connect", _configure_sqlite_connection)
    return database_engine


READ_DATABASE_URLS = _read_database_urls(
    DATABASE_URL,
    setting("HEALTHAI_READ_DATABASE_URLS"),
)
READ_REPLICA_FALLBACK = _boolean_setting(
    "HEALTHAI_READ_REPLICA_FALLBACK",
    True,
)

engine = _create_database_engine(DATABASE_URL)
read_engines = tuple(_create_database_engine(url) for url in READ_DATABASE_URLS)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class ReadOnlySession(Session):
    """Sessão que falha cedo caso uma rota de leitura tente escrever."""

    def execute(self, statement, *args, **kwargs):
        raw_sql_is_not_read = isinstance(statement, TextClause) and not (
            statement.text.lstrip().upper().startswith(("SELECT", "SHOW", "EXPLAIN"))
        )
        if (
            getattr(statement, "is_dml", False)
            or getattr(statement, "is_ddl", False)
            or raw_sql_is_not_read
        ):
            raise InvalidRequestError(
                "A sessão de read replica aceita apenas leituras."
            )
        return super().execute(statement, *args, **kwargs)

    def flush(self, objects=None) -> None:
        if self.new or self.dirty or self.deleted:
            raise InvalidRequestError(
                "A sessão de read replica aceita apenas leituras."
            )
        super().flush(objects)

    def commit(self) -> None:
        raise InvalidRequestError("A sessão de read replica não permite commit.")


PrimaryReadSessionLocal = sessionmaker(
    bind=engine,
    class_=ReadOnlySession,
    expire_on_commit=False,
)
ReadSessionLocals = tuple(
    sessionmaker(bind=read_engine, class_=ReadOnlySession, expire_on_commit=False)
    for read_engine in read_engines
)
_read_replica_lock = Lock()
_read_replica_cursor = 0


class Base(DeclarativeBase):
    pass


def _next_read_session_factory():
    """Distribui novas sessões igualmente entre as réplicas disponíveis."""
    global _read_replica_cursor
    if not ReadSessionLocals:
        return PrimaryReadSessionLocal, None
    with _read_replica_lock:
        replica_index = _read_replica_cursor % len(ReadSessionLocals)
        _read_replica_cursor += 1
    return ReadSessionLocals[replica_index], replica_index


def init_database() -> None:
    """Atualiza somente o banco primário até a revisão mais recente."""
    config = Config(PROJECT_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    command.upgrade(config, "head")


def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão transacional no banco primário por requisição."""
    with SessionLocal() as session:
        yield session


def get_read_db() -> Generator[Session, None, None]:
    """Fornece uma sessão somente de leitura em uma réplica ou no primário."""
    session_factory, replica_index = _next_read_session_factory()
    session = session_factory()
    try:
        if replica_index is not None:
            try:
                # Faz o checkout agora para que falhas de conexão possam usar o
                # fallback antes de a consulta da rota ser executada.
                session.connection()
            except SQLAlchemyError:
                session.close()
                if not READ_REPLICA_FALLBACK:
                    raise
                logger.warning(
                    "read_replica_unavailable replica=%s fallback=primary",
                    replica_index + 1,
                )
                session = PrimaryReadSessionLocal()
        yield session
    finally:
        session.close()
