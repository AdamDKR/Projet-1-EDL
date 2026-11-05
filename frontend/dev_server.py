"""Serveur de développement et d'exécution Partage de frais.

Connecté directement au backend, à la base SQLite et aux templates Jinja2.
Lancer avec :
    python frontend/dev_server.py
ou :
    python backend/app.py
"""
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import app

if __name__ == "__main__":
    print("Démarrage du serveur Partage de frais...")
    print("Ouvrez http://127.0.0.1:5000 dans votre navigateur.")
    app.run(host="127.0.0.1", port=5000, debug=True)
