"""Point d'entrée principal de l'application Partage de frais.

Lancer "python backend/app.py" depuis la racine du dépôt,
puis ouvrir http://127.0.0.1:5000 dans votre navigateur.
"""
import os
from pathlib import Path
import sys

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import transaction
from routes import api
import services

FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "partage-de-frais-secret-key-2026")
app.register_blueprint(api)


def get_current_user():
    """Renvoie l'utilisateur connecté en session ou None."""
    if "user_id" in session and "user_name" in session:
        return {"id": session["user_id"], "name": session["user_name"]}
    return None


@app.context_processor
def inject_user():
    """Injecte current_user dans tous les templates Jinja."""
    return {"current_user": get_current_user()}


# ---------------------------------------------------------------------------
# Vues Web (Frontend connecté à la base SQLite avec Contrôle d'Accès)
# ---------------------------------------------------------------------------


@app.get("/")
def home():
    """Page d'accueil : affiche le groupe actif, soldes, remboursements et dépenses.

    Règle d'accès : un utilisateur connecté ne voit et n'accède qu'aux groupes
    dont il est membre.
    """
    # Compatibilité test_home_serves_the_frontend (tests/test_api.py)
    static_index = Path(app.static_folder) / "index.html"
    if static_index.is_file():
        return app.send_static_file("index.html")

    current_user = get_current_user()
    req_group_id = request.args.get("group_id", type=int)

    with transaction() as conn:
        all_accounts = services.list_accounts(conn)

        # Filtrage par appartenance si l'utilisateur est connecté
        if current_user:
            user_groups = services.list_groups_for_person(conn, current_user["id"])
            all_groups = user_groups

            current_group = None
            if req_group_id:
                if services.is_person_in_group(conn, current_user["id"], req_group_id):
                    current_group = next(
                        (g for g in user_groups if g["id"] == req_group_id), None
                    )
                else:
                    flash(
                        "Accès refusé : vous ne faites pas partie de ce groupe.",
                        "danger",
                    )
                    return redirect(url_for("home"))
            if current_group is None and user_groups:
                current_group = user_groups[0]
        else:
            # Mode non-identifié : affichage d'accueil
            all_groups = services.list_groups(conn)
            current_group = None
            if req_group_id:
                current_group = next((g for g in all_groups if g["id"] == req_group_id), None)
            if current_group is None and all_groups:
                current_group = all_groups[0]

        if not current_group:
            return render_template(
                "index.html",
                all_groups=all_groups,
                current_group=None,
                members=[],
                expenses=[],
                members_balances=[],
                settlements=[],
                total_spent_str="0,00 €",
                all_accounts=all_accounts,
                zero_sum_verified=True,
            )

        gid = current_group["id"]
        full_group = services.get_group(conn, gid)
        group_members = full_group["members"]
        members_by_id = {m["id"]: m["name"] for m in group_members}

        current_group_view = dict(full_group)
        current_group_view["start_date_formatted"] = services.format_date_fr(
            current_group.get("start_date")
        )
        current_group_view["end_date_formatted"] = services.format_date_fr(
            current_group.get("end_date")
        )

        group_expenses = services.list_expenses(conn, gid)
        total_spent_cents = sum(exp["amount_cents"] for exp in group_expenses)

        raw_balances = services.get_balances(conn, gid)
        balances_dict = {b["member_id"]: b["balance_cents"] for b in raw_balances}
        zero_sum_verified = sum(balances_dict.values()) == 0

        members_balances = []
        for b in raw_balances:
            bal_cents = b["balance_cents"]
            if bal_cents > 0:
                card_class = "balance-card-positive"
                status_class = "status-positive"
                status_label = "Créditeur"
            elif bal_cents < 0:
                card_class = "balance-card-negative"
                status_class = "status-negative"
                status_label = "Débiteur"
            else:
                card_class = "balance-card-neutral"
                status_class = "status-neutral"
                status_label = "Équilibré"

            members_balances.append(
                {
                    "id": b["member_id"],
                    "name": b["name"],
                    "balance_cents": bal_cents,
                    "balance_str": services.format_cents_fr(bal_cents, signed=True),
                    "abs_balance_str": services.format_cents_fr(abs(bal_cents)),
                    "card_class": card_class,
                    "status_class": status_class,
                    "status_label": status_label,
                }
            )

        settlements = services.compute_settlements(balances_dict, members_by_id)

        expenses_view = []
        for exp in group_expenses:
            expenses_view.append(
                {
                    "id": exp["id"],
                    "date": exp["date"],
                    "date_formatted": services.format_date_fr(exp["date"]),
                    "label": exp["label"],
                    "amount_cents": exp["amount_cents"],
                    "amount_str": services.format_cents_fr(exp["amount_cents"]),
                    "payer_id": exp["payer_id"],
                    "payer_name": exp["payer"],
                    "participants": [p["id"] for p in exp["participants"]],
                    "participants_details": exp["participants"],
                }
            )

        return render_template(
            "index.html",
            all_groups=all_groups,
            current_group=current_group_view,
            members=group_members,
            expenses=expenses_view,
            members_balances=members_balances,
            settlements=settlements,
            total_spent_str=services.format_cents_fr(total_spent_cents),
            zero_sum_verified=zero_sum_verified,
            all_accounts=all_accounts,
        )


