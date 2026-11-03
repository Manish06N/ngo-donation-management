# NGO Donation, Volunteer & Community Project Management

Backend for an NGO that records donors and donations, runs fundraising campaigns, assigns volunteers, approves community projects, and tracks expenses, stock, beneficiaries, and impact.

The API is FastAPI. Business rules live in `app/services` and `app/domain`. A route does not decide whether a campaign can take money or whether a project can go live. PostgreSQL is the server database. Tests and a laptop without Docker use SQLite through the same models.

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Roles

| Role | What they can do |
| --- | --- |
| Super Admin | Everything, including creating staff and activating accounts |
| NGO Manager | Donors, campaigns, donations, projects, approvals, impact |
| Finance Officer | Confirm donations, issue receipts, approve expenses, read budgets |
| Volunteer Coordinator | Volunteers, assignments, tasks, stock, beneficiaries |
| Volunteer | Own profile, assigned projects, own tasks, assistance on those projects |
| Donor | Own profile, public campaign list, own donations and receipts |

Public registration can open only a donor or volunteer account. Staff accounts are created by an administrator. A person cannot approve their own expense unless they are the super admin. Finance users see a beneficiary's name and category, not their address or phone.

## Run it on your machine

```bash
cd ngo-management-system
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Open `/docs`. Log in with the admin in `.env`:

- email: `admin@ngo.local`
- password: `Admin@12345`

Those values are for a local demo. Change `SECRET_KEY` and `ADMIN_PASSWORD` before any shared deployment. The application reads them from the environment. It does not contain a production password.

With `DEBUG=true`, `POST /api/v1/auth/forgot-password` includes the reset token in the JSON so you can finish the flow without an email server. Turn debug off and that field stays empty.

## Run it with PostgreSQL

```bash
docker compose up --build
```

API: [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)

Postgres is published on port `5433` so it does not collide with another local database. The container runs `alembic upgrade head` before Uvicorn, then seeds the admin user.

## Tests

```bash
pytest -q
```

The suite covers login and permissions, donation totals, duplicate receipts, the project approval gate, assignment conflicts, expense approval and budget limits, stock that cannot go negative, dashboard totals, CSV export, and the full demonstration path in `tests/integration/test_e2e.py`.

Against a running server:

```bash
python scripts/e2e_demo.py
```

Use `BASE_URL=http://127.0.0.1:8010` if you started Docker.

## How a request is handled

1. The route checks the access token and calls a service.
2. The service checks the role, then the status map, then the numbers.
3. Services call `flush()` so new ids exist. They do not call `commit()`.
4. `get_db` commits if the service returned, and rolls back if it raised.

A confirmed donation, the campaign total, the audit row, and a voided receipt therefore land together or not at all. The same is true for a stock allocation made while recording beneficiary assistance.

## Rules worth knowing

- A donation amount must be positive. Reference numbers are unique and compared in uppercase.
- Only an **active** campaign accepts a new donation or a confirmation. Draft, paused, completed, and cancelled campaigns refuse it.
- The campaign total increases when a donation is confirmed and decreases when that donation is reversed or refunded.
- A receipt is issued once, and only for a confirmed donation. Refund or reversal marks it void. A second receipt is refused.
- A project is created in **planning**. It becomes **approved** only through the approval decision. Activation is refused before that.
- A rejection needs a comment. Completing a project is refused while a milestone is still open.
- Only an **active** volunteer can be assigned. Overlapping open assignments for the same person are refused.
- An expense starts as **submitted**. Approval is refused when it would exceed the project budget, or the campaign budget when the expense is linked to a campaign. Approved and reimbursed amounts are what "spent" means.
- Stock-in, stock-out, and allocation each write a movement row. The quantity on hand cannot go below zero. Opening stock is a stock-in movement.
- Dashboard figures are `COUNT` and `SUM` queries. They are not stored constants.

Status maps are in `app/domain/transitions.py`.

## API map

| Area | Method and path |
| --- | --- |
| Auth | `POST /api/v1/auth/register`, `/login`, `/token`, `/refresh`, `/logout`, `/forgot-password`, `/reset-password`, `GET/PATCH /auth/me` |
| Accounts | `GET/POST /api/v1/users`, `PATCH /api/v1/users/{id}/activation` |
| Donors | `POST/GET /api/v1/donors`, `GET /donors/me`, `GET/PATCH /donors/{id}`, `GET /donors/{id}/donations`, `GET /donors/{id}/receipts` |
| Campaigns | `POST/GET /api/v1/campaigns`, `GET/PATCH /campaigns/{id}`, `POST /campaigns/{id}/status` |
| Donations | `POST/GET /api/v1/donations`, `POST /donations/{id}/status`, `POST /donations/{id}/receipt` |
| Receipts | `GET /api/v1/receipts/{id}`, `GET /receipts/{id}/pdf` |
| Volunteers | `POST/GET /api/v1/volunteers`, `GET /volunteers/me`, `GET/PATCH /volunteers/{id}` |
| Assignments | `POST/GET /api/v1/assignments`, `PATCH /assignments/{id}`, attendance under that id |
| Projects | `POST/GET /api/v1/projects`, `POST /projects/{id}/submit`, `/decision`, `/status`, milestones, impact |
| Tasks | `GET /api/v1/tasks?overdue=true`, `PATCH /api/v1/tasks/{id}` |
| Expenses | `POST/GET /api/v1/expenses`, `POST /expenses/{id}/decision` |
| Budgets | `GET /api/v1/budgets/projects/{id}`, `/budgets/campaigns/{id}`, `/budgets/utilization` |
| Resources | `POST/GET /api/v1/resources`, `POST /resources/{id}/movements` |
| Beneficiaries | `POST/GET /api/v1/beneficiaries`, `POST /beneficiaries/{id}/assistance` |
| Dashboard | `GET /api/v1/dashboard` |
| Notifications | `GET /api/v1/notifications`, `POST /notifications/scan`, `POST /notifications/{id}/read` |
| Reports | `GET /api/v1/reports/donations?format=csv` and the same shape for campaigns, volunteers, projects, expenses, resources, beneficiaries |
| Audit | `GET /api/v1/audit-logs` |

List endpoints take `page`, `page_size` (max 100), `sort_by`, and `sort_dir`. Reports also filter by date, campaign, project, and status. `format=csv` returns the same page as a spreadsheet. Cells that start with `=`, `+`, `-`, or `@` are prefixed so a spreadsheet does not treat them as formulas.

Import `postman/ngo-management.postman_collection.json` and set `base_url` to `http://127.0.0.1:8000` or `http://127.0.0.1:8010`.

## Layout

```
app/
  api/            HTTP routes, grouped by area
  core/           settings, passwords, tokens, error JSON
  domain/         roles, status maps, money and stock rules
  models/         tables and relationships
  schemas/        request and response models
  services/       workflows
  repositories/   shared queries, paging, record numbers
  db/             engine, session, first-admin seed
  main.py
alembic/          schema migration
tests/unit        rules with no database
tests/integration API flows, including the full demonstration
```

The entity diagram is in [docs/er-diagram.md](docs/er-diagram.md).
