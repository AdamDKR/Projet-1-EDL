"""Toutes les requêtes SQL. Si le schéma change, c'est le seul fichier à adapter."""


def list_groups(conn):
    rows = conn.execute(
        "SELECT id, name, startDate AS start_date, endDate AS end_date FROM Groups ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


def find_group(conn, group_id):
    row = conn.execute(
        "SELECT id, name, startDate AS start_date, endDate AS end_date FROM Groups WHERE id = ?",
        [group_id],
    ).fetchone()
    return dict(row) if row is not None else None


def insert_group(conn, name, start_date, end_date):
    return conn.execute(
        "INSERT INTO Groups (name, startDate, endDate) VALUES (?, ?, ?)",
        [name, start_date, end_date],
    ).lastrowid


def list_members(conn, group_id):
    rows = conn.execute(
        """
        SELECT m.id, m.personId AS person_id, p.name
        FROM Member m
        JOIN Person p ON p.id = m.personId
        WHERE m.groupId = ?
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
        "INSERT INTO Member (personId, groupId) VALUES (?, ?)", [person_id, group_id]
    ).lastrowid


def list_expenses(conn, group_id):
    rows = conn.execute(
        """
        SELECT e.id, e.label, e.amountCents AS amount_cents, e.date,
               e.payerMemberId AS payer_id, p.name AS payer
        FROM Expense e
        JOIN Member m ON m.id = e.payerMemberId
        JOIN Person p ON p.id = m.personId
        WHERE e.groupId = ?
        ORDER BY e.date, e.id
        """,
        [group_id],
    ).fetchall()
    return [dict(row) for row in rows]


def list_participants(conn, group_id):
    """Renvoie les participants de toutes les dépenses du groupe, dans leur ordre d'ajout."""
    rows = conn.execute(
        """
        SELECT ep.expenseId AS expense_id, m.id, p.name
        FROM ExpenseParticipant ep
        JOIN Expense e ON e.id = ep.expenseId
        JOIN Member m ON m.id = ep.memberId
        JOIN Person p ON p.id = m.personId
        WHERE e.groupId = ?
        ORDER BY ep.expenseId, ep.position
        """,
        [group_id],
    ).fetchall()
    return [dict(row) for row in rows]


def insert_expense(conn, group_id, label, amount_cents, date, payer_id):
    return conn.execute(
        """
        INSERT INTO Expense (groupId, label, amountCents, date, payerMemberId)
        VALUES (?, ?, ?, ?, ?)
        """,
        [group_id, label, amount_cents, date, payer_id],
    ).lastrowid


def insert_participant(conn, expense_id, member_id, position):
    conn.execute(
        "INSERT INTO ExpenseParticipant (expenseId, memberId, position) VALUES (?, ?, ?)",
        [expense_id, member_id, position],
    )


def delete_expense(conn, group_id, expense_id):
    """Renvoie False si la dépense n'existe pas dans ce groupe."""
    found = conn.execute(
        "SELECT 1 FROM Expense WHERE id = ? AND groupId = ?", [expense_id, group_id]
    ).fetchone()
    if found is None:
        return False
    # Les participants sont supprimés d'abord, sans dépendre d'un ON DELETE CASCADE du schéma.
    conn.execute("DELETE FROM ExpenseParticipant WHERE expenseId = ?", [expense_id])
    conn.execute("DELETE FROM Expense WHERE id = ?", [expense_id])
    return True
