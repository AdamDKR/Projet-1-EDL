import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

import database
import repository
import services
from app import app


@pytest.fixture
def client():
    return app.test_client()


def new_group(client, members=("Alice", "Bob", "Chloé"), name="Test"):
    """Un nouveau groupe, du 1er au 8 juillet 2026."""
    return client.post(
        "/api/groups",
        json={
            "name": name,
            "start_date": "2026-07-01",
            "end_date": "2026-07-08",
            "members": list(members),
        },
    ).get_json()


@pytest.fixture
def group(client):
    return new_group(client)


def ids(group):
    return [member["id"] for member in group["members"]]


def add(client, group, **changes):
    alice, bob, chloe = ids(group)[:3]
    body = {
        "label": "Groceries",
        "amount": "30",
        "date": "2026-07-02",
        "payer_id": alice,
        "participants": [alice, bob, chloe],
        **changes,
    }
    return client.post(f"/api/groups/{group['id']}/expenses", json=body)


def balances(client, group):
    response = client.get(f"/api/groups/{group['id']}/balances").get_json()
    return [line["balance"] for line in response]


# --- Le tableau « Pour vérifier » du sujet, lignes enchaînées ---


def test_assignment_checks(client, group):
    assert add(client, group).status_code == 201
    assert balances(client, group) == ["+20.00", "-10.00", "-10.00"]

    assert add(client, group, date="2026-07-09").status_code == 400
    assert balances(client, group) == ["+20.00", "-10.00", "-10.00"]

    assert add(client, group, amount=0).status_code == 400
    assert balances(client, group) == ["+20.00", "-10.00", "-10.00"]

    other = new_group(client, name="New")
    assert add(client, other, amount=10).status_code == 201
    assert balances(client, other) == ["+6.66", "-3.33", "-3.33"]


# --- Règles sur les dépenses ---


@pytest.mark.parametrize("expense_date", ["2026-07-01", "2026-07-08"])
def test_stay_boundaries_are_included(client, group, expense_date):
    assert add(client, group, date=expense_date).status_code == 201


@pytest.mark.parametrize(
    "expense_date", ["2026-06-30", "2026-07-09", "2026-02-30", "20260702", "tomorrow", None]
)
def test_invalid_date_is_rejected(client, group, expense_date):
    assert add(client, group, date=expense_date).status_code == 400


@pytest.mark.parametrize("amount", [0, "0,00", -5, "-5", "abc", "1,234", True, None, [], "1e5"])
def test_invalid_amount_is_rejected(client, group, amount):
    assert add(client, group, amount=amount).status_code == 400
    assert balances(client, group) == ["0.00", "0.00", "0.00"]


@pytest.mark.parametrize("participants", [[], None, "1", ["1"], [True], [9999]])
def test_invalid_participants_are_rejected(client, group, participants):
    assert add(client, group, participants=participants).status_code == 400


def test_duplicate_participant_is_rejected(client, group):
    alice = ids(group)[0]
    assert add(client, group, participants=[alice, alice]).status_code == 400


def test_members_of_another_group_are_rejected(client, group):
    zoe = ids(new_group(client, members=["Zoé"], name="Other"))[0]
    assert add(client, group, payer_id=zoe).status_code == 400
    assert add(client, group, participants=[ids(group)[0], zoe]).status_code == 400
    assert client.get(f"/api/groups/{group['id']}/expenses").get_json() == []


def test_remaining_cent_goes_to_first_added_participant(client, group):
    alice, bob, chloe = ids(group)
    # Bob est ajouté en premier, alors que son id est plus grand que celui d'Alice.
    response = add(client, group, amount=10, payer_id=chloe, participants=[bob, alice, chloe])
    assert [p["id"] for p in response.get_json()["participants"]] == [bob, alice, chloe]
    assert balances(client, group) == ["-3.33", "-3.34", "+6.67"]


def test_two_remaining_cents_go_to_first_two_added(client, group):
    alice, bob, chloe = ids(group)
    # 10,01 € / 3 = 3,33 € et 2 centimes restants, pour Chloé puis Bob.
    add(client, group, amount="10,01", payer_id=alice, participants=[chloe, bob, alice])
    assert balances(client, group) == ["+6.68", "-3.34", "-3.34"]