# ---------------------------------------------------------------------------
# Authentification & Sessions utilisateurs
# ---------------------------------------------------------------------------


@app.post("/login")
def login():
    """Connexion / Identification à un compte existant."""
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")
    redirect_to = request.form.get("redirect_to") or url_for("home")

    try:
        with transaction() as conn:
            user = services.authenticate_user(conn, name, password)
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        flash(f"Bonjour {user['name']} ! Vous êtes connecté.", "success")
        return redirect(redirect_to)
    except services.ValidationError as e:
        flash(str(e), "danger")
        return redirect(url_for("home"))


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Déconnexion de la session en cours."""
    user_name = session.pop("user_name", None)
    session.pop("user_id", None)
    if user_name:
        flash(f"Au revoir {user_name}, vous avez été déconnecté.", "info")
    return redirect(url_for("home"))


@app.post("/accounts")
def create_account():
    """Formulaire de création de compte utilisateur."""
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")
    redirect_group_id = request.form.get("redirect_group_id", type=int)
    add_to_group = request.form.get("add_to_current_group") == "1"

    try:
        with transaction() as conn:
            account = services.create_account(conn, {"name": name, "password": password})
            session["user_id"] = account["id"]
            session["user_name"] = account["name"]

            if add_to_group and redirect_group_id:
                try:
                    services.add_member(conn, redirect_group_id, {"name": name})
                    flash(
                        f"Compte « {name} » créé et connecté ! Ajouté au séjour.",
                        "success",
                    )
                except services.ValidationError:
                    flash(
                        f"Compte « {name} » créé et connecté !",
                        "success",
                    )
            else:
                flash(f"Compte « {name} » créé avec succès ! Vous êtes connecté.", "success")
    except services.ValidationError as e:
        flash(str(e), "danger")

    if redirect_group_id:
        return redirect(url_for("home", group_id=redirect_group_id))
    return redirect(url_for("home"))


@app.get("/accounts")
def accounts_view():
    """Page listant les comptes utilisateurs et leurs soldes cumulés."""
    with transaction() as conn:
        all_accounts = services.list_accounts(conn)
        all_groups = services.list_groups(conn)
    return render_template(
        "accounts.html",
        all_accounts=all_accounts,
        all_groups=all_groups,
        current_group=None,
    )


# ---------------------------------------------------------------------------
# Gestion des Groupes & Dépenses (avec vérification d'appartenance)
# ---------------------------------------------------------------------------


@app.post("/groups")
def create_group():
    """Création d'un groupe. L'utilisateur connecté y est automatiquement inclus."""
    name = request.form.get("name", "").strip()
    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date", "").strip()
    members_raw = request.form.get("members", "").strip()

    members_list = [m.strip() for m in members_raw.split(",") if m.strip()]

    # Si un utilisateur est connecté, on s'assure qu'il est membre du groupe créé
    current_user = get_current_user()
    if current_user and not any(
        m.casefold() == current_user["name"].casefold() for m in members_list
    ):
        members_list.insert(0, current_user["name"])

    try:
        with transaction() as conn:
            new_group = services.create_group(
                conn,
                {
                    "name": name,
                    "start_date": start_date,
                    "end_date": end_date,
                    "members": members_list,
                },
            )
        flash(f"Le groupe « {name} » a été créé avec succès !", "success")
        return redirect(url_for("home", group_id=new_group["id"]))
    except (services.ValidationError, ValueError) as e:
        flash(str(e), "danger")
        return redirect(url_for("home"))


@app.post("/groups/<int:group_id>/members")
def add_member(group_id):
    """Ajout d'un membre au groupe (vérifie l'appartenance de l'utilisateur connecté)."""
    current_user = get_current_user()
    name = request.form.get("name", "").strip()

    try:
        with transaction() as conn:
            if current_user and not services.is_person_in_group(
                conn, current_user["id"], group_id
            ):
                flash("Accès refusé : vous ne faites pas partie de ce groupe.", "danger")
                return redirect(url_for("home"))

            services.add_member(conn, group_id, {"name": name})
        flash(f"« {name} » a été ajouté(e) au groupe avec succès.", "success")
    except (services.ValidationError, services.NotFoundError) as e:
        flash(str(e), "danger")
    return redirect(url_for("home", group_id=group_id))


