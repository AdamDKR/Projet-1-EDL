"""Ouverture de la base SQLite."""
import sqlite3
import threading
from contextlib import closing, contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = ROOT / "data.db"
# Fichier SQL du schéma, utilisé pour créer data.db s'il n'existe pas encore.
SCHEMA_PATH = ROOT / "db" / "schema.sql"

# Le frontend peut envoyer plusieurs requêtes à la fois : une seule doit créer la base.
_creation_lock = threading.Lock()


def _create_database():
    # La base est construite à part, pour ne jamais laisser un data.db incomplet en cas d'erreur.
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    temporary_path = DATABASE_PATH.with_name(DATABASE_PATH.name + ".tmp")
    temporary_path.unlink(missing_ok=True)
    with closing(sqlite3.connect(temporary_path)) as conn:
        conn.executescript(schema)
    temporary_path.replace(DATABASE_PATH)


def open_database():
    with _creation_lock:
        if not DATABASE_PATH.exists():
            _create_database()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction():
    """Tout est validé à la fin du bloc, ou annulé en cas d'erreur, puis la connexion est fermée."""
    with closing(open_database()) as conn, conn:
        yield conn
