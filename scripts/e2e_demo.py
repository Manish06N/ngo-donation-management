"""Walk the demonstration against a running API and print each result.

    uvicorn app.main:app --reload
    python scripts/e2e_demo.py

Docker publishes the API on port 8010:

    BASE_URL=http://127.0.0.1:8010 python scripts/e2e_demo.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@ngo.local")
PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")
TOKEN = ""


def call(method, path, body=None, expected=200):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read()
            status = response.status
            payload = json.loads(raw.decode() or "null")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        print(f"FAIL {method} {path} -> {exc.code} {raw}")
        sys.exit(1)
    if status != expected and not (expected == 200 and status == 201):
        print(f"FAIL {method} {path} -> {status} {payload}")
        sys.exit(1)
    print(f"OK   {method} {path} -> {status}")
    return payload


def main():
    global TOKEN
    today = date.today()
    later = (today + timedelta(days=40)).isoformat()
    logged = call("POST", "/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD})
    TOKEN = logged["access_token"]
    admin_id = logged["user"]["id"]
    print(f"     signed in as {logged['user']['email']} ({logged['user']['role']})")

    donor = call(
        "POST",
        "/api/v1/donors",
        {
            "donor_type": "organization",
            "name": "Demo Trust",
            "organization_name": "Demo Trust",
            "email": f"demo.trust.{today.strftime('%Y%m%d')}@example.com",
            "city": "Patna",
        },
        201,
    )
    campaign = call(
        "POST",
        "/api/v1/campaigns",
        {
            "title": "Demo relief drive",
            "description": "A scripted walk through the API",
            "goal_amount": "10000.00",
            "budget_amount": "4000.00",
            "start_date": today.isoformat(),
            "end_date": later,
            "category": "community",
            "manager_id": admin_id,
        },
        201,
    )
    call("POST", f"/api/v1/campaigns/{campaign['id']}/status", {"status": "active"})
    donation = call(
        "POST",
        "/api/v1/donations",
        {
            "donor_id": donor["id"],
            "campaign_id": campaign["id"],
            "amount": "750.00",
            "donation_date": today.isoformat(),
            "method": "upi",
            "reference_number": f"DEMO-{today.strftime('%Y%m%d')}-001",
        },
        201,
    )
    call("POST", f"/api/v1/donations/{donation['id']}/status", {"status": "confirmed"})
    receipt = call("POST", f"/api/v1/donations/{donation['id']}/receipt", None, 201)
    print(f"     receipt {receipt['receipt_number']}")

    volunteer = call(
        "POST",
        "/api/v1/volunteers",
        {
            "full_name": "Demo Volunteer",
            "email": f"demo.volunteer.{today.strftime('%Y%m%d')}@example.com",
            "skills": ["logistics"],
            "availability": "Weekends",
            "status": "active",
            "emergency_contact_name": "Kin",
            "emergency_contact_phone": "9000000000",
        },
        201,
    )
    project = call(
        "POST",
        "/api/v1/projects",
        {
            "title": "Demo community project",
            "objectives": "Show the approval gate",
            "location": "Patna",
            "start_date": today.isoformat(),
            "end_date": later,
            "budget_amount": "3000.00",
            "manager_id": admin_id,
        },
        201,
    )
    call("POST", f"/api/v1/projects/{project['id']}/submit", {"comments": "Ready for review"})
    call("POST", f"/api/v1/projects/{project['id']}/decision", {"decision": "approved", "comments": "Approved"})
    call("POST", f"/api/v1/projects/{project['id']}/status", {"status": "active"})
    assignment = call(
        "POST",
        "/api/v1/assignments",
        {
            "volunteer_id": volunteer["id"],
            "project_id": project["id"],
            "responsibility": "Distribution",
            "start_date": today.isoformat(),
            "end_date": later,
        },
        201,
    )
    call(
        "POST",
        f"/api/v1/assignments/{assignment['id']}/attendance",
        {"attended_on": today.isoformat(), "status": "present", "hours": "3"},
    )
    milestone = call(
        "POST",
        f"/api/v1/projects/{project['id']}/milestones",
        {"title": "First drop", "due_date": later},
        201,
    )
    call(
        "POST",
        f"/api/v1/milestones/{milestone['id']}/tasks",
        {"title": "Pack kits", "deadline": later, "priority": "high"},
        201,
    )
    expense = call(
        "POST",
        "/api/v1/expenses",
        {
            "project_id": project["id"],
            "category": "supplies",
            "amount": "120.00",
            "expense_date": today.isoformat(),
            "description": "Packing materials",
        },
        201,
    )
    call("POST", f"/api/v1/expenses/{expense['id']}/decision", {"status": "approved", "comments": "Checked"})
    resource = call(
        "POST",
        "/api/v1/resources",
        {"name": "Demo kit", "category": "emergency_kits", "unit": "kit", "quantity_on_hand": 10, "reorder_level": 2},
        201,
    )
    call(
        "POST",
        f"/api/v1/resources/{resource['id']}/movements",
        {"movement_type": "allocation", "quantity": 2, "project_id": project["id"]},
        201,
    )
    beneficiary = call(
        "POST",
        "/api/v1/beneficiaries",
        {"full_name": "Demo Family", "category": "family", "contact": "9811111111", "address": "Ward 1", "project_ids": [project["id"]]},
        201,
    )
    call(
        "POST",
        f"/api/v1/beneficiaries/{beneficiary['id']}/assistance",
        {
            "project_id": project["id"],
            "assistance_type": "kit",
            "description": "One kit",
            "quantity": 1,
            "distribution_date": today.isoformat(),
            "resource_id": resource["id"],
        },
        201,
    )
    call(
        "POST",
        f"/api/v1/projects/{project['id']}/impact",
        {
            "beneficiaries_served": 1,
            "volunteer_hours": "3",
            "resources_distributed": 1,
            "funds_utilized": "120",
            "milestones_achieved": 0,
            "narrative": "Demo distribution completed.",
        },
        201,
    )
    board = call("GET", "/api/v1/dashboard")
    print(
        f"     donations confirmed {board['confirmed_amount']} | "
        f"active campaigns {board['active_fundraising_campaigns']} | "
        f"active projects {board['active_community_projects']}"
    )
    logs = call("GET", "/api/v1/audit-logs?page_size=5")
    print(f"     latest audit actions: {', '.join(item['action'] for item in logs['items'][:5])}")
    print("Demonstration finished.")


if __name__ == "__main__":
    main()
