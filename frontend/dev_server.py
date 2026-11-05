"""Standalone Flask preview server for Partage de frais.

Points to frontend/templates and frontend/static, preloaded with mock data matching
base.sql (Spa group, Alice, Bob, Chloé).
Can be run directly:
    python frontend/dev_server.py
"""

from copy import deepcopy
from datetime import date
import os
from pathlib import Path
import re

from flask import Flask, flash, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
    static_url_path="/static",
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "partage-de-frais-preview-secret-key-2026")

# ---------------------------------------------------------------------------
# Initial Mock Data (matching base.sql)
# ---------------------------------------------------------------------------

INITIAL_GROUPS = [
    {
        "id": 1,
        "name": "Vacances à Spa",
        "nom": "Vacances à Spa",
        "start_date": "2026-07-01",
        "date_debut": "2026-07-01",
        "end_date": "2026-07-08",
        "date_fin": "2026-07-08",
    }
]

INITIAL_MEMBERS = [
    {"id": 1, "group_id": 1, "name": "Alice"},
    {"id": 2, "group_id": 1, "name": "Bob"},
    {"id": 3, "group_id": 1, "name": "Chloé"},
]

INITIAL_EXPENSES = [
    {
        "id": 1,
        "group_id": 1,
        "label": "Courses",
        "libelle": "Courses",
        "amount_cents": 3000,
        "date": "2026-07-02",
        "payer_id": 1,
        "participants": [1, 2, 3],
    }
]

groups_store = deepcopy(INITIAL_GROUPS)
members_store = deepcopy(INITIAL_MEMBERS)
expenses_store = deepcopy(INITIAL_EXPENSES)
next_group_id = 2
next_member_id = 4
next_expense_id = 2


def reset_mock_data():
    """Reset store to initial mock state (useful for tests)."""
    global groups_store, members_store, expenses_store
    global next_group_id, next_member_id, next_expense_id
    groups_store = deepcopy(INITIAL_GROUPS)
    members_store = deepcopy(INITIAL_MEMBERS)
    expenses_store = deepcopy(INITIAL_EXPENSES)
    next_group_id = 2
    next_member_id = 4
    next_expense_id = 2


# ---------------------------------------------------------------------------
# Calculation and Formatting Helpers
# ---------------------------------------------------------------------------


def parse_amount_to_cents(value):
    """Convert "30", "30.00", "12,50" or 30 into cents."""
    if not value:
        raise ValueError("Le montant est requis.")
    text = str(value).strip().replace(",", ".")
    match = re.fullmatch(r"([0-9]{1,10})(?:\.([0-9]{1,2}))?", text)
    if not match:
        raise ValueError("Le montant doit être un nombre positif avec au plus 2 décimales.")
    euros, decimals = match.groups()
    cents = int(euros) * 100 + int((decimals or "").ljust(2, "0"))
    if cents <= 0:
        raise ValueError("Le montant doit être strictement supérieur à zéro.")
    return cents


def parse_iso_date(value, field_name="date"):
    """Valide qu'une valeur est une date réelle au format AAAA-MM-JJ."""
    if not value or not isinstance(value, str):
        raise ValueError(f"La {field_name} est requise.")
    value = value.strip()
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError(f"La {field_name} doit être au format AAAA-MM-JJ (ex : 2026-07-01).")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"La {field_name} ({value}) n'est pas une date de calendrier valide.")
    return value


def format_cents_fr(cents, signed=False):
    """Format cents into French currency string (e.g. +20,00 € or -10,00 €)."""
    prefix = "-" if cents < 0 else ("+" if signed and cents > 0 else "")
    euros, rem = divmod(abs(cents), 100)
    return f"{prefix}{euros},{rem:02d} €"


def format_date_fr(date_str):
    """Format YYYY-MM-DD into DD/MM/YYYY."""
    if not date_str or len(date_str) != 10:
        return date_str
    try:
        parts = date_str.split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        return date_str


