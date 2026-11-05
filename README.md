# Partage de frais

> **Noter les dépenses d’un séjour entre amis et savoir à tout moment qui doit combien à qui.**

Séance 1 · En binôme · Master 1 Informatique — UMONS · Expertises digitale et logicielle.

---

## Ce que fait l’application

- [x] **Créer un groupe de séjour et ses membres** (avec dates de début et de fin).
- [x] **Créer des comptes utilisateurs** (personnes réutilisables entre plusieurs séjours, consultation du bilan net global).
- [x] **Ajouter ou supprimer une dépense partagée** (libellé, montant en euros, date du séjour, payeur, sélection des participants).
- [x] **Afficher les soldes individuels et suggérer les règlements** (algorithme qui doit combien à qui).
- [x] **Validation stricte de toutes les règles métier** :
  - Montant positif au centime près.
  - La somme de tous les soldes vaut toujours 0,00 €.
  - Règle des centimes restants : distribués un à un aux premiers participants ajoutés.
  - Date de la dépense strictement comprise dans les dates du séjour.
  - Vérification de l'appartenance des membres et payeurs au groupe.

---

## Installation et lancement

Python 3.11 ou supérieur est requis.

### 1. Cloner et installer les dépendances

Sous Windows (PowerShell) :

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process RemoteSigned
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Sous macOS ou Linux :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Lancer les tests

```bash
pytest
```

> **271 tests** couvrent l'API REST, le moteur de règles métier, les cas limites et l'interface web.

### 3. Lancer l'application

```bash
python backend/app.py
```

Puis ouvrez votre navigateur à l'adresse : **<http://127.0.0.1:5000>**

*(Alternativement, `python frontend/dev_server.py` lance également la même application intégrée).*

---

## Structure du projet

```
Projet-1-EDL/
├── backend/
│   ├── app.py            # Point d'entrée principal Flask & routes Web
│   ├── routes.py         # Routes API JSON REST (/api/...)
│   ├── services.py       # Logique métier, calcul des soldes, règlements et validation
│   ├── repository.py     # Requêtes SQL SQLite
│   └── database.py       # Connexion SQLite et gestion des transactions
├── db/
│   ├── schema.sql        # Schéma de la base SQLite, triggers, vues v_share et v_balance
│   └── queries.sql       # Requêtes de référence
├── frontend/
│   ├── templates/        # Templates Jinja2 (base.html, index.html, accounts.html)
│   ├── static/css/       # Feuilles de style CSS modernes et responsives
│   └── static/js/        # Interactions (modales, validation client, sélecteur)
├── tests/
│   ├── conftest.py       # Fixtures pytest (base de test temporaire isolée)
│   ├── test_api.py       # Tests d'intégration de l'API et des routes web
│   └── test_services.py  # Tests unitaires de la logique métier
└── docs/
    └── API.md            # Documentation exhaustive de l'API JSON
```

---

## API REST

L'API est documentée dans [`docs/API.md`](docs/API.md). Toutes les routes retournent du JSON :

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/api/groups` | Lister les séjours |
| `POST` | `/api/groups` | Créer un séjour |
| `GET` | `/api/groups/<id>` | Détails d'un séjour et membres |
| `POST` | `/api/groups/<id>/members` | Ajouter un membre au séjour |
| `GET` | `/api/groups/<id>/expenses` | Lister les dépenses d'un séjour |
| `POST` | `/api/groups/<id>/expenses` | Ajouter une dépense |
| `DELETE` | `/api/groups/<id>/expenses/<expense_id>` | Supprimer une dépense |
| `GET` | `/api/groups/<id>/balances` | Obtenir les soldes des membres |
| `GET` | `/api/accounts` | Lister les comptes utilisateurs et soldes cumulés |
| `POST` | `/api/accounts` | Créer un compte utilisateur |
