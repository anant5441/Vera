"""Comprehensive test suite for Vera message composer (T01-T30 validation)."""

import json
from pathlib import Path
import pytest

from app.composer import compose
from app.models import ComposedMessage

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "expanded"


@pytest.fixture(scope="module")
def dataset():
    pairs_file = DATASET_DIR / "test_pairs.json"
    assert pairs_file.exists(), f"Missing {pairs_file}"
    pairs = json.loads(pairs_file.read_text(encoding="utf-8"))["pairs"]
    return pairs


def _load_pair_context(pair: dict):
    tid = pair["trigger_id"]
    mid = pair["merchant_id"]
    cid = pair["customer_id"]

    trg = json.loads((DATASET_DIR / "triggers" / f"{tid}.json").read_text(encoding="utf-8"))
    m = json.loads((DATASET_DIR / "merchants" / f"{mid}.json").read_text(encoding="utf-8"))
    c = (
        json.loads((DATASET_DIR / "customers" / f"{cid}.json").read_text(encoding="utf-8"))
        if cid
        else None
    )
    cat_slug = m.get("category_slug", "restaurants")
    cat = json.loads((DATASET_DIR / "categories" / f"{cat_slug}.json").read_text(encoding="utf-8"))
    return cat, m, trg, c


def test_all_30_canonical_pairs(dataset):
    """Ensure all 30 canonical test pairs produce valid, non-empty, grounded messages."""
    assert len(dataset) == 30, f"Expected 30 test pairs, got {len(dataset)}"

    for pair in dataset:
        test_id = pair["test_id"]
        cat, m, trg, c = _load_pair_context(pair)

        msg = compose(cat, m, trg, c)

        assert isinstance(msg, ComposedMessage), f"{test_id}: Expected ComposedMessage"
        assert len(msg.body) >= 20, f"{test_id}: Message body too short: '{msg.body}'"
        assert "http://" not in msg.body and "https://" not in msg.body, (
            f"{test_id}: Message contains URL: '{msg.body}'"
        )
        assert msg.cta, f"{test_id}: Missing CTA"
        assert msg.suppression_key, f"{test_id}: Missing suppression key"
        assert msg.rationale, f"{test_id}: Missing rationale"

        # Scope validation
        if c is not None or trg.get("scope") == "customer":
            assert msg.send_as == "merchant_on_behalf", (
                f"{test_id}: Customer scope should send_as 'merchant_on_behalf'"
            )
        else:
            assert msg.send_as == "vera", (
                f"{test_id}: Merchant scope should send_as 'vera'"
            )

        # Determinism check
        msg_repeat = compose(cat, m, trg, c)
        assert msg.body == msg_repeat.body, f"{test_id}: Non-deterministic body output"
        assert msg.cta == msg_repeat.cta, f"{test_id}: Non-deterministic cta output"
        assert msg.suppression_key == msg_repeat.suppression_key, (
            f"{test_id}: Non-deterministic suppression key"
        )


def test_t01_corporate_thali_planning(dataset):
    pair = next(p for p in dataset if p["test_id"] == "T01")
    cat, m, trg, c = _load_pair_context(pair)
    msg = compose(cat, m, trg, c)

    assert "Suresh" in msg.body
    assert "₹149" in msg.body or "thali" in msg.body
    assert "Indiranagar" in msg.body
    assert "draft" in msg.body.lower()
    assert msg.send_as == "vera"


def test_t02_kids_yoga_planning(dataset):
    pair = next(p for p in dataset if p["test_id"] == "T02")
    cat, m, trg, c = _load_pair_context(pair)
    msg = compose(cat, m, trg, c)

    assert "Padma" in msg.body
    assert "kids yoga" in msg.body.lower()
    assert "₹2,499" in msg.body
    assert "Mylapore" in msg.body
    assert msg.send_as == "vera"


def test_t03_t04_customer_appointment_reminders(dataset):
    for tid in ("T03", "T04"):
        pair = next(p for p in dataset if p["test_id"] == tid)
        cat, m, trg, c = _load_pair_context(pair)
        msg = compose(cat, m, trg, c)

        assert msg.send_as == "merchant_on_behalf"
        assert "appointment tomorrow" in msg.body.lower()
        assert "confirm" in msg.body.lower() or "reply yes" in msg.body.lower()


def test_t07_chronic_refill_due(dataset):
    pair = next(p for p in dataset if p["test_id"] == "T07")
    cat, m, trg, c = _load_pair_context(pair)
    msg = compose(cat, m, trg, c)

    assert msg.send_as == "merchant_on_behalf"
    assert "Sharma" in msg.body
    assert "metformin" in msg.body.lower()
    assert "atorvastatin" in msg.body.lower()
    assert "telmisartan" in msg.body.lower()
    assert "15%" in msg.body


def test_t09_competitor_opened(dataset):
    pair = next(p for p in dataset if p["test_id"] == "T09")
    cat, m, trg, c = _load_pair_context(pair)
    msg = compose(cat, m, trg, c)

    assert "Dr. Meera" in msg.body
    assert "Smile Studio" in msg.body
    assert "1.3 km" in msg.body
    assert "₹299" in msg.body


def test_t13_customer_winback(dataset):
    pair = next(p for p in dataset if p["test_id"] == "T13")
    cat, m, trg, c = _load_pair_context(pair)
    msg = compose(cat, m, trg, c)

    assert msg.send_as == "merchant_on_behalf"
    assert "Rashmi" in msg.body
    assert "Karthik" in msg.body
    assert "PowerHouse" in msg.body
    assert "weight-loss" in msg.body.lower() or "trial" in msg.body.lower()


def test_t20_gbp_unverified(dataset):
    pair = next(p for p in dataset if p["test_id"] == "T20")
    cat, m, trg, c = _load_pair_context(pair)
    msg = compose(cat, m, trg, c)

    assert "Vikas" in msg.body
    assert "30%" in msg.body
    assert "unverified" in msg.body.lower()
    assert "Gomti Nagar" in msg.body


def test_t21_ipl_match_today(dataset):
    pair = next(p for p in dataset if p["test_id"] == "T21")
    cat, m, trg, c = _load_pair_context(pair)
    msg = compose(cat, m, trg, c)

    assert "Suresh" in msg.body
    assert "DC vs MI" in msg.body
    assert "Arun Jaitley" in msg.body
    assert "BOGO" in msg.body or "Buy 1" in msg.body


def test_t28_dentist_recall_due(dataset):
    pair = next(p for p in dataset if p["test_id"] == "T28")
    cat, m, trg, c = _load_pair_context(pair)
    msg = compose(cat, m, trg, c)

    assert msg.send_as == "merchant_on_behalf"
    assert "Priya" in msg.body
    assert "Dr. Meera" in msg.body
    assert "5 months" in msg.body.lower()
    assert "₹299" in msg.body


def test_t30_compliance_dci_radiograph(dataset):
    pair = next(p for p in dataset if p["test_id"] == "T30")
    cat, m, trg, c = _load_pair_context(pair)
    msg = compose(cat, m, trg, c)

    assert "Dr. Meera" in msg.body
    assert "DCI" in msg.body
    assert "radiograph" in msg.body.lower()
    assert "1.0 mSv" in msg.body or "1.5 to 1.0" in msg.body
