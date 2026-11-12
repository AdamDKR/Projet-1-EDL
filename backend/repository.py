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


def find_person_by_name(conn, name):
    row = conn.execute(
        "SELECT id, name, password_hash FROM Person WHERE lower(name) = lower(?) ORDER BY id LIMIT 1",
        [name],
    ).fetchone()
    return dict(row) if row is not None else None


def list_persons(conn):
    rows = conn.execute("SELECT id, name FROM Person ORDER BY name, id").fetchall()
    return [dict(row) for row in rows]


def get_person(conn, person_id):
    row = conn.execute("SELECT id, name FROM Person WHERE id = ?", [person_id]).fetchone()
    return dict(row) if row is not None else None


def is_person_in_group(conn, person_id, group_id):
    row = conn.execute(
        "SELECT 1 FROM Member WHERE person_id = ? AND group_id = ?",
        [person_id, group_id],
    ).fetchone()
    return row is not None


def list_groups_for_person(conn, person_id):
    rows = conn.execute(
        """
        SELECT g.id, g.name, g.start_date, g.end_date
        FROM "Group" g
        JOIN Member m ON m.group_id = g.id
        WHERE m.person_id = ?
        ORDER BY g.start_date, g.id
        """,
        [person_id],
    ).fetchall()
    return [dict(row) for row in rows]


def list_person_memberships(conn, person_id):
    rows = conn.execute(
        """
        SELECT m.id AS member_id, m.group_id, g.name AS group_name, g.start_date, g.end_date
        FROM Member m
        JOIN "Group" g ON g.id = m.group_id
        WHERE m.person_id = ?
        ORDER BY g.start_date, g.id
        """,
        [person_id],
    ).fetchall()
    return [dict(row) for row in rows]


def insert_person(conn, name, password_hash=None):
    return conn.execute(
        "INSERT INTO Person (name, password_hash) VALUES (?, ?)",
        [name, password_hash],
    ).lastrowid


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


def insert_refund(conn, group_id, from_member_id, to_member_id, amount_cents, date):
    return conn.execute(
        """
        INSERT INTO Refund (group_id, from_member_id, to_member_id, amount_cents, date)
        VALUES (?, ?, ?, ?, ?)
        """,
        [group_id, from_member_id, to_member_id, amount_cents, date],
    ).lastrowid


def list_refunds(conn, group_id):
    rows = conn.execute(
        """
        SELECT r.id, r.amount_cents, r.date,
               r.from_member_id AS payer_id, payer.name AS payer,
               r.to_member_id AS reimbursed_id, reimbursed.name AS reimbursed
        FROM Refund r
        JOIN Member mf ON mf.id = r.from_member_id
        JOIN Person payer ON payer.id = mf.person_id
        JOIN Member mt ON mt.id = r.to_member_id
        JOIN Person reimbursed ON reimbursed.id = mt.person_id
        WHERE r.group_id = ?
        ORDER BY r.date, r.id
        """,
        [group_id],
    ).fetchall()
    return [dict(row) for row in rows]


def delete_expense(conn, group_id, expense_id):
    """Renvoie False si la dépense n'existe pas dans ce groupe."""
    # Les participants partent en cascade : le schéma interdit de retirer le dernier à la main.
    cursor = conn.execute(
        "DELETE FROM Expense WHERE id = ? AND group_id = ?", [expense_id, group_id]
    )
    return cursor.rowcount > 0
