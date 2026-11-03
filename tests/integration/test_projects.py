from datetime import date, timedelta

from tests.conftest import auth_header, make_user
from app.domain.enums import Role


def _project(client, headers, manager_id, budget="5000.00"):
    today = date.today()
    response = client.post(
        "/api/v1/projects",
        json={
            "title": "Village library",
            "objectives": "Open a reading room",
            "description": "Books and a quiet room",
            "location": "Patna",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=60)).isoformat(),
            "budget_amount": budget,
            "manager_id": manager_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _volunteer(client, headers, email="helper@example.com", status="active"):
    response = client.post(
        "/api/v1/volunteers",
        json={
            "full_name": "Helper One",
            "email": email,
            "skills": ["teaching", "first aid"],
            "experience": "Two years in classrooms",
            "availability": "Weekends",
            "status": status,
            "emergency_contact_name": "Kin",
            "emergency_contact_phone": "9000000000",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_project_cannot_activate_until_approved(client, admin, admin_headers):
    project = _project(client, admin_headers, admin.id)
    blocked = client.post(f"/api/v1/projects/{project['id']}/status", json={"status": "active"}, headers=admin_headers)
    assert blocked.status_code == 409

    submitted = client.post(f"/api/v1/projects/{project['id']}/submit", json={"comments": "Ready"}, headers=admin_headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["approval_state"] == "pending"
    rejected = client.post(
        f"/api/v1/projects/{project['id']}/decision",
        json={"decision": "rejected", "comments": "Budget notes are missing"},
        headers=admin_headers,
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "planning"
    bare = client.post(f"/api/v1/projects/{project['id']}/decision", json={"decision": "rejected"}, headers=admin_headers)
    assert bare.status_code == 409

    client.post(f"/api/v1/projects/{project['id']}/submit", json={"comments": "Notes added"}, headers=admin_headers)
    approved = client.post(
        f"/api/v1/projects/{project['id']}/decision",
        json={"decision": "approved", "comments": "Proceed"},
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    history = client.get(f"/api/v1/projects/{project['id']}/approvals", headers=admin_headers)
    assert [item["action"] for item in history.json()] == ["submitted", "rejected", "submitted", "approved"]
    active = client.post(f"/api/v1/projects/{project['id']}/status", json={"status": "active"}, headers=admin_headers)
    assert active.status_code == 200, active.text


def test_assignment_conflict_and_hours(client, admin, admin_headers):
    project = _project(client, admin_headers, admin.id)
    client.post(f"/api/v1/projects/{project['id']}/submit", json={"comments": "go"}, headers=admin_headers)
    client.post(
        f"/api/v1/projects/{project['id']}/decision",
        json={"decision": "approved", "comments": "ok"},
        headers=admin_headers,
    )
    applied = _volunteer(client, admin_headers, "applied@example.com", "applied")
    refused = client.post(
        "/api/v1/assignments",
        json={
            "volunteer_id": applied["id"],
            "project_id": project["id"],
            "responsibility": "Teaching",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
        },
        headers=admin_headers,
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "volunteer_not_active"

    volunteer = _volunteer(client, admin_headers)
    first = client.post(
        "/api/v1/assignments",
        json={
            "volunteer_id": volunteer["id"],
            "project_id": project["id"],
            "responsibility": "Teaching",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=10)).isoformat(),
        },
        headers=admin_headers,
    )
    assert first.status_code == 201, first.text
    other = _project(client, admin_headers, admin.id)
    client.post(f"/api/v1/projects/{other['id']}/submit", json={}, headers=admin_headers)
    client.post(f"/api/v1/projects/{other['id']}/decision", json={"decision": "approved", "comments": "ok"}, headers=admin_headers)
    overlap = client.post(
        "/api/v1/assignments",
        json={
            "volunteer_id": volunteer["id"],
            "project_id": other["id"],
            "responsibility": "Logistics",
            "start_date": (date.today() + timedelta(days=5)).isoformat(),
            "end_date": (date.today() + timedelta(days=12)).isoformat(),
        },
        headers=admin_headers,
    )
    assert overlap.status_code == 409
    assert overlap.json()["code"] == "assignment_conflict"

    attendance = client.post(
        f"/api/v1/assignments/{first.json()['id']}/attendance",
        json={"attended_on": date.today().isoformat(), "status": "present", "hours": "4.5"},
        headers=admin_headers,
    )
    assert attendance.status_code == 200, attendance.text
    listed = client.get("/api/v1/assignments", headers=admin_headers).json()
    match = next(item for item in listed["items"] if item["id"] == first.json()["id"])
    assert str(match["hours_completed"]).startswith("4.5")

    found = client.get("/api/v1/volunteers", params={"skill": "teaching"}, headers=admin_headers)
    assert found.status_code == 200
    assert found.json()["total"] >= 1


def test_milestone_completion_blocks_project_completion(client, admin, admin_headers):
    project = _project(client, admin_headers, admin.id)
    client.post(f"/api/v1/projects/{project['id']}/submit", json={}, headers=admin_headers)
    client.post(f"/api/v1/projects/{project['id']}/decision", json={"decision": "approved", "comments": "ok"}, headers=admin_headers)
    client.post(f"/api/v1/projects/{project['id']}/status", json={"status": "active"}, headers=admin_headers)
    milestone = client.post(
        f"/api/v1/projects/{project['id']}/milestones",
        json={"title": "Room ready", "due_date": (date.today() + timedelta(days=7)).isoformat()},
        headers=admin_headers,
    )
    assert milestone.status_code == 201, milestone.text
    task = client.post(
        f"/api/v1/milestones/{milestone.json()['id']}/tasks",
        json={"title": "Paint walls", "deadline": (date.today() - timedelta(days=1)).isoformat(), "priority": "high"},
        headers=admin_headers,
    )
    assert task.status_code == 201, task.text
    overdue = client.get("/api/v1/tasks", params={"overdue": True}, headers=admin_headers)
    assert any(item["id"] == task.json()["id"] for item in overdue.json()["items"])
    blocked = client.post(f"/api/v1/projects/{project['id']}/status", json={"status": "completed"}, headers=admin_headers)
    assert blocked.status_code == 409
    done = client.patch(f"/api/v1/tasks/{task.json()['id']}", json={"status": "done"}, headers=admin_headers)
    assert done.status_code == 200, done.text
    milestones = client.get(f"/api/v1/projects/{project['id']}/milestones", headers=admin_headers).json()
    assert milestones[0]["status"] == "completed"
    finished = client.post(f"/api/v1/projects/{project['id']}/status", json={"status": "completed"}, headers=admin_headers)
    assert finished.status_code == 200, finished.text
    _ = make_user, auth_header, Role