def test_payer_does_not_have_to_participate(client, group):
    alice, bob, chloe = ids(group)
    add(client, group, payer_id=alice, participants=[bob, chloe])
    assert balances(client, group) == ["+30.00", "-15.00", "-15.00"]


def test_expense_response_format(client, group):
    alice = ids(group)[0]
    expense = add(client, group, amount="12,5", participants=[alice]).get_json()
    assert expense["amount"] == "12.50"
    assert expense["amount_cents"] == 1250
    assert expense["payer"] == "Alice"
    assert expense["participants"] == [{"id": alice, "name": "Alice"}]


def test_delete_restores_balances(client, group):
    expense_id = add(client, group).get_json()["id"]
    url = f"/api/groups/{group['id']}/expenses/{expense_id}"
    assert client.delete(url).status_code == 204
    assert balances(client, group) == ["0.00", "0.00", "0.00"]
    assert client.delete(url).status_code == 404


def test_delete_is_limited_to_the_group(client, group):
    other = new_group(client, name="Other")
    expense_id = add(client, group).get_json()["id"]
    assert client.delete(f"/api/groups/{other['id']}/expenses/{expense_id}").status_code == 404
    assert balances(client, group) == ["+20.00", "-10.00", "-10.00"]


# --- Groupes et membres ---


def test_create_and_read_group(client, group):
    read = client.get(f"/api/groups/{group['id']}").get_json()
    assert read == group
    assert [member["name"] for member in read["members"]] == ["Alice", "Bob", "Chloé"]
    assert group["id"] in [g["id"] for g in client.get("/api/groups").get_json()]


def test_add_member(client, group):
    url = f"/api/groups/{group['id']}/members"
    assert client.post(url, json={"name": "David"}).status_code == 201
    assert client.post(url, json={"name": " david "}).status_code == 400
    assert client.post(url, json={"name": "  "}).status_code == 400
    assert len(balances(client, group)) == 4


def test_same_person_can_join_several_groups(client):
    first = new_group(client, members=["Alice"], name="First")["members"][0]
    second = new_group(client, members=["Alice"], name="Second")["members"][0]
    assert first["person_id"] == second["person_id"]
    assert first["id"] != second["id"]


def test_member_and_person_ids_are_not_confused(client):
    # Alice est la personne 2 mais le membre 3 : l'API doit toujours exposer l'id de membre.
    new_group(client, members=["Zoé", "Alice"], name="First")
    second = new_group(client, members=["Alice", "Bob"], name="Second")
    alice, bob = second["members"]
    assert alice["id"] != alice["person_id"]

    url = f"/api/groups/{second['id']}/expenses"
    body = {
        "label": "Taxi",
        "amount": "10",
        "date": "2026-07-02",
        "payer_id": alice["id"],
        "participants": [alice["id"], bob["id"]],
    }
    expense = client.post(url, json=body).get_json()
    assert expense["payer_id"] == alice["id"]
    assert expense["payer"] == "Alice"
    assert balances(client, second) == ["+5.00", "-5.00"]


def test_person_id_is_not_accepted_as_payer(client):
    new_group(client, members=["Zoé", "Alice"], name="First")
    second = new_group(client, members=["Alice", "Bob"], name="Second")
    alice, bob = second["members"]
    # Le numéro de personne d'Alice ne correspond à aucun membre de ce groupe.
    assert alice["person_id"] not in [alice["id"], bob["id"]]
    url = f"/api/groups/{second['id']}/expenses"
    body = {
        "label": "Taxi",
        "amount": "10",
        "date": "2026-07-02",
        "payer_id": alice["person_id"],
        "participants": [alice["id"]],
    }
    assert client.post(url, json=body).status_code == 400


def test_delete_expense_with_a_single_participant(client, group):
    # Le schéma interdit de retirer le dernier participant, sauf par cascade.
    alice = ids(group)[0]
    expense_id = add(client, group, participants=[alice]).get_json()["id"]
    url = f"/api/groups/{group['id']}/expenses/{expense_id}"
    assert client.delete(url).status_code == 204
    assert client.get(f"/api/groups/{group['id']}/expenses").get_json() == []


