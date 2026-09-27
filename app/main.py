"""FastAPI application for Vera Message Engine."""

import os
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.models import (
    ContextPushRequest,
    HealthzResponse,
    MetadataResponse,
    ReplyRequest,
    ReplyResponse,
    TickRequest,
    TickResponse,
)
from app.state import store

app = FastAPI(
    title="Vera Message Engine",
    description="Deterministic context-aware merchant engagement assistant for magicpin",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "vera-message-engine",
        "uptime_seconds": store.uptime_seconds,
    }


@app.get("/v1/healthz", response_model=HealthzResponse)
def healthz():
    return HealthzResponse(
        status="ok",
        uptime_seconds=store.uptime_seconds,
        contexts_loaded=store.counts,
    )


@app.get("/v1/metadata", response_model=MetadataResponse)
def metadata():
    return MetadataResponse(
        team_name=os.getenv("TEAM_NAME", "Team Anant"),
        team_members=[os.getenv("TEAM_MEMBER", "Anant")],
        model="deterministic-rules-engine",
        approach="modular deterministic composer with context-grounding & intent-state routing",
        contact_email=os.getenv("CONTACT_EMAIL", "anantji2332@gmail.com"),
        version="1.0.0",
        submitted_at="2026-04-26T08:00:00Z",
    )


@app.post("/v1/context")
def push_context(req: ContextPushRequest):
    accepted, ack_or_reason, curr_ver = store.push_context(
        scope=req.scope,
        context_id=req.context_id,
        version=req.version,
        payload=req.payload,
    )
    if not accepted:
        if ack_or_reason == "stale_version":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "accepted": False,
                    "reason": "stale_version",
                    "current_version": curr_ver,
                },
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "accepted": False,
                "reason": ack_or_reason or "invalid_payload",
            },
        )

    return {
        "accepted": True,
        "ack_id": ack_or_reason,
        "stored_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/v1/tick", response_model=TickResponse)
def tick(req: TickRequest):
    return store.tick(now=req.now, available_triggers=req.available_triggers)


@app.post("/v1/reply", response_model=ReplyResponse)
def reply(req: ReplyRequest):
    return store.handle_reply(
        conversation_id=req.conversation_id,
        merchant_id=req.merchant_id,
        customer_id=req.customer_id,
        from_role=req.from_role,
        message=req.message,
        turn_number=req.turn_number,
    )


@app.post("/v1/teardown")
def teardown():
    """Wipe all state — called by judge at end of test."""
    store.reset()
    return {"status": "wiped", "contexts_loaded": store.counts}

