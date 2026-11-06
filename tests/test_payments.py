from uuid import uuid4


def register(client, email="owner@example.com"):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Owner",
            "email": email,
            "password": "a-strong-test-password",
            "company_name": "Acme Academy",
        },
    )
    assert res.status_code == 201, res.text
    return client.get("/api/v1/companies").json()[0]["id"]


def new_link(client, cid):
    res = client.post(
        f"/api/v1/companies/{cid}/links",
        json={
            "title": "Term tuition",
            "amount": 125000,
            "currency": "USD",
            "methods": [
                {
                    "label": "International bank transfer",
                    "details": "IBAN: TEST123. Beneficiary: Acme Academy",
                }
            ],
            "recipient_email": "private@example.com",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_claim_review_and_immutable_receipt(client):
    cid = register(client)
    lid = new_link(client, cid)
    public = client.get(f"/api/v1/public/links/{lid}").json()
    assert "recipient_email" not in public
    assert public["methods"][0]["details"].startswith("IBAN")
    claim = {
        "name": "Customer",
        "email": "customer@example.com",
        "method_index": 0,
        "request_key": str(uuid4()),
        "transfer_reference": "BANK-001",
    }
    res = client.post(f"/api/v1/public/links/{lid}/claims", json=claim)
    assert res.status_code == 201, res.text
    pid = res.json()["payment_id"]
    assert client.get(f"/api/v1/public/receipts/{pid}").status_code == 404
    assert client.post(f"/api/v1/public/links/{lid}/claims", json=claim).json()["payment_id"] == pid
    assert (
        client.post(f"/api/v1/companies/{cid}/payments/{pid}/review", json={"decision": "paid"}).status_code
        == 200
    )
    receipt = client.get(f"/api/v1/public/receipts/{pid}").json()
    assert receipt["amount"] == 125000
    assert receipt["reference"] == "BANK-001"
    assert receipt["company"] == "Acme Academy"
    client.put(f"/api/v1/companies/{cid}", json={"name": "Changed company", "accent": "#112233"})
    assert client.get(f"/api/v1/public/receipts/{pid}").json() == receipt
    assert (
        client.post(f"/api/v1/companies/{cid}/payments/{pid}/review", json={"decision": "paid"}).status_code
        == 409
    )


def test_company_isolation(client):
    cid = register(client)
    lid = new_link(client, cid)
    pid = client.post(
        f"/api/v1/public/links/{lid}/claims",
        json={"name": "X", "email": "x@example.com", "method_index": 0, "request_key": str(uuid4())},
    ).json()["payment_id"]
    other = register(client, "other@example.com")
    assert client.get(f"/api/v1/companies/{cid}/links").status_code == 403
    assert (
        client.post(f"/api/v1/companies/{cid}/payments/{pid}/review", json={"decision": "paid"}).status_code
        == 403
    )
    assert (
        client.post(f"/api/v1/companies/{other}/payments/{pid}/review", json={"decision": "paid"}).status_code
        == 404
    )
    assert client.patch(f"/api/v1/companies/{other}/links/{lid}", json={"active": False}).status_code == 404


def test_pause_reject_and_validation(client):
    cid = register(client)
    lid = new_link(client, cid)
    payload = {"name": "X", "email": "x@example.com", "method_index": 3, "request_key": str(uuid4())}
    assert client.post(f"/api/v1/public/links/{lid}/claims", json=payload).status_code == 422
    payload["method_index"] = 0
    pid = client.post(f"/api/v1/public/links/{lid}/claims", json=payload).json()["payment_id"]
    assert (
        client.post(
            f"/api/v1/companies/{cid}/payments/{pid}/review", json={"decision": "rejected"}
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/public/receipts/{pid}").status_code == 404
    assert client.patch(f"/api/v1/companies/{cid}/links/{lid}", json={"active": False}).status_code == 200
    assert client.post(f"/api/v1/public/links/{lid}/claims", json=payload).status_code == 404
    assert client.get(f"/api/v1/public/links/{lid}").status_code == 404


def test_csrf_and_login(client):
    register(client)
    assert (
        client.post("/api/v1/auth/logout", headers={"Origin": "https://evil.example"}, json={}).status_code
        == 403
    )
    assert client.post("/api/v1/auth/logout", json={}).status_code == 204
    assert client.get("/api/v1/companies").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": "a-strong-test-password"}
        ).status_code
        == 200
    )


def test_receipt_outbox_mailjet_retry(client, monkeypatch):
    from types import SimpleNamespace
    import httpx
    from app import worker
    from app.models.entities import Outbox

    cid = register(client)
    lid = new_link(client, cid)
    pid = client.post(
        f"/api/v1/public/links/{lid}/claims",
        json={"name": "Payer", "email": "payer@example.com", "method_index": 0, "request_key": str(uuid4())},
    ).json()["payment_id"]
    client.post(f"/api/v1/companies/{cid}/payments/{pid}/review", json={"decision": "paid"})
    monkeypatch.setattr(worker, "SessionLocal", client.db_factory)
    monkeypatch.setattr(
        worker,
        "settings",
        lambda: SimpleNamespace(
            mailjet_api_key="test",
            mailjet_secret_key="test",
            mail_from="receipts@example.com",
            frontend_url="http://localhost:5173",
        ),
    )

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(worker.httpx, "post", unavailable)
    worker.deliver_batch()
    with client.db_factory() as db:
        row = db.query(Outbox).one()
        assert row.attempts == 1 and not row.sent
    calls = []

    def sent(url, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(
            200, json={"Messages": [{"Status": "success"}]}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(worker.httpx, "post", sent)
    worker.deliver_batch()
    worker.deliver_batch()
    assert len(calls) == 1
    assert f"/receipt/{pid}" in calls[0]["Messages"][0]["TextPart"]
    with client.db_factory() as db:
        assert db.query(Outbox).one().sent


def test_media_signature_tenant_scope(client, monkeypatch):
    from app.core.config import settings

    cid = register(client)
    config = settings()
    monkeypatch.setattr(config, "cloudinary_api_secret", "test-private-secret")
    monkeypatch.setattr(config, "cloudinary_api_key", "test-public-key")
    monkeypatch.setattr(config, "cloudinary_cloud_name", "test-cloud")
    res = client.post(f"/api/v1/companies/{cid}/media-signature", json={})
    assert res.status_code == 200
    assert res.json()["params"]["folder"] == f"paylink/{cid}"
    assert "test-private-secret" not in res.text
    register(client, "another@example.com")
    assert client.post(f"/api/v1/companies/{cid}/media-signature", json={}).status_code == 403