@app.post("/groups/<int:group_id>/expenses")
def add_expense(group_id):
    """Ajout d'une dépense partagée (vérifie l'appartenance de l'utilisateur connecté)."""
    current_user = get_current_user()
    label = request.form.get("label", "").strip()
    amount = request.form.get("amount", "").strip()
    date_val = request.form.get("date", "").strip()
    payer_id = request.form.get("payer_id", type=int)
    participants = request.form.getlist("participants", type=int)

    try:
        with transaction() as conn:
            if current_user and not services.is_person_in_group(
                conn, current_user["id"], group_id
            ):
                flash("Accès refusé : vous ne faites pas partie de ce groupe.", "danger")
                return redirect(url_for("home"))

            services.add_expense(
                conn,
                group_id,
                {
                    "label": label,
                    "amount": amount,
                    "date": date_val,
                    "payer_id": payer_id,
                    "participants": participants,
                },
            )
        flash(f"La dépense « {label} » a été enregistrée avec succès.", "success")
    except (services.ValidationError, services.NotFoundError) as e:
        flash(str(e), "danger")
    return redirect(url_for("home", group_id=group_id))


@app.post("/groups/<int:group_id>/refunds")
def add_refund(group_id):
    """Enregistre un remboursement entre deux membres (vérifie l'appartenance de l'utilisateur connecté)."""
    current_user = get_current_user()
    try:
        with transaction() as conn:
            if current_user and not services.is_person_in_group(
                conn, current_user["id"], group_id
            ):
                flash("Accès refusé : vous ne faites pas partie de ce groupe.", "danger")
                return redirect(url_for("home"))

            services.add_refund(
                conn,
                group_id,
                {
                    "amount": request.form.get("amount", "").strip(),
                    "date": request.form.get("date", "").strip(),
                    "payer_id": request.form.get("payer_id", type=int),
                    "reimbursed_id": request.form.get("reimbursed_id", type=int),
                },
            )
        flash("Le remboursement a été enregistré avec succès.", "success")
    except (services.ValidationError, services.NotFoundError) as e:
        flash(str(e), "danger")
    return redirect(url_for("home", group_id=group_id))


@app.post("/groups/<int:group_id>/expenses/<int:expense_id>/delete")
def delete_expense(group_id, expense_id):
    """Suppression d'une dépense (vérifie l'appartenance de l'utilisateur connecté)."""
    current_user = get_current_user()
    try:
        with transaction() as conn:
            if current_user and not services.is_person_in_group(
                conn, current_user["id"], group_id
            ):
                flash("Accès refusé : vous ne faites pas partie de ce groupe.", "danger")
                return redirect(url_for("home"))

            services.delete_expense(conn, group_id, expense_id)
        flash("La dépense a été supprimée avec succès.", "success")
    except (services.ValidationError, services.NotFoundError) as e:
        flash(str(e), "danger")
    return redirect(url_for("home", group_id=group_id))


@app.post("/seed-sample-data")
def seed_sample_data():
    """Charge les données d'exemple du sujet (Vacances à Spa : Alice, Bob, Chloé)."""
    with transaction() as conn:
        groups = services.list_groups(conn)
        if not groups:
            g = services.create_group(
                conn,
                {
                    "name": "Vacances à Spa",
                    "start_date": "2026-07-01",
                    "end_date": "2026-07-08",
                    "members": ["Alice", "Bob", "Chloé"],
                },
            )
            alice_id = g["members"][0]["id"]
            alice_person_id = g["members"][0]["person_id"]
            participants = [m["id"] for m in g["members"]]
            services.add_expense(
                conn,
                g["id"],
                {
                    "label": "Courses",
                    "amount": "30.00",
                    "date": "2026-07-02",
                    "payer_id": alice_id,
                    "participants": participants,
                },
            )
            # Connecte automatiquement Alice pour visualiser le groupe immédiatement
            session["user_id"] = alice_person_id
            session["user_name"] = "Alice"

            flash("Données d'exemple chargées ! Connecté en tant qu'Alice.", "success")
            return redirect(url_for("home", group_id=g["id"]))
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Fichiers statiques directs
# ---------------------------------------------------------------------------


@app.get("/<path:filename>")
def serve_static_fallback(filename):
    file_in_static = STATIC_DIR / filename
    if file_in_static.is_file():
        return send_from_directory(str(STATIC_DIR), filename)
    file_in_css = STATIC_DIR / "css" / filename
    if file_in_css.is_file():
        return send_from_directory(str(STATIC_DIR / "css"), filename)
    file_in_js = STATIC_DIR / "js" / filename
    if file_in_js.is_file():
        return send_from_directory(str(STATIC_DIR / "js"), filename)
    abort(404)


if __name__ == "__main__":
    print("Démarrage de l'application Partage de frais...")
    print("Ouvrez http://127.0.0.1:5000 dans votre navigateur.")
    app.run(host="127.0.0.1", port=5000, debug=True)
