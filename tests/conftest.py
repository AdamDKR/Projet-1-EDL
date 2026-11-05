import pytest

import database


@pytest.fixture(autouse=True)
def temporary_database(tmp_path, monkeypatch):
    """Chaque test utilise une base neuve, créée avec le vrai schéma : data.db n'est jamais touché."""
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
