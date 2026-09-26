"""API integration tests for all 5 Vera endpoints."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.state import store

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "expanded"


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield
    store.reset()


@pytest.fixture
def client():
    return TestClient(app)


def test_healthz_and_metadata(client):
    res = client.get("/v1/healthz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["contexts_loaded"]["category"] == 0

    res_meta = client.get("/v1/metadata")
    assert res_meta.status_code == 200
    meta = res_meta.json()
    assert meta["team_name"] == "Team Vera"
    assert meta["model"] == "deterministic-rules-engine"


def test_context_push_and_versioning(client):
    dentist_cat = json.loads((DATASET_DIR / "categories" / "dentists.json").read_text(encoding="utf-8"))
    
    # 1. Initial push (v1) -> 200
    res = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": dentist_cat
    })
    assert res.status_code == 200
    assert res.json()["accepted"] is True
    assert "ack_dentists_v1" in res.json()["ack_id"]

    # 2. Re-push same version (v1) -> 200 (Idempotent no-op)
    res_idempotent = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": dentist_cat
    })
    assert res_idempotent.status_code == 200
    assert res_idempotent.json()["accepted"] is True

    # 3. Version bump (v2) -> 200
    res_v2 = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 2,
        "payload": dentist_cat
    })
    assert res_v2.status_code == 200
    assert res_v2.json()["accepted"] is True
    assert "ack_dentists_v2" in res_v2.json()["ack_id"]

    # 4. Push stale/lower version (v1 after v2) -> 409 Conflict
    res_stale = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": dentist_cat
    })
    assert res_stale.status_code == 409
    assert res_stale.json()["accepted"] is False
    assert res_stale.json()["reason"] == "stale_version"
    assert res_stale.json()["current_version"] == 2

    # 5. Check healthz contexts_loaded
    res_health = client.get("/v1/healthz")
    assert res_health.json()["contexts_loaded"]["category"] == 1



def test_tick_and_suppression(client):
    # Load Category, Merchant, Trigger
    cat = json.loads((DATASET_DIR / "categories" / "restaurants.json").read_text(encoding="utf-8"))
    merchant = json.loads((DATASET_DIR / "merchants" / "m_006_southindiancafe_restaurant_bangalore.json").read_text(encoding="utf-8"))
    trigger = json.loads((DATASET_DIR / "triggers" / "trg_013_corporate_thali_planning.json").read_text(encoding="utf-8"))

    client.post("/v1/context", json={"scope": "category", "context_id": "restaurants", "version": 1, "payload": cat})
    client.post("/v1/context", json={"scope": "merchant", "context_id": "m_006_southindiancafe_restaurant_bangalore", "version": 1, "payload": merchant})
    client.post("/v1/context", json={"scope": "trigger", "context_id": "trg_013_corporate_thali_planning", "version": 1, "payload": trigger})

    # First tick -> 1 action
    res_tick = client.post("/v1/tick", json={
        "now": "2026-04-26T10:00:00Z",
        "available_triggers": ["trg_013_corporate_thali_planning"]
    })
    assert res_tick.status_code == 200
    actions = res_tick.json()["actions"]
    assert len(actions) == 1
    act = actions[0]
    assert act["merchant_id"] == "m_006_southindiancafe_restaurant_bangalore"
    assert act["trigger_id"] == "trg_013_corporate_thali_planning"
    assert act["send_as"] == "vera"
    assert "Suresh" in act["body"]
    assert act["cta"] == "binary_yes_no"

    # Second tick with same trigger -> Suppressed (0 actions)
    res_tick_2 = client.post("/v1/tick", json={
        "now": "2026-04-26T10:05:00Z",
        "available_triggers": ["trg_013_corporate_thali_planning"]
    })
    assert res_tick_2.status_code == 200
    assert len(res_tick_2.json()["actions"]) == 0


def test_reply_auto_reply_cycle(client):
    conv_id = "conv_autoreply_test"

    # Turn 1: Bot flags auto-reply
    res1 = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "from_role": "merchant",
        "message": "Thank you for contacting us! Our team will respond shortly.",
        "turn_number": 1
    })
    assert res1.status_code == 200
    assert res1.json()["action"] == "send"
    assert "auto-reply" in res1.json()["body"].lower()

    # Turn 2 / 3: Bot enters wait
    res2 = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "from_role": "merchant",
        "message": "Thank you for contacting us! Our team will respond shortly.",
        "turn_number": 3
    })
    assert res2.status_code == 200
    assert res2.json()["action"] == "wait"
    assert res2.json()["wait_seconds"] == 86400

    # Turn 4: Repeated auto-replies -> End
    res3 = client.post("/v1/reply", json={
        "conversation_id": conv_id,
        "from_role": "merchant",
        "message": "Thank you for contacting us! Our team will respond shortly.",
        "turn_number": 4
    })
    assert res3.status_code == 200
    assert res3.json()["action"] == "end"


def test_reply_intent_transition(client):
    res = client.post("/v1/reply", json={
        "conversation_id": "conv_intent_1",
        "from_role": "merchant",
        "message": "Ok, let's do it. What's next?",
        "turn_number": 2
    })
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "send"
    body_lower = data["body"].lower()
    # Must be in action mode, not qualifying
    assert any(w in body_lower for w in ["draft", "pre-fill", "confirm", "ready"])
    assert not any(w in body_lower for w in ["would you", "do you", "can you tell"])


def test_reply_hostile_opt_out(client):
    res = client.post("/v1/reply", json={
        "conversation_id": "conv_hostile_1",
        "from_role": "merchant",
        "message": "Stop messaging me. This is useless spam.",
        "turn_number": 2
    })
    assert res.status_code == 200
    assert res.json()["action"] == "end"


def test_reply_off_topic_redirect(client):
    res = client.post("/v1/reply", json={
        "conversation_id": "conv_offtopic_1",
        "from_role": "merchant",
        "message": "Can you also help me with my GST filing this month?",
        "turn_number": 2
    })
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "send"
    assert "gst" in data["body"].lower() or "ca" in data["body"].lower()
