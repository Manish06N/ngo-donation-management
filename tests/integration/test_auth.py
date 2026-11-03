from tests.conftest import auth_header, make_user
from app.domain.enums import Role


def test_register_login_me_and_refresh_rotation(client):
    created = client.post(
        "/api/v1/auth/register",
        json={
            "email": "donor@example.com",
            "password": "Password1",
            "full_name": "Ada Donor",
            "role": "donor",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "donor"

    logged = client.post("/api/v1/auth/login", json={"email": "donor@example.com", "password": "Password1"})
    assert logged.status_code == 200, logged.text
    body = logged.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "donor@example.com"

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert reused.status_code == 401


def test_wrong_password_and_short_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "ada@example.com", "password": "Password1", "full_name": "Ada", "role": "donor"},
    )
    bad = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "nope1234"})
    assert bad.status_code == 401
    missing = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "nope1234"})
    assert missing.status_code == 401
    assert bad.json()["detail"] == missing.json()["detail"]
    short = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "short", "full_name": "Short", "role": "donor"},
    )
    assert short.status_code == 422


def test_public_registration_cannot_create_staff(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "boss@example.com", "password": "Password1", "full_name": "Boss", "role": "super_admin"},
    )
    assert response.status_code == 422


def test_password_reset_and_deactivation(client, session, admin_headers):
    client.post(
        "/api/v1/auth/register",
        json={"email": "reset@example.com", "password": "Password1", "full_name": "Reset Me", "role": "donor"},
    )
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    assert forgot.status_code == 200
    token = forgot.json()["reset_token"]
    assert token
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})
    assert unknown.json()["message"] == forgot.json()["message"]
    assert unknown.json()["reset_token"] is None

    reset = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Password2"})
    assert reset.status_code == 200, reset.text
    old = client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "Password1"})
    assert old.status_code == 401
    new = client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "Password2"})
    assert new.status_code == 200
    again = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Password3"})
    assert again.status_code == 400

    user_id = new.json()["user"]["id"]
    off = client.patch(f"/api/v1/users/{user_id}/activation", json={"is_active": False}, headers=admin_headers)
    assert off.status_code == 200, off.text
    blocked = client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "Password2"})
    assert blocked.status_code == 403
    self_off = client.patch(
        f"/api/v1/users/{client.get('/api/v1/auth/me', headers=admin_headers).json()['id']}/activation",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert self_off.status_code == 409


def test_donor_cannot_list_other_donors(client, session, admin_headers):
    client.post(
        "/api/v1/auth/register",
        json={"email": "one@example.com", "password": "Password1", "full_name": "One", "role": "donor"},
    )
    created = client.post(
        "/api/v1/donors",
        json={"donor_type": "individual", "name": "Hidden Person", "email": "hidden@example.com"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    headers = auth_header(client, "one@example.com")
    listing = client.get("/api/v1/donors", headers=headers)
    assert listing.status_code == 200, listing.text
    assert [item["email"] for item in listing.json()["items"]] == ["one@example.com"]
    denied = client.get(f"/api/v1/donors/{created.json()['id']}", headers=headers)
    assert denied.status_code == 403
    volunteer = make_user(session, "vol@example.com", Role.VOLUNTEER)
    denied_vol = client.get("/api/v1/donors", headers=auth_header(client, volunteer.email))
    assert denied_vol.status_code == 403


def test_protected_route_without_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
