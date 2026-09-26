# Vera Message Engine — Merchant AI Assistant

A high-performance, deterministic, context-aware merchant engagement engine built for the **magicpin AI Challenge**.

---

## 1. Overview & Core Philosophy

Vera engages and assists local-commerce merchants across 5 core verticals (Dentists, Salons, Restaurants, Gyms, Pharmacies) over WhatsApp.

### Key Principles:
1. **Deterministic & Grounded**: Every outbound message strictly uses verifiable facts present in the received context (exact prices, verified metrics, customer slots, clinical citations). Zero hallucination.
2. **Single Actionable CTA**: Every message features exactly one low-friction Call-to-Action (binary YES/NO, confirm/cancel, or slot choice).
3. **Conversational Continuity**: Automatically detects active merchant intent, switches to action mode, and avoids redundant qualification questions.
4. **Resilient Edge Handling**: Handles WhatsApp Business auto-replies gracefully, respects merchant opt-outs immediately, and tactfully redirects out-of-scope queries (e.g. Tax/GST).
5. **Ultra-Lean Architecture**: Minimal lines of code with maximum scalability, zero bloat, and millisecond execution time.

---

## 2. The 4-Context Framework

Every message is composed from four structured context layers:

```python
compose(category, merchant, trigger, customer=None) -> ComposedMessage
```

- **CategoryContext**: Vertical-specific rules, tone, allowed clinical/commercial terms, and taboo constraints.
- **MerchantContext**: Business identity, owner, locality, performance signals, active offers, and conversation history.
- **TriggerContext**: Event prompting the message (e.g. `active_planning_intent`, `recall_due`, `perf_dip`, `cde_opportunity`, `competitor_opened`, `chronic_refill_due`).
- **CustomerContext** *(Optional)*: Customer identity, visit history, preferences, and explicit consent for `send_as="merchant_on_behalf"` communications.

---

## 3. Architecture & Project Structure

```
Vera/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI REST server exposing all 5 /v1/ endpoints
│   ├── composer.py      # Core pure deterministic composer & trigger dispatcher
│   ├── compose.py       # Re-export interface
│   ├── models.py        # Lightweight Pydantic data schemas
│   ├── state.py         # Thread-safe in-memory context store & reply state machine
│   └── categories/      # Vertical-specific rules (Dentists, Salons, Restaurants, Gyms, Pharmacies)
├── tests/
│   ├── test_composer.py # Validates all 30 canonical test pairs (T01-T30) & determinism
│   └── test_api.py      # Integration tests for all REST endpoints & conversation flows
├── bot.py               # Candidate submission module
├── chat.py              # Interactive WhatsApp CLI simulator
├── generate_submission.py
├── submission.jsonl     # Generated 30 canonical scenario outputs
├── main.py              # Server launcher
├── pyproject.toml       # Dependencies and pytest configuration
└── AI/
    └── session.md       # Step-by-step thinking and architectural decision log
```

---

## 4. API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/v1/healthz` | `GET` | Health check & loaded context counts |
| `/v1/metadata` | `GET` | Bot identity, approach, and version info |
| `/v1/context` | `POST` | Ingests context with atomic versioning (409 on stale version) |
| `/v1/tick` | `POST` | Wake-up trigger evaluation & proactive message generation |
| `/v1/reply` | `POST` | Handles simulated merchant/customer replies with intent routing |

---

## 5. Getting Started & Testing

### Interactive WhatsApp Chat Session
You can chat directly with Vera as any merchant persona:
```bash
uv run python chat.py
```

### Running Tests
```bash
uv run pytest
```

### Running the API Server
```bash
uv run python main.py
# Server starts on http://0.0.0.0:8080
```

### Generating `submission.jsonl`
```bash
uv run python generate_submission.py
```

