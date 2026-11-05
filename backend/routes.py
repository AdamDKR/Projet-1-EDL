"""Routes JSON utilisées par le frontend. Détail des routes : docs/API.md."""
import sqlite3

from flask import Blueprint, jsonify, request

import services
from database import transaction

api = Blueprint("api", __name__, url_prefix="/api")


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise services.ValidationError("The request body must be a JSON object.")
    return data


@api.errorhandler(services.ValidationError)
def handle_validation_error(error):
    return jsonify(error=str(error)), 400


@api.errorhandler(services.NotFoundError)
def handle_not_found(error):
    return jsonify(error=str(error)), 404


# Filet de sécurité si une contrainte du schéma refuse une donnée acceptée par services.py.
@api.errorhandler(sqlite3.IntegrityError)
def handle_integrity_error(error):
    return jsonify(error="The database rejected this data."), 400


@api.get("/groups")
def list_groups():
    with transaction() as conn:
        return jsonify(services.list_groups(conn))


@api.post("/groups")
def create_group():
    data = json_body()
    with transaction() as conn:
        return jsonify(services.create_group(conn, data)), 201


@api.get("/groups/<int:group_id>")
def get_group(group_id):
    with transaction() as conn:
        return jsonify(services.get_group(conn, group_id))


@api.post("/groups/<int:group_id>/members")
def add_member(group_id):
    data = json_body()
    with transaction() as conn:
        return jsonify(services.add_member(conn, group_id, data)), 201


@api.get("/groups/<int:group_id>/expenses")
def list_expenses(group_id):
    with transaction() as conn:
        return jsonify(services.list_expenses(conn, group_id))


@api.post("/groups/<int:group_id>/expenses")
def add_expense(group_id):
    data = json_body()
    with transaction() as conn:
        return jsonify(services.add_expense(conn, group_id, data)), 201


@api.delete("/groups/<int:group_id>/expenses/<int:expense_id>")
def delete_expense(group_id, expense_id):
    with transaction() as conn:
        services.delete_expense(conn, group_id, expense_id)
    return "", 204


@api.get("/groups/<int:group_id>/balances")
def get_balances(group_id):
    with transaction() as conn:
        return jsonify(services.get_balances(conn, group_id))


@api.get("/accounts")
def list_accounts():
    with transaction() as conn:
        return jsonify(services.list_accounts(conn))


@api.post("/accounts")
def create_account():
    data = json_body()
    with transaction() as conn:
        return jsonify(services.create_account(conn, data)), 201


@api.post("/login")
def login():
    data = json_body()
    with transaction() as conn:
        return jsonify(services.authenticate_user(conn, data.get("name"), data.get("password"))), 200
