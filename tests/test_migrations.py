from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from backend.database import Base
from backend.models import User

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "alembic_version",
    "email_verification_tokens",
    "prediction_results",
    "user_sessions",
    "users",
    "crm_review_events",
    "password_reset_tokens",
}


def alembic_config(database_path: Path) -> Config:
    config = Config(PROJECT_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    return config


def test_migrations_create_fresh_database(tmp_path: Path) -> None:
    database_path = tmp_path / "fresh.db"
    config = alembic_config(database_path)

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    assert EXPECTED_TABLES <= set(inspector.get_table_names())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert {
        "crm",
        "crm_uf",
        "crm_status",
        "crm_verified_at",
        "crm_verified_by",
        "crm_rejection_reason",
        "terms_accepted_at",
        "terms_version",
    } <= user_columns
    with engine.connect() as connection:
        revision = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
    result_columns = {
        column["name"] for column in inspector.get_columns("prediction_results")
    }
    assert {
        "model_version",
        "input_completeness",
        "missing_feature_count",
    } <= result_columns
    indexes = {
        table: {index["name"] for index in inspector.get_indexes(table)}
        for table in EXPECTED_TABLES - {"alembic_version"}
    }
    assert {
        "ix_prediction_results_user_created_id",
        "ix_prediction_results_created_at",
    } <= indexes["prediction_results"]
    assert {
        "ix_users_created_at",
        "ix_users_crm_status_created",
        "ix_users_crm_verified_by",
    } <= indexes["users"]
    assert "ix_user_sessions_user_id" in indexes["user_sessions"]
    assert (
        "ix_email_verification_tokens_user_created"
        in indexes["email_verification_tokens"]
    )
    assert (
        "ix_password_reset_tokens_user_created"
        in indexes["password_reset_tokens"]
    )
    assert {
        "ix_crm_review_events_user_created_id",
        "ix_crm_review_events_reviewer_id",
    } <= indexes["crm_review_events"]
    assert revision == "20260713_10"
    command.check(config)
    engine.dispose()


def test_migrations_adopt_legacy_database_without_losing_data(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{database_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            User(
                email="legacy@example.com",
                name="Usuário existente",
                password_hash="hash-existente",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    engine.dispose()

    command.upgrade(alembic_config(database_path), "head")

    migrated_engine = create_engine(f"sqlite:///{database_path}")
    with Session(migrated_engine) as session:
        user = session.scalar(select(User).where(User.email == "legacy@example.com"))
        assert user is not None
        assert user.name == "Usuário existente"
        assert user.email_verified_at is not None
    assert EXPECTED_TABLES <= set(inspect(migrated_engine).get_table_names())
    migrated_engine.dispose()


def test_privacy_migration_removes_existing_patient_names(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "with_names.db"
    config = alembic_config(database_path)
    command.upgrade(config, "20260703_01")

    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            INSERT INTO users
                (id, email, name, password_hash, role, is_active, created_at)
            VALUES
                (1, 'legacy@example.com', 'Legado', 'hash', 'user', 1,
                 '2026-01-01 00:00:00')
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO prediction_results
                (id, user_id, patient_name, experiment, model,
                 predicted_class, probability, decision_threshold, created_at)
            VALUES
                (1, 1, 'Nome que deve desaparecer', 'Pima', 'Random Forest',
                 0, 0.2, 0.35, '2026-01-01 00:00:00')
            """
        )
    engine.dispose()

    command.upgrade(config, "head")

    migrated_engine = create_engine(f"sqlite:///{database_path}")
    columns = {
        column["name"]
        for column in inspect(migrated_engine).get_columns("prediction_results")
    }
    assert "patient_name" not in columns
    assert "patient_identifier" in columns
    with migrated_engine.connect() as connection:
        identifier = connection.exec_driver_sql(
            "SELECT patient_identifier FROM prediction_results WHERE id = 1"
        ).scalar_one()
        profile = connection.exec_driver_sql(
            "SELECT experiment FROM prediction_results WHERE id = 1"
        ).scalar_one()
    assert identifier.startswith("PAC-")
    assert "Nome" not in identifier
    assert profile == "Perfil feminino"
    migrated_engine.dispose()
