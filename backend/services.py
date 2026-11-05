"""Règles du partage de frais et calcul des soldes. Aucun SQL ni code HTTP ici."""
import re
from datetime import date

import repository


class ValidationError(Exception):
    """Les données reçues ne respectent pas une règle du sujet."""


class NotFoundError(Exception):
    """Le groupe ou la dépense demandé n'existe pas."""


# --- Lecture et contrôle des valeurs reçues ---


def parse_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'The "{field}" field is required.')
    return value.strip()


def parse_date(value, field):
    """Accepte uniquement le format AAAA-MM-JJ, seul à se comparer correctement en texte."""
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            pass
    raise ValidationError(f'The "{field}" field must be a valid date in YYYY-MM-DD format.')


def parse_amount(value):
    """Convertit 30, "30", "12,50" ou 12.5 en centimes, sans calcul à virgule flottante."""
    message = "The amount must be a positive number with at most 2 decimals."
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValidationError(message)
    text = str(value).strip().replace(",", ".")
    match = re.fullmatch(r"([0-9]{1,10})(?:\.([0-9]{1,2}))?", text)
    if match is None:
        raise ValidationError(message)
    euros, decimals = match.groups()
    cents = int(euros) * 100 + int((decimals or "").ljust(2, "0"))
    if cents <= 0:
        raise ValidationError("The amount must be greater than zero.")
    return cents


def format_cents(cents, signed=False):
    """3000 -> "30.00". Avec signed=True : "+30.00", "-30.00" ou "0.00"."""
    prefix = "-" if cents < 0 else ("+" if signed and cents > 0 else "")
    euros, remainder = divmod(abs(cents), 100)
    return f"{prefix}{euros}.{remainder:02d}"


def _is_id(value):
    return isinstance(value, int) and not isinstance(value, bool)


# --- Calcul des soldes ---


def compute_balances(member_ids, expenses):
    """Renvoie {member_id: solde en centimes}. La somme des soldes vaut toujours 0.

    Chaque dépense contient amount_cents, payer_id et participants, ces derniers dans
    leur ordre d'ajout. Les centimes restants sont donnés un par un, en commençant par
    le premier participant : avec 2 centimes restants, le premier et le deuxième en
    reçoivent chacun un.
    """
    balances = dict.fromkeys(member_ids, 0)
    for expense in expenses:
        amount = expense["amount_cents"]
        participants = expense["participants"]
        share, remainder = divmod(amount, len(participants))
        balances[expense["payer_id"]] += amount
        for rank, member_id in enumerate(participants):
            balances[member_id] -= share + (1 if rank < remainder else 0)
    return balances


# --- Groupes et membres ---


def list_groups(conn):
    return repository.list_groups(conn)


def get_group(conn, group_id):
    group = repository.find_group(conn, group_id)
    if group is None:
        raise NotFoundError("This group does not exist.")
    return {**group, "members": repository.list_members(conn, group_id)}


def _insert_member(conn, group_id, name, existing_names):
    name = parse_text(name, "name")
    if name.casefold() in existing_names:
        raise ValidationError(f'The member "{name}" already exists in this group.')
    existing_names.add(name.casefold())
    # Une personne déjà connue sous ce nom est réutilisée d'un groupe à l'autre.
    person_id = repository.find_person_id_by_name(conn, name)
    if person_id is None:
        person_id = repository.insert_person(conn, name)
    member_id = repository.insert_member(conn, person_id, group_id)
    return {"id": member_id, "person_id": person_id, "name": name}


def create_group(conn, data):
    name = parse_text(data.get("name"), "name")
    start_date = parse_date(data.get("start_date"), "start_date")
    end_date = parse_date(data.get("end_date"), "end_date")
    if start_date > end_date:
        raise ValidationError("The start date must not be after the end date.")
    members = data.get("members", [])
    if not isinstance(members, list):
        raise ValidationError('The "members" field must be a list of names.')

    group_id = repository.insert_group(conn, name, start_date, end_date)
    existing_names = set()
    for member_name in members:
        _insert_member(conn, group_id, member_name, existing_names)
    return get_group(conn, group_id)


def add_member(conn, group_id, data):
    group = get_group(conn, group_id)
    existing_names = {member["name"].casefold() for member in group["members"]}
    return _insert_member(conn, group_id, data.get("name"), existing_names)


# --- Dépenses ---


def list_expenses(conn, group_id):
    get_group(conn, group_id)
    expenses = {
        expense["id"]: {
            **expense,
            "amount": format_cents(expense["amount_cents"]),
            "participants": [],
        }
        for expense in repository.list_expenses(conn, group_id)
    }
    for participant in repository.list_participants(conn, group_id):
        expenses[participant["expense_id"]]["participants"].append(
            {"id": participant["id"], "name": participant["name"]}
        )
    return list(expenses.values())


def add_expense(conn, group_id, data):
    group = get_group(conn, group_id)
    group_member_ids = {member["id"] for member in group["members"]}

    label = parse_text(data.get("label"), "label")
    amount_cents = parse_amount(data.get("amount"))
    expense_date = parse_date(data.get("date"), "date")
    if not group["start_date"] <= expense_date <= group["end_date"]:
        raise ValidationError("The expense date must be within the stay.")

    payer_id = data.get("payer_id")
    if not _is_id(payer_id) or payer_id not in group_member_ids:
        raise ValidationError("The payer must belong to the group.")

    participants = data.get("participants")
    if not isinstance(participants, list) or not participants:
        raise ValidationError("An expense must have at least one participant.")
    if not all(_is_id(member_id) and member_id in group_member_ids for member_id in participants):
        raise ValidationError("All participants must belong to the group.")
    if len(set(participants)) != len(participants):
        raise ValidationError("A member can only participate once in an expense.")

    expense_id = repository.insert_expense(
        conn, group_id, label, amount_cents, expense_date, payer_id
    )
    for position, member_id in enumerate(participants, start=1):
        repository.insert_participant(conn, expense_id, member_id, position)
    return next(e for e in list_expenses(conn, group_id) if e["id"] == expense_id)


def delete_expense(conn, group_id, expense_id):
    get_group(conn, group_id)
    if not repository.delete_expense(conn, group_id, expense_id):
        raise NotFoundError("This expense does not exist in this group.")


# --- Soldes ---


def get_balances(conn, group_id):
    members = get_group(conn, group_id)["members"]
    expenses = [
        {
            "amount_cents": expense["amount_cents"],
            "payer_id": expense["payer_id"],
            "participants": [participant["id"] for participant in expense["participants"]],
        }
        for expense in list_expenses(conn, group_id)
    ]
    balances = compute_balances([member["id"] for member in members], expenses)
    return [
        {
            "member_id": member["id"],
            "name": member["name"],
            "balance_cents": balances[member["id"]],
            "balance": format_cents(balances[member["id"]], signed=True),
        }
        for member in members
    ]