def test_schema_rejects_expense_outside_the_stay(group):
    # Double sécurité : même sans services.py, le trigger du schéma refuse la dépense.
    person_id = group["members"][0]["person_id"]
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as conn:
            repository.insert_expense(conn, group["id"], "Late", 100, "2026-07-09", person_id)


@pytest.mark.parametrize("amount_cents", [10.5, "abc"])
def test_schema_rejects_non_integer_amount(group, amount_cents):
    person_id = group["members"][0]["person_id"]
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as conn:
            repository.insert_expense(
                conn, group["id"], "Odd", amount_cents, "2026-07-02", person_id
            )


@pytest.mark.parametrize("amount", ["10.00", "10.01", "10.02", "0.01", "0.02"])
def test_sql_views_match_backend_balances(client, group, amount):
    # L'ordre d'ajout (Chloé, Alice, Bob) diffère volontairement de l'ordre des id.
    alice, bob, chloe = ids(group)
    add(client, group, amount=amount, payer_id=bob, participants=[chloe, alice, bob])
    response = client.get(f"/api/groups/{group['id']}/balances").get_json()
    backend = [line["balance_cents"] for line in response]
    with database.transaction() as conn:
        rows = conn.execute(
            "SELECT balance_cents FROM v_balance WHERE group_id = ? ORDER BY member_id",
            [group["id"]],
        ).fetchall()
    assert [row["balance_cents"] for row in rows] == backend
    assert sum(backend) == 0


def test_simultaneous_first_requests_share_one_database():
    def first_request(_):
        return app.test_client().get("/api/groups").status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert list(executor.map(first_request, range(8))) == [200] * 8


def test_balances_are_separate_between_groups(client):
    first = new_group(client, name="First")
    second = new_group(client, name="Second")
    add(client, first)
    assert balances(client, first) == ["+20.00", "-10.00", "-10.00"]
    assert balances(client, second) == ["0.00", "0.00", "0.00"]


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"start_date": "2026-07-09"},
        {"end_date": "not a date"},
        {"members": "Alice"},
        {"members": ["Alice", "alice"]},
        {"members": [1]},
    ],
)
def test_rejected_group_saves_nothing(client, changes):
    before = client.get("/api/groups").get_json()
    body = {"name": "X", "start_date": "2026-07-01", "end_date": "2026-07-08", **changes}
    assert client.post("/api/groups", json=body).status_code == 400
    assert client.get("/api/groups").get_json() == before


def test_unknown_group(client):
    assert client.get("/api/groups/9999").status_code == 404
    assert client.get("/api/groups/9999/balances").status_code == 404
    assert client.get("/api/groups/9999/expenses").status_code == 404
    assert client.post("/api/groups/9999/members", json={"name": "A"}).status_code == 404
    assert client.post("/api/groups/9999/expenses", json={}).status_code == 404


def test_non_json_body(client):
    response = client.post("/api/groups", data="name=X")
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_database_constraint_returns_an_error_message(client, group, monkeypatch):
    def rejected(*args):
        raise sqlite3.IntegrityError("constraint failed")

    monkeypatch.setattr(services.repository, "insert_expense", rejected)
    response = add(client, group)
    assert response.status_code == 400
    assert "error" in response.get_json()


# --- Point d'entrée ---