def compute_group_balances(member_ids, expenses):
    """Compute balance in cents for each member.

    Applies the rule:
    - Expense is split equally among participants.
    - Remaining cents are assigned one-by-one to participants in order of addition.
    - Sum of balances always equals 0.
    """
    balances = {mid: 0 for mid in member_ids}
    for exp in expenses:
        amount = exp["amount_cents"]
        participants = exp["participants"]
        if not participants:
            continue
        share, remainder = divmod(amount, len(participants))
        if exp["payer_id"] in balances:
            balances[exp["payer_id"]] += amount
        for rank, pid in enumerate(participants):
            if pid in balances:
                balances[pid] -= share + (1 if rank < remainder else 0)
    return balances


def compute_settlements(balances, members_by_id):
    """Calculate who owes how much to whom to settle debts.

    Greedy algorithm matching debtors and creditors.
    """
    debtors = []  # (member_id, amount_owed_in_cents)
    creditors = []  # (member_id, amount_to_receive_in_cents)

    for mid, bal in balances.items():
        if bal < 0:
            debtors.append([mid, -bal])
        elif bal > 0:
            creditors.append([mid, bal])

    # Sort descending by amount for clean, deterministic settlements
    debtors.sort(key=lambda x: -x[1])
    creditors.sort(key=lambda x: -x[1])

    settlements = []
    d_idx = 0
    c_idx = 0

    while d_idx < len(debtors) and c_idx < len(creditors):
        debtor_id, debt = debtors[d_idx]
        creditor_id, credit = creditors[c_idx]
        payment = min(debt, credit)

        if payment > 0:
            settlements.append({
                "debtor": members_by_id.get(debtor_id, f"Membre #{debtor_id}"),
                "creditor": members_by_id.get(creditor_id, f"Membre #{creditor_id}"),
                "amount_cents": payment,
                "amount_str": format_cents_fr(payment),
            })
            debtors[d_idx][1] -= payment
            creditors[c_idx][1] -= payment

        if debtors[d_idx][1] == 0:
            d_idx += 1
        if creditors[c_idx][1] == 0:
            c_idx += 1

    return settlements


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
def home():
    """Main view displaying active group, balances, settlements, expenses, forms."""
    req_group_id = request.args.get("group_id", type=int)

    # Find requested group or fallback to first
    current_group = None
    if req_group_id:
        current_group = next((g for g in groups_store if g["id"] == req_group_id), None)
    if current_group is None and groups_store:
        current_group = groups_store[0]

    if not current_group:
        return render_template(
            "index.html",
            all_groups=[],
            current_group=None,
            members=[],
            expenses=[],
            members_balances=[],
            settlements=[],
            total_spent_str="0,00 €",
        )

    gid = current_group["id"]
    group_members = [m for m in members_store if m["group_id"] == gid]
    members_by_id = {m["id"]: m["name"] for m in group_members}

    # Format group dates for display
    current_group_view = dict(current_group)
    current_group_view["start_date_formatted"] = format_date_fr(current_group.get("start_date"))
    current_group_view["end_date_formatted"] = format_date_fr(current_group.get("end_date"))

    # Group expenses (sorted chronologically by date then id)
    group_expenses = [exp for exp in expenses_store if exp["group_id"] == gid]
    group_expenses.sort(key=lambda x: (x.get("date", ""), x.get("id", 0)))
    total_spent_cents = sum(exp["amount_cents"] for exp in group_expenses)

    # Compute balances
    member_ids = [m["id"] for m in group_members]
    balances = compute_group_balances(member_ids, group_expenses)
    zero_sum_verified = (sum(balances.values()) == 0)

    # Build rich member balance view objects
    members_balances = []
    for m in group_members:
        bal_cents = balances.get(m["id"], 0)
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

        members_balances.append({
            "id": m["id"],
            "name": m["name"],
            "balance_cents": bal_cents,
            "balance_str": format_cents_fr(bal_cents, signed=True),
            "abs_balance_str": format_cents_fr(abs(bal_cents)),
            "card_class": card_class,
            "status_class": status_class,
            "status_label": status_label,
        })

    # Compute settlements
    settlements = compute_settlements(balances, members_by_id)

    # Format expenses for view
    expenses_view = []
    for exp in group_expenses:
        participants_details = [
            {"id": pid, "name": members_by_id.get(pid, f"Membre #{pid}")}
            for pid in exp["participants"]
        ]
        expenses_view.append({
            "id": exp["id"],
            "date": exp["date"],
            "date_formatted": format_date_fr(exp["date"]),
            "label": exp.get("label") or exp.get("libelle"),
            "amount_cents": exp["amount_cents"],
            "amount_str": format_cents_fr(exp["amount_cents"]),
            "payer_id": exp["payer_id"],
            "payer_name": members_by_id.get(exp["payer_id"], f"Membre #{exp['payer_id']}"),
            "participants": exp["participants"],
            "participants_details": participants_details,
        })

    return render_template(
        "index.html",
        all_groups=groups_store,
        current_group=current_group_view,
        members=group_members,
        expenses=expenses_view,
        members_balances=members_balances,
        settlements=settlements,
        total_spent_str=format_cents_fr(total_spent_cents),
        zero_sum_verified=zero_sum_verified,
    )


