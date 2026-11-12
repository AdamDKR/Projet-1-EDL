# Expense sharing API

## Running the application

From the repository root, on Windows (PowerShell):

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process RemoteSigned
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python backend/app.py
```

Then open <http://127.0.0.1:5000>. Run the tests with `pytest`.

Flask also serves the `frontend/` folder: `/` returns `frontend/index.html`, and a file such as `frontend/style.css` is available at `/style.css`.

## Routes

All routes start with `/api`. Requests and responses use JSON, so send the `Content-Type: application/json` header.

| Method | URL | Purpose | Success |
|---|---|---|---|
| GET | `/api/groups` | List groups | 200 |
| POST | `/api/groups` | Create a group and its members | 201 |
| GET | `/api/groups/<id>` | Read a group and its members | 200 |
| POST | `/api/groups/<id>/members` | Add a member | 201 |
| GET | `/api/groups/<id>/expenses` | List expenses | 200 |
| POST | `/api/groups/<id>/expenses` | Add an expense | 201 |
| DELETE | `/api/groups/<id>/expenses/<expense_id>` | Delete an expense | 204, no content |
| GET | `/api/groups/<id>/balances` | Get member balances | 200 |
| GET | `/api/groups/<id>/settlements` | Get suggested settlements | 200 |
| POST | `/api/groups/<id>/reimbursements` | Record a reimbursement between members | 201 |
| GET | `/api/accounts` | List user accounts and global balances | 200 |
| POST | `/api/accounts` | Create a user account | 201 |

## Errors

Errors return a message you can display as is:

```json
{ "error": "The expense date must be within the stay." }
```

- **400**: the data was rejected and nothing was saved.
- **404**: the group or expense does not exist.

## Create a group

`POST /api/groups`. The `members` field is optional.

```json
{
  "name": "Trip to Spa",
  "start_date": "2026-07-01",
  "end_date": "2026-07-08",
  "members": ["Alice", "Bob", "Chloé"]
}
```

The response has the same format as `GET /api/groups/<id>`:

```json
{
  "id": 2,
  "name": "Trip to Spa",
  "start_date": "2026-07-01",
  "end_date": "2026-07-08",
  "members": [
    { "id": 4, "person_id": 1, "name": "Alice" },
    { "id": 5, "person_id": 2, "name": "Bob" },
    { "id": 6, "person_id": 3, "name": "Chloé" }
  ]
}
```

`GET /api/groups` returns a list of groups without their members.

## Add a member

`POST /api/groups/<id>/members` with `{ "name": "David" }`. The response is `{ "id": 7, "person_id": 4, "name": "David" }`.

Use the member `id` in expenses, not `person_id`. A name can only appear once in a group, ignoring case. If a person with exactly the same name already exists in another group, they are reused.

## Add an expense

`POST /api/groups/<id>/expenses`

```json
{
  "label": "Groceries",
  "amount": "30.00",
  "date": "2026-07-02",
  "payer_id": 4,
  "participants": [4, 5, 6]
}
```

- `amount` is in **euros**, with at most 2 decimals. Send the text as typed: both `"12.50"` and `"12,50"` work, and the backend converts it to cents.
- `date` uses the `YYYY-MM-DD` format, which is what `<input type="date">` provides.
- `payer_id` and `participants` contain member ids as **numbers**, not text. Convert a value read from a `<select>` with `Number(...)`.
- **The order of `participants` matters**: remaining cents are handed out one at a time, following the list. With 2 remaining cents, the first and second participants each get one. Send members in the order the user added them.

The response has the same format as one item of the list below.

## List expenses

`GET /api/groups/<id>/expenses` returns expenses sorted by date:

```json
[
  {
    "id": 2,
    "label": "Groceries",
    "amount": "30.00",
    "amount_cents": 3000,
    "date": "2026-07-02",
    "payer_id": 4,
    "payer": "Alice",
    "participants": [
      { "id": 4, "name": "Alice" },
      { "id": 5, "name": "Bob" },
      { "id": 6, "name": "Chloé" }
    ]
  }
]
```

## Get balances

`GET /api/groups/<id>/balances`

```json
[
  { "member_id": 4, "name": "Alice", "balance": "+20.00", "balance_cents": 2000 },
  { "member_id": 5, "name": "Bob", "balance": "-10.00", "balance_cents": -1000 },
  { "member_id": 6, "name": "Chloé", "balance": "-10.00", "balance_cents": -1000 }
]
```

Display `balance`, which is already formatted. Reload the balances after adding or deleting an expense: the backend computes them on each call.

## Reimbursements between members

`POST /api/groups/<id>/reimbursements`

```json
{
  "from_member_id": 5,
  "to_member_id": 4,
  "amount": "10.00",
  "date": "2026-07-02"
}
```

- `from_member_id` (the member paying back) and `to_member_id` (the recipient) must be distinct member IDs belonging to the group.
- `date` and `label` are optional (defaulting to a valid date within the stay and `"Remboursement (Payeur → Bénéficiaire)"`).

## `fetch` example

```js
const response = await fetch(`/api/groups/${groupId}/expenses`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    label: "Groceries",
    amount: "30.00",
    date: "2026-07-02",
    payer_id: 4,
    participants: [4, 5, 6],
  }),
});

if (!response.ok) {
  const { error } = await response.json();
  alert(error);
}
```
