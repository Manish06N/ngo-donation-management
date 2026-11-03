from datetime import date, timedelta
from decimal import Decimal

from tests.conftest import make_user
from app.domain.enums import Role


def _approve_project(client, headers, manager_id, budget="100.00"):
    today = date.today()
    project = client.post(
        "/api/v1/projects",
        json={
            "title": "Clinic day",
            "objectives": "Run a clinic",
            "location": "Gaya",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=20)).isoformat(),
            "budget_amount": budget,
            "manager_id": manager_id,
        },
        headers=headers,
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    client.post(f"/api/v1/projects/{project_id}/submit", json={"comments": "submit"}, headers=headers)
    client.post(f"/api/v1/projects/{project_id}/decision", json={"decision": "approved", "comments": "ok"}, headers=headers)
    client.post(f"/api/v1/projects/{project_id}/status", json={"status": "active"}, headers=headers)
    return project_id


def test_expense_approval_budget_and_separation(client, session, admin, admin_headers):
    finance = make_user(session, "finance@ngo.local", Role.FINANCE_OFFICER, "Password1")
    finance_headers = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/login", json={"email": finance.email, "password": "Password1"}).json()["access_token"]
    }
    project_id = _approve_project(client, admin_headers, admin.id, "100.00")
    expense = client.post(
        "/api/v1/expenses",
        json={
            "project_id": project_id,
            "category": "medical",
            "amount": "40.00",
            "expense_date": date.today().isoformat(),
            "description": "Medicines",
            "receipt_reference": "BILL-1",
        },
        headers=finance_headers,
    )
    assert expense.status_code == 201, expense.text
    own = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/decision",
        json={"status": "approved", "comments": "ok"},
        headers=finance_headers,
    )
    assert own.status_code == 403
    assert own.json()["code"] == "separation_of_duties"
    volunteer = make_user(session, "helper2@ngo.local", Role.VOLUNTEER)
    volunteer_headers = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/login", json={"email": volunteer.email, "password": "Password1"}).json()["access_token"]
    }
    denied = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/decision",
        json={"status": "approved"},
        headers=volunteer_headers,
    )
    assert denied.status_code == 403

    approved = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/decision",
        json={"status": "approved", "comments": "Within budget"},
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    budget = client.get(f"/api/v1/budgets/projects/{project_id}", headers=finance_headers)
    assert budget.status_code == 200, budget.text
    assert Decimal(str(budget.json()["spent_amount"])) == Decimal("40.00")
    assert Decimal(str(budget.json()["remaining_amount"])) == Decimal("60.00")
    assert budget.json()["overrun"] is False

    too_big = client.post(
        "/api/v1/expenses",
        json={
            "project_id": project_id,
            "category": "travel",
            "amount": "80.00",
            "expense_date": date.today().isoformat(),
            "description": "Van hire",
        },
        headers=admin_headers,
    )
    assert too_big.status_code == 201, too_big.text
    overflow = client.post(
        f"/api/v1/expenses/{too_big.json()['id']}/decision",
        json={"status": "approved", "comments": "no"},
        headers=finance_headers,
    )
    assert overflow.status_code == 409
    assert overflow.json()["code"] == "budget_exceeded"


def test_resource_stock_and_beneficiary_masking(client, session, admin, admin_headers):
    project_id = _approve_project(client, admin_headers, admin.id, "1000.00")
    resource = client.post(
        "/api/v1/resources",
        json={
            "name": "Rice bag",
            "category": "food_packages",
            "unit": "bag",
            "quantity_on_hand": 5,
            "reorder_level": 2,
        },
        headers=admin_headers,
    )
    assert resource.status_code == 201, resource.text
    history = client.get(f"/api/v1/resources/{resource.json()['id']}/movements", headers=admin_headers)
    assert history.json()[0]["movement_type"] == "stock_in"
    assert history.json()[0]["balance_after"] == 5

    too_many = client.post(
        f"/api/v1/resources/{resource.json()['id']}/movements",
        json={"movement_type": "stock_out", "quantity": 9},
        headers=admin_headers,
    )
    assert too_many.status_code == 409
    assert too_many.json()["code"] == "insufficient_stock"

    finance = make_user(session, "books@ngo.local", Role.FINANCE_OFFICER)
    finance_headers = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/login", json={"email": finance.email, "password": "Password1"}).json()["access_token"]
    }
    beneficiary = client.post(
        "/api/v1/beneficiaries",
        json={
            "full_name": "Ravi Kumar",
            "category": "adult",
            "contact": "9000011111",
            "address": "Lane 4, Patna",
            "project_ids": [project_id],
        },
        headers=admin_headers,
    )
    assert beneficiary.status_code == 201, beneficiary.text
    assert beneficiary.json()["address"] == "Lane 4, Patna"
    masked = client.get(f"/api/v1/beneficiaries/{beneficiary.json()['id']}", headers=finance_headers)
    assert masked.status_code == 200, masked.text
    assert masked.json()["full_name"] == "Ravi Kumar"
    assert masked.json()["address"] is None
    assert masked.json()["contact"] is None

    assistance = client.post(
        f"/api/v1/beneficiaries/{beneficiary.json()['id']}/assistance",
        json={
            "project_id": project_id,
            "assistance_type": "food",
            "description": "Monthly ration",
            "quantity": 2,
            "distribution_date": date.today().isoformat(),
            "resource_id": resource.json()["id"],
        },
        headers=admin_headers,
    )
    assert assistance.status_code == 201, assistance.text
    stock = client.get(f"/api/v1/resources/{resource.json()['id']}", headers=admin_headers).json()
    assert stock["quantity_on_hand"] == 3
    movements = client.get(f"/api/v1/resources/{resource.json()['id']}/movements", headers=admin_headers).json()
    assert any(item["movement_type"] == "allocation" for item in movements)