@app.post("/groups")
def create_group():
    """Create a new group with optional initial comma-separated members."""
    global next_group_id, next_member_id

    name = request.form.get("name", "").strip()
    start_date_raw = request.form.get("start_date", "").strip()
    end_date_raw = request.form.get("end_date", "").strip()
    members_raw = request.form.get("members", "").strip()

    if not name:
        flash("Le nom du groupe est obligatoire.", "danger")
        return redirect(url_for("home"))

    try:
        start_date = parse_iso_date(start_date_raw, "date de début")
        end_date = parse_iso_date(end_date_raw, "date de fin")
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("home"))

    if start_date > end_date:
        flash("La date de début ne peut pas être postérieure à la date de fin.", "danger")
        return redirect(url_for("home"))

    # Process initial members if provided
    initial_member_names = []
    if members_raw:
        raw_names = [n.strip() for n in members_raw.split(",") if n.strip()]
        seen_casefold = set()
        for member_name in raw_names:
            cf = member_name.casefold()
            if cf in seen_casefold:
                flash(f"Le membre « {member_name} » est mentionné plusieurs fois.", "danger")
                return redirect(url_for("home"))
            seen_casefold.add(cf)
            initial_member_names.append(member_name)

    new_group = {
        "id": next_group_id,
        "name": name,
        "nom": name,
        "start_date": start_date,
        "date_debut": start_date,
        "end_date": end_date,
        "date_fin": end_date,
    }
    next_group_id += 1
    groups_store.append(new_group)

    for member_name in initial_member_names:
        members_store.append({
            "id": next_member_id,
            "group_id": new_group["id"],
            "name": member_name,
        })
        next_member_id += 1

    flash(f"Le groupe « {name} » a été créé avec succès !", "success")
    return redirect(url_for("home", group_id=new_group["id"]))


@app.post("/groups/<int:group_id>/members")
def add_member(group_id):
    """Add a new member to an existing group."""
    global next_member_id

    group = next((g for g in groups_store if g["id"] == group_id), None)
    if not group:
        flash("Ce groupe n'existe pas.", "danger")
        return redirect(url_for("home"))

    name = request.form.get("name", "").strip()
    if not name:
        flash("Le nom du membre est obligatoire.", "danger")
        return redirect(url_for("home", group_id=group_id))

    existing = [m["name"].casefold() for m in members_store if m["group_id"] == group_id]
    if name.casefold() in existing:
        flash(f"Un membre nommé « {name} » existe déjà dans ce groupe.", "danger")
        return redirect(url_for("home", group_id=group_id))

    members_store.append({
        "id": next_member_id,
        "group_id": group_id,
        "name": name,
    })
    next_member_id += 1

    flash(f"« {name} » a été ajouté(e) au groupe avec succès.", "success")
    return redirect(url_for("home", group_id=group_id))


