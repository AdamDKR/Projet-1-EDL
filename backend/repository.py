"""Toutes les requêtes SQL. Si le schéma change, c'est le seul fichier à adapter."""


def list_groups(conn):
    rows = conn.execute(
        'SELECT id, name, start_date, end_date FROM "Group" ORDER BY start_date, id'
    ).fetchall()
    return [dict(row) for row in rows]


def find_group(conn, group_id):
    row = conn.execute(
        'SELECT id, name, start_date, end_date FROM "Group" WHERE id = ?', [group_id]
    ).fetchone()
    return dict(row) if row is not None else None


def insert_group(conn, name, start_date, end_date):
    return conn.execute(
        'INSERT INTO "Group" (name, start_date, end_date) VALUES (?, ?, ?)',
        [name, start_date, end_date],
    ).lastrowid


def list_members(conn, group_id):
    rows = conn.execute(
        """
        SELECT m.id, m.person_id, p.name
        FROM Member m
        JOIN Person p ON p.id = m.person_id
        WHERE m.group_id = ?
        ORDER BY m.id
        """,
        [group_id],
    ).fetchall()
    return [dict(row) for row in rows]


def find_person_id_by_name(conn, name):
    row = conn.execute(
        "SELECT id FROM Person WHERE name = ? ORDER BY id LIMIT 1", [name]
    ).fetchone()
    return row["id"] if row is not None else None


def insert_person(conn, name):
    return conn.execute("INSERT INTO Person (name) VALUES (?)", [name]).lastrowid


def insert_member(conn, person_id, group_id):
    return conn.execute(
        "INSERT INTO Member (person_id, group_id) VALUES (?, ?)", [person_id, group_id]
    ).lastrowid


def list_expenses(conn, group_id):
    # Le schéma stocke le payeur comme une personne : l'API, elle, expose son id de membre.
    rows = conn.execute(
        """
        SELECT e.id, e.label, e.amount_cents, e.date, m.id AS payer_id, p.name AS payer
        FROM Expense e
        JOIN Member m ON m.person_id = e.person_id AND m.group_id = e.group_id
        JOIN Person p ON p.id = e.person_id
        WHERE e.group_id = ?
        ORDER BY e.date, e.id
        """,
        [group_id],
    ).fetchall()
    return [dict(row) for row in rows]


def list_participants(conn, group_id):
    """Renvoie les participants de toutes les dépenses du groupe, dans leur ordre d'ajout."""
    # Dans le schéma, l'ordre des id de ExpenseParticipant est l'ordre d'ajout.
    rows = conn.execute(
        """
        SELECT ep.expense_id, m.id, p.name
        FROM ExpenseParticipant ep
        JOIN Expense e ON e.id = ep.expense_id
        JOIN Member m ON m.id = ep.member_id
        JOIN Person p ON p.id = m.person_id
        WHERE e.group_id = ?
        ORDER BY ep.id
        """,
        [group_id],
    ).fetchall()
    return [dict(row) for row in rows]


def insert_expense(conn, group_id, label, amount_cents, date, payer_person_id):
    return conn.execute(
        """
        INSERT INTO Expense (group_id, label, amount_cents, date, person_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        [group_id, label, amount_cents, date, payer_person_id],
    ).lastrowid


def insert_participant(conn, expense_id, member_id):
    conn.execute(
        "INSERT INTO ExpenseParticipant (expense_id, member_id) VALUES (?, ?)",
        [expense_id, member_id],
    )


def delete_expense(conn, group_id, expense_id):
    """Renvoie False si la dépense n'existe pas dans ce groupe."""
    # Les participants partent en cascade : le schéma interdit de retirer le dernier à la main.
    cursor = conn.execute(
        "DELETE FROM Expense WHERE id = ? AND group_id = ?", [expense_id, group_id]
    )
    return cursor.rowcount > 0
