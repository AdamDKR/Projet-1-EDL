from pathlib import Path

import pytest

import database

SCHEMA = Path(__file__).parent / "schema.sql"


@pytest.fixture(autouse=True)
def temporary_database(tmp_path, monkeypatch):
    """Chaque test utilise une base neuve : data.db n'est jamais touché."""
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(database, "SCHEMA_PATH", SCHEMA)
