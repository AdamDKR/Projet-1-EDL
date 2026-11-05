"""Ouverture de la base SQLite."""
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = ROOT / "data.db"
# Fichier SQL du schéma, utilisé pour créer data.db s'il n'existe pas encore.
SCHEMA_PATH = ROOT / "base.sql"


def open_database():
    # Le schéma est lu avant la connexion, pour ne pas laisser une base vide en cas d'erreur.
    schema = SCHEMA_PATH.read_text(encoding="utf-8") if not DATABASE_PATH.exists() else None
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if schema is not None:
        conn.executescript(schema)
    return conn


@contextmanager
def transaction():
    """Tout est validé à la fin du bloc, ou annulé en cas d'erreur, puis la connexion est fermée."""
    with closing(open_database()) as conn, conn:
        yield conn