@app.post("/groups/<int:group_id>/expenses")
def add_expense(group_id):
    """Add an expense to the group."""
    global next_expense_id

    group = next((g for g in groups_store if g["id"] == group_id), None)
    if not group:
        flash("Ce groupe n'existe pas.", "danger")
        return redirect(url_for("home"))

    label = request.form.get("label", "").strip()
    amount_raw = request.form.get("amount", "").strip()
    expense_date_raw = request.form.get("date", "").strip()
    payer_id = request.form.get("payer_id", type=int)
    participant_ids = request.form.getlist("participants", type=int)

    if not label:
        flash("Le libellé de la dépense est obligatoire.", "danger")
        return redirect(url_for("home", group_id=group_id))

    try:
        amount_cents = parse_amount_to_cents(amount_raw)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("home", group_id=group_id))

    try:
        expense_date = parse_iso_date(expense_date_raw, "date de la dépense")
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("home", group_id=group_id))

    # Verify date is within group travel stay
    if not (group["start_date"] <= expense_date <= group["end_date"]):
        flash(
            f"La date de la dépense ({format_date_fr(expense_date)}) doit être comprise entre le "
            f"{format_date_fr(group['start_date'])} et le {format_date_fr(group['end_date'])}.",
            "danger",
        )
        return redirect(url_for("home", group_id=group_id))

    # Verify payer
    group_member_ids = {m["id"] for m in members_store if m["group_id"] == group_id}
    if payer_id not in group_member_ids:
        flash("Le payeur sélectionné n'appartient pas à ce groupe.", "danger")
        return redirect(url_for("home", group_id=group_id))

    # Verify participants
    if not participant_ids:
        flash("Une dépense doit avoir au moins un participant.", "danger")
        return redirect(url_for("home", group_id=group_id))

    if len(set(participant_ids)) != len(participant_ids):
        flash("Un membre ne peut participer qu'une seule fois à une même dépense.", "danger")
        return redirect(url_for("home", group_id=group_id))

    for pid in participant_ids:
        if pid not in group_member_ids:
            flash("Tous les participants doivent appartenir au groupe.", "danger")
            return redirect(url_for("home", group_id=group_id))

    new_expense = {
        "id": next_expense_id,
        "group_id": group_id,
        "label": label,
        "libelle": label,
        "amount_cents": amount_cents,
        "date": expense_date,
        "payer_id": payer_id,
        "participants": participant_ids,
    }
    next_expense_id += 1
    expenses_store.append(new_expense)

    flash(f"La dépense « {label} » ({format_cents_fr(amount_cents)}) a été ajoutée.", "success")
    return redirect(url_for("home", group_id=group_id))



@app.post("/groups/<int:group_id>/expenses/<int:expense_id>/delete")
def delete_expense(group_id, expense_id):
    """Delete an expense."""
    global expenses_store

    expense = next(
        (e for e in expenses_store if e["id"] == expense_id and e["group_id"] == group_id),
        None,
    )
    if not expense:
        flash("Dépense introuvable.", "danger")
        return redirect(url_for("home", group_id=group_id))

    expenses_store = [e for e in expenses_store if e["id"] != expense_id]
    label = expense.get("label") or expense.get("libelle")
    flash(f"La dépense « {label} » a été supprimée.", "success")
    return redirect(url_for("home", group_id=group_id))


if __name__ == "__main__":
    print("Démarrage du serveur de prévisualisation Partage de frais...")
    print("Ouvrez http://127.0.0.1:5000 dans votre navigateur.")
    app.run(host="127.0.0.1", port=5000, debug=True)