def test_home_serves_the_frontend(client, tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<h1>Expense sharing</h1>", encoding="utf-8")
    monkeypatch.setattr(app, "static_folder", str(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    assert b"Expense sharing" in response.data
    response.close()


# --- Comptes utilisateurs & intégration Web ---


def test_create_and_list_accounts_api(client):
    res = client.post("/api/accounts", json={"name": "Martin"})
    assert res.status_code == 201
    account = res.get_json()
    assert account["name"] == "Martin"
    assert "id" in account

    # Duplicate account name rejected
    dup = client.post("/api/accounts", json={"name": "Martin"})
    assert dup.status_code == 400

    # Empty name rejected
    empty = client.post("/api/accounts", json={"name": "   "})
    assert empty.status_code == 400

    # List accounts
    listed = client.get("/api/accounts").get_json()
    assert any(a["name"] == "Martin" for a in listed)


def test_web_routes_and_account_creation_flow(client):
    # Home empty state
    res = client.get("/")
    assert res.status_code == 200
    assert "Bienvenue sur Partage de frais" in res.text

    # Seed sample data
    seed = client.post("/seed-sample-data", follow_redirects=True)
    assert seed.status_code == 200
    assert "Vacances à Spa" in seed.text
    assert "Alice" in seed.text
    assert "Courses" in seed.text

    # Accounts view
    acc_page = client.get("/accounts")
    assert acc_page.status_code == 200
    assert "Comptes Utilisateurs" in acc_page.text

    # Create account from web form
    new_acc = client.post("/accounts", data={"name": "Nicolas"}, follow_redirects=True)
    assert new_acc.status_code == 200
    assert "Nicolas" in new_acc.text

    # Add member from web form
    add_m = client.post("/groups/1/members", data={"name": "Nicolas"}, follow_redirects=True)
    assert add_m.status_code == 200
    assert "Nicolas" in add_m.text


def test_account_authentication_and_login(client):
    # Créer un compte avec mot de passe
    res = client.post(
        "/accounts",
        data={"name": "Sophie", "password": "mypassword"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "Sophie" in res.text

    # Se déconnecter
    logout = client.get("/logout", follow_redirects=True)
    assert logout.status_code == 200

    # Mauvais mot de passe
    bad_login = client.post(
        "/login",
        data={"name": "Sophie", "password": "wrong"},
        follow_redirects=True,
    )
    assert "Mot de passe incorrect" in bad_login.text

    # Bon mot de passe
    good_login = client.post(
        "/login",
        data={"name": "Sophie", "password": "mypassword"},
        follow_redirects=True,
    )
    assert good_login.status_code == 200
    assert "Bonjour Sophie" in good_login.text


def test_group_access_control_isolated_to_members(client):
    # Sophie crée son compte et son groupe
    client.post("/accounts", data={"name": "Sophie", "password": "123"})
    g_sophie = client.post(
        "/groups",
        data={
            "name": "Lisbonne",
            "start_date": "2026-07-01",
            "end_date": "2026-07-08",
            "members": "Marc",
        },
        follow_redirects=True,
    )
    assert "Lisbonne" in g_sophie.text

    # Sophie se déconnecte
    client.get("/logout")

    # Paul crée son compte et son groupe
    client.post("/accounts", data={"name": "Paul", "password": "456"})
    g_paul = client.post(
        "/groups",
        data={
            "name": "Bruges",
            "start_date": "2026-08-01",
            "end_date": "2026-08-05",
            "members": "",
        },
        follow_redirects=True,
    )
    assert "Bruges" in g_paul.text

    # Paul connecté ne voit QUE son groupe dans sa liste
    home_paul = client.get("/")
    assert "Bruges" in home_paul.text
    # Lisbonne ne doit pas apparaître dans les séjours de Paul
    assert "Lisbonne" not in home_paul.text

    # Paul essaie d'accéder au groupe de Sophie (id 1) -> Accès refusé
    forbidden_view = client.get("/?group_id=1", follow_redirects=True)
    assert "Accès refusé" in forbidden_view.text

    # Paul essaie d'ajouter une dépense au groupe de Sophie -> Refusé
    forbidden_expense = client.post(
        "/groups/1/expenses",
        data={
            "label": "Tapas",
            "amount": "20",
            "date": "2026-07-02",
            "payer_id": 1,
            "participants": [1],
        },
        follow_redirects=True,
    )
    assert "Accès refusé" in forbidden_expense.text




# --- Remboursements ---


def refund(client, group, **changes):
    alice, bob = ids(group)[:2]
    body = {"payer_id": bob, "reimbursed_id": alice, "amount": "10", "date": "2026-07-15", **changes}
    return client.post(f"/api/groups/{group['id']}/refund", json=body)


def test_refund_settles_a_debt(client, group):
    add(client, group)
    response = refund(client, group)
    assert response.status_code == 201
    assert response.get_json()["payer"] == "Bob"
    assert response.get_json()["reimbursed"] == "Alice"
    assert balances(client, group) == ["+10.00", "0.00", "-10.00"]


def test_refund_is_not_listed_as_an_expense(client, group):
    add(client, group)
    refund(client, group)
    assert len(client.get(f"/api/groups/{group['id']}/expenses").get_json()) == 1


@pytest.mark.parametrize("refund_date", ["2026-07-01", "2026-07-08", "2026-12-31"])
def test_refund_can_be_dated_after_the_stay(client, group, refund_date):
    assert refund(client, group, date=refund_date).status_code == 201


@pytest.mark.parametrize(
    "changes",
    [
        {"date": "2026-06-30"},
        {"date": "not a date"},
        {"amount": 0},
        {"amount": "-5"},
        {"payer_id": 9999},
        {"reimbursed_id": 9999},
        {"reimbursed_id": [1]},
        {"reimbursed_id": "1"},
        {"payer_id": None},
    ],
)
def test_invalid_refund_is_rejected(client, group, changes):
    assert refund(client, group, **changes).status_code == 400
    assert balances(client, group) == ["0.00", "0.00", "0.00"]


def test_member_cannot_refund_themselves(client, group):
    alice = ids(group)[0]
    assert refund(client, group, payer_id=alice, reimbursed_id=alice).status_code == 400


def test_refund_with_a_member_of_another_group_is_rejected(client, group):
    zoe = ids(new_group(client, members=["Zoé"], name="Other"))[0]
    assert refund(client, group, reimbursed_id=zoe).status_code == 400
    assert refund(client, group, payer_id=zoe).status_code == 400


def test_suggested_settlements_bring_balances_to_zero(client, group):
    alice, bob, chloe = ids(group)
    add(client, group, amount="10.01", participants=[chloe, bob, alice])
    with database.transaction() as conn:
        balances_by_id = {b["member_id"]: b["balance_cents"] for b in services.get_balances(conn, group["id"])}
        settlements = services.compute_settlements(balances_by_id, {m["id"]: m["name"] for m in group["members"]})
    names = {m["name"]: m["id"] for m in group["members"]}
    for s in settlements:
        assert refund(
            client, group,
            payer_id=names[s["debtor"]], reimbursed_id=names[s["creditor"]],
            amount=f"{s['amount_cents'] / 100:.2f}",
        ).status_code == 201
    assert balances(client, group) == ["0.00", "0.00", "0.00"]


def test_sql_views_include_refunds(client, group):
    add(client, group, amount="10.01")
    refund(client, group, amount="3.34")
    backend = [b["balance_cents"] for b in client.get(f"/api/groups/{group['id']}/balances").get_json()]
    with database.transaction() as conn:
        rows = conn.execute(
            "SELECT balance_cents FROM v_balance WHERE group_id = ? ORDER BY member_id", [group["id"]]
        ).fetchall()
    assert [row["balance_cents"] for row in rows] == backend
    assert sum(backend) == 0


def test_refund_form_on_the_web_page(client, group):
    alice, bob = ids(group)[:2]
    add(client, group)
    form = {"payer_id": str(bob), "reimbursed_id": str(alice), "amount": "10,00", "date": "2026-07-20"}
    response = client.post(f"/groups/{group['id']}/refunds", data=form)
    assert response.status_code == 302
    assert balances(client, group) == ["+10.00", "0.00", "-10.00"]

    page = client.get(f"/?group_id={group['id']}")
    assert page.status_code == 200
    assert "Ajouter un remboursement".encode() in page.data


def test_database_created_before_refunds_is_upgraded(client, group):
    # Simule un data.db créé avant l'ajout des remboursements, avec des données dedans.
    add(client, group)
    with database.transaction() as conn:
        conn.execute("DROP TABLE Refund")
    database._checked_databases.clear()

    assert client.get("/").status_code == 200
    assert balances(client, group) == ["+20.00", "-10.00", "-10.00"]
    assert refund(client, group).status_code == 201
    assert balances(client, group) == ["+10.00", "0.00", "-10.00"]
