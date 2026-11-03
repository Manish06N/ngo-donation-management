from datetime import date, timedelta
from decimal import Decimal


def _money(value):
    return Decimal(str(value))


def _campaign(client, headers, manager_id, title="School kits"):
    today = date.today()
    response = client.post(
        "/api/v1/campaigns",
        json={
            "title": title,
            "description": "Fund school kits for the term",
            "goal_amount": "10000.00",
            "budget_amount": "2000.00",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "category": "education",
            "manager_id": manager_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _donor(client, headers, email="giver@example.com", name="Giver"):
    response = client.post(
        "/api/v1/donors",
        json={"donor_type": "individual", "name": name, "email": email, "city": "Patna"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _activate(client, headers, campaign_id):
    response = client.post(f"/api/v1/campaigns/{campaign_id}/status", json={"status": "active"}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_donation_rules_totals_and_receipts(client, admin, admin_headers):
    donor = _donor(client, admin_headers)
    campaign = _campaign(client, admin_headers, admin.id)
    draft = client.post(
        "/api/v1/donations",
        json={
            "donor_id": donor["id"],
            "campaign_id": campaign["id"],
            "amount": "500.00",
            "donation_date": date.today().isoformat(),
            "method": "upi",
            "reference_number": "REF-1001",
        },
        headers=admin_headers,
    )
    assert draft.status_code == 409
    assert draft.json()["code"] == "campaign_not_accepting"

    _activate(client, admin_headers, campaign["id"])
    bad_amount = client.post(
        "/api/v1/donations",
        json={
            "donor_id": donor["id"],
            "campaign_id": campaign["id"],
            "amount": "0",
            "donation_date": date.today().isoformat(),
            "method": "cash",
            "reference_number": "REF-ZERO",
        },
        headers=admin_headers,
    )
    assert bad_amount.status_code == 422

    created = client.post(
        "/api/v1/donations",
        json={
            "donor_id": donor["id"],
            "campaign_id": campaign["id"],
            "amount": "500.00",
            "donation_date": date.today().isoformat(),
            "method": "upi",
            "reference_number": "ref-1001",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    donation_id = created.json()["id"]
    assert created.json()["reference_number"] == "REF-1001"
    assert created.json()["status"] == "pending"

    duplicate = client.post(
        "/api/v1/donations",
        json={
            "donor_id": donor["id"],
            "campaign_id": campaign["id"],
            "amount": "20.00",
            "donation_date": date.today().isoformat(),
            "method": "cash",
            "reference_number": "REF-1001",
        },
        headers=admin_headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "duplicate_reference"

    early_receipt = client.post(f"/api/v1/donations/{donation_id}/receipt", headers=admin_headers)
    assert early_receipt.status_code == 409

    confirmed = client.post(f"/api/v1/donations/{donation_id}/status", json={"status": "confirmed"}, headers=admin_headers)
    assert confirmed.status_code == 200, confirmed.text
    campaign_body = client.get(f"/api/v1/campaigns/{campaign['id']}", headers=admin_headers).json()
    assert _money(campaign_body["raised_amount"]) == Decimal("500.00")

    receipt = client.post(f"/api/v1/donations/{donation_id}/receipt", headers=admin_headers)
    assert receipt.status_code == 201, receipt.text
    again = client.post(f"/api/v1/donations/{donation_id}/receipt", headers=admin_headers)
    assert again.status_code == 409
    assert again.json()["code"] == "duplicate_receipt"

    pdf = client.get(f"/api/v1/receipts/{receipt.json()['id']}/pdf", headers=admin_headers)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    refunded = client.post(f"/api/v1/donations/{donation_id}/status", json={"status": "refunded"}, headers=admin_headers)
    assert refunded.status_code == 200, refunded.text
    after = client.get(f"/api/v1/campaigns/{campaign['id']}", headers=admin_headers).json()
    assert _money(after["raised_amount"]) == Decimal("0.00")
    voided = client.get(f"/api/v1/receipts/{receipt.json()['id']}", headers=admin_headers).json()
    assert voided["status"] == "void"

    paused = client.post(f"/api/v1/campaigns/{campaign['id']}/status", json={"status": "paused"}, headers=admin_headers)
    assert paused.status_code == 200
    refused = client.post(
        "/api/v1/donations",
        json={
            "donor_id": donor["id"],
            "campaign_id": campaign["id"],
            "amount": "10.00",
            "donation_date": date.today().isoformat(),
            "method": "cash",
            "reference_number": "REF-2002",
        },
        headers=admin_headers,
    )
    assert refused.status_code == 409


def test_second_confirmed_donation_adds_to_the_same_total(client, admin, admin_headers):
    donor = _donor(client, admin_headers, "second@example.com", "Second")
    campaign = _activate(client, admin_headers, _campaign(client, admin_headers, admin.id, "Health camp")["id"])
    for reference, amount in (("AAA-100", "40.00"), ("BBB-200", "60.00")):
        created = client.post(
            "/api/v1/donations",
            json={
                "donor_id": donor["id"],
                "campaign_id": campaign["id"],
                "amount": amount,
                "donation_date": date.today().isoformat(),
                "method": "bank_transfer",
                "reference_number": reference,
            },
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text
        confirmed = client.post(
            f"/api/v1/donations/{created.json()['id']}/status",
            json={"status": "confirmed"},
            headers=admin_headers,
        )
        assert confirmed.status_code == 200, confirmed.text
    total = client.get(f"/api/v1/campaigns/{campaign['id']}", headers=admin_headers).json()
    assert _money(total["raised_amount"]) == Decimal("100.00")
    history = client.get(f"/api/v1/donors/{donor['id']}/donations", headers=admin_headers)
    assert history.status_code == 200
    assert history.json()["total"] == 2
