from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select
from tests.conftest import TestDB
from backend.models import CPAOrder


def body(pieces, shift="T1"):
    return {"request_id": str(uuid4()), "order_number": "SO-100001", "line": "a",
            "pieces": pieces, "shift": shift}


def test_login_missing_machine(env):
    client, headers = env
    no_machine = {"Authorization": headers["Authorization"]}
    assert client.get("/orders/100001/A", headers=no_machine).status_code == 401


def test_cpa_lookup_and_limit(env):
    client, headers = env
    before = client.get("/orders/100001/A", headers=headers)
    assert before.status_code == 200
    assert before.json()["available_pieces"] == 20
    first = client.post("/production", headers=headers, json=body(12))
    assert first.status_code == 201, first.text
    second_payload = body(5)
    warning = client.post("/production", headers=headers, json=second_payload)
    assert warning.status_code == 409
    assert warning.json()["detail"]["code"] == "DUPLICADO_REQUIERE_CONFIRMACION"
    second_payload["confirm_duplicate"] = True
    second = client.post("/production", headers=headers, json=second_payload)
    assert second.status_code == 201, second.text
    over = client.post("/production", headers=headers, json=dict(body(4), confirm_duplicate=True))
    assert over.status_code == 409
    assert over.json()["detail"]["code"] == "EXCESO_CPA"
    assert over.json()["detail"]["available_pieces"] == 3
    final = client.post("/production", headers=headers, json=dict(body(3), confirm_duplicate=True))
    assert final.status_code == 201
    assert final.json()["produced_total"] == 20


def test_cross_laser_and_shift_and_idempotency(env):
    client, headers = env
    first_payload = body(11)
    first = client.post("/production", headers=headers, json=first_payload)
    assert first.status_code == 201
    retry = client.post("/production", headers=headers, json=first_payload)
    assert retry.status_code == 201
    assert retry.json()["replayed"] is True
    h2 = dict(headers, **{"X-Workstation-Key": "Q"*48})
    second = client.post("/production", headers=h2,
                         json=dict(body(9, shift="T2"), confirm_duplicate=True))
    assert second.status_code == 201, second.text
    summary = client.get("/summary?start=2026-01-01&end=2026-12-31", headers=headers)
    assert summary.status_code == 422  # El resumen no permite consultas masivas.
    status = client.get("/orders/100001/A", headers=h2)
    assert status.json()["produced_pieces"] == 20
    assert status.json()["prior_entries"] == 2


def test_fail_closed_when_cpa_unknown_or_stale(env):
    client, headers = env
    assert client.get("/orders/999999/A", headers=headers).status_code == 404
    with TestDB() as db:
        cpa = db.scalar(select(CPAOrder).where(CPAOrder.order_number == "100001"))
        cpa.imported_at = datetime.now(timezone.utc) - timedelta(days=3)
        db.commit()
    result = client.post("/production", headers=headers, json=body(1))
    assert result.status_code == 503
    assert result.json()["detail"]["code"] == "CPA_DESACTUALIZADO"


def test_reused_request_id_cannot_change_payload(env):
    client, headers = env
    original = body(2)
    assert client.post("/production", headers=headers, json=original).status_code == 201
    changed = dict(original, pieces=3)
    response = client.post("/production", headers=headers, json=changed)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ID_REUTILIZADO"
