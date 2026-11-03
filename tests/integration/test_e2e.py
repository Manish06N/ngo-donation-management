"""The mandatory demonstration, as one API conversation."""

from datetime import date, timedelta
from decimal import Decimal


def test_end_to_end_demo(client, admin, admin_headers):
    today = date.today()
    later = today + timedelta(days=45)

    donor = client.post(
        "/api/v1/donors",
        json={
            "donor_type": "organization",
            "name": "Meera Shah",
            "organization_name": "Shah Trust",
            "email": "trust@example.com",
            "phone": "9811111111",
            "city": "Patna",
        },
        headers=admin_headers,
    )
    assert donor.status_code == 201, donor.text

    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "title": "Monsoon relief",
            "description": "Dry rations for flooded wards",
            "goal_amount": "20000.00",
            "budget_amount": "5000.00",
            "start_date": today.isoformat(),
            "end_date": later.isoformat(),
            "category": "disaster_relief",
            "manager_id": admin.id,
        },
        headers=admin_headers,
    )
    assert campaign.status_code == 201, campaign.text
    campaign_id = campaign.json()["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/status", json={"status": "active"}, headers=admin_headers).status_code == 200

    donation = client.post(
        "/api/v1/donations",
        json={
            "donor_id": donor.json()["id"],
            "campaign_id": campaign_id,
            "amount": "1500.00",
            "donation_date": today.isoformat(),
            "method": "bank_transfer",
            "reference_number": "NEFT-77881",
        },
        headers=admin_headers,
    )
    assert donation.status_code == 201, donation.text
    donation_id = donation.json()["id"]
    confirmed = client.post(f"/api/v1/donations/{donation_id}/status", json={"status": "confirmed"}, headers=admin_headers)
    assert confirmed.status_code == 200, confirmed.text
    receipt = client.post(f"/api/v1/donations/{donation_id}/receipt", headers=admin_headers)
    assert receipt.status_code == 201, receipt.text
    assert receipt.json()["receipt_number"].startswith("RCP-")

    volunteer = client.post(
        "/api/v1/volunteers",
        json={
            "full_name": "Anil Das",
            "email": "anil@example.com",
            "skills": ["logistics"],
            "availability": "Weekdays",
            "status": "active",
            "emergency_contact_name": "Sita Das",
            "emergency_contact_phone": "9822222222",
        },
        headers=admin_headers,
    )
    assert volunteer.status_code == 201, volunteer.text

    project = client.post(
        "/api/v1/projects",
        json={
            "title": "Ward 12 relief",
            "objectives": "Distribute rations",
            "location": "Ward 12, Patna",
            "start_date": today.isoformat(),
            "end_date": later.isoformat(),
            "budget_amount": "8000.00",
            "manager_id": admin.id,
        },
        headers=admin_headers,
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    assert client.post(f"/api/v1/projects/{project_id}/submit", json={"comments": "Please approve"}, headers=admin_headers).status_code == 200
    approved = client.post(
        f"/api/v1/projects/{project_id}/decision",
        json={"decision": "approved", "comments": "Approved for relief"},
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    assert client.post(f"/api/v1/projects/{project_id}/status", json={"status": "active"}, headers=admin_headers).status_code == 200

    assignment = client.post(
        "/api/v1/assignments",
        json={
            "volunteer_id": volunteer.json()["id"],
            "project_id": project_id,
            "responsibility": "Distribution lead",
            "start_date": today.isoformat(),
            "end_date": later.isoformat(),
        },
        headers=admin_headers,
    )
    assert assignment.status_code == 201, assignment.text
    assert client.post(
        f"/api/v1/assignments/{assignment.json()['id']}/attendance",
        json={"attended_on": today.isoformat(), "status": "present", "hours": "6"},
        headers=admin_headers,
    ).status_code == 200

    milestone = client.post(
        f"/api/v1/projects/{project_id}/milestones",
        json={"title": "First distribution", "due_date": later.isoformat()},
        headers=admin_headers,
    )
    assert milestone.status_code == 201, milestone.text
    task = client.post(
        f"/api/v1/milestones/{milestone.json()['id']}/tasks",
        json={"title": "Pack kits", "deadline": later.isoformat(), "priority": "high", "assignee_id": volunteer.json()["id"]},
        headers=admin_headers,
    )
    assert task.status_code == 201, task.text

    expense = client.post(
        "/api/v1/expenses",
        json={
            "project_id": project_id,
            "category": "food",
            "amount": "900.00",
            "expense_date": today.isoformat(),
            "description": "Ration purchase",
            "receipt_reference": "INV-19",
        },
        headers=admin_headers,
    )
    assert expense.status_code == 201, expense.text
    assert client.post(
        f"/api/v1/expenses/{expense.json()['id']}/decision",
        json={"status": "approved", "comments": "Checked"},
        headers=admin_headers,
    ).status_code == 200

    resource = client.post(
        "/api/v1/resources",
        json={"name": "Family kit", "category": "emergency_kits", "unit": "kit", "quantity_on_hand": 20, "reorder_level": 5},
        headers=admin_headers,
    )
    assert resource.status_code == 201, resource.text
    allocated = client.post(
        f"/api/v1/resources/{resource.json()['id']}/movements",
        json={"movement_type": "allocation", "quantity": 4, "project_id": project_id, "notes": "Ward 12"},
        headers=admin_headers,
    )
    assert allocated.status_code == 201, allocated.text

    beneficiary = client.post(
        "/api/v1/beneficiaries",
        json={"full_name": "Family 18", "category": "family", "contact": "9800000000", "address": "Ward 12", "project_ids": [project_id]},
        headers=admin_headers,
    )
    assert beneficiary.status_code == 201, beneficiary.text
    assistance = client.post(
        f"/api/v1/beneficiaries/{beneficiary.json()['id']}/assistance",
        json={
            "project_id": project_id,
            "assistance_type": "ration",
            "description": "One family kit",
            "quantity": 1,
            "distribution_date": today.isoformat(),
            "resource_id": resource.json()["id"],
        },
        headers=admin_headers,
    )
    assert assistance.status_code == 201, assistance.text

    impact = client.post(
        f"/api/v1/projects/{project_id}/impact",
        json={
            "beneficiaries_served": 1,
            "volunteer_hours": "6",
            "resources_distributed": 1,
            "funds_utilized": "900",
            "milestones_achieved": 0,
            "narrative": "First kits reached Ward 12.",
        },
        headers=admin_headers,
    )
    assert impact.status_code == 201, impact.text

    board = client.get("/api/v1/dashboard", headers=admin_headers)
    assert board.status_code == 200, board.text
    body = board.json()
    assert body["total_donations"] >= 1
    assert body["confirmed_donations"] >= 1
    assert Decimal(body["confirmed_amount"]) == Decimal("1500.00")
    assert body["active_fundraising_campaigns"] >= 1
    assert body["total_volunteers"] >= 1
    assert body["active_community_projects"] >= 1
    assert body["pending_project_approvals"] == 0
    assert Decimal(body["volunteer_hours"]) == Decimal("6.00")
    assert body["total_beneficiaries_served"] >= 1
    assert Decimal(body["funds_utilized"]) == Decimal("900.00")
    assert any(item["name"] == "Family kit" and item["quantity_on_hand"] == 15 for item in body["resource_stock_levels"])

    exported = client.get("/api/v1/reports/donations", params={"format": "csv"}, headers=admin_headers)
    assert exported.status_code == 200
    assert "NEFT-77881" in exported.text
    assert exported.headers["content-type"].startswith("text/csv")

    logs = client.get("/api/v1/audit-logs", params={"page_size": 100}, headers=admin_headers)
    assert logs.status_code == 200, logs.text
    actions = {item["action"] for item in logs.json()["items"]}
    assert "donation.created" in actions
    assert "donation.status_changed" in actions
    assert "project.approved" in actions
    assert "expense.approved" in actions
    assert "resource.movement" in actions
    assert "assistance.recorded" in actions
    assert all(item["actor_id"] == admin.id for item in logs.json()["items"])
