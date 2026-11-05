# Point d'entrée de l'application : lancer "python backend/app.py" depuis la racine du dépôt.
from pathlib import Path

from flask import Flask

from routes import api

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Flask sert aussi les fichiers du frontend : la page et l'API ont la même adresse.
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.register_blueprint(api)


@app.get("/")
def home():
    return app.send_static_file("index.html")


if __name__ == "__main__":
    app.run(debug=True)
