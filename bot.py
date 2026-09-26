"""Vera Merchant AI Assistant — bot submission module."""

from typing import Any, Optional
from app.composer import compose as _internal_compose


def compose(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Compose a deterministic message from the 4 contexts.

    Inputs:
        category: dict loaded from dataset JSON
        merchant: dict loaded from dataset JSON
        trigger: dict loaded from dataset JSON
        customer: optional dict loaded from dataset JSON

    Returns:
        dict with keys: body, cta, send_as, suppression_key, rationale
    """
    res = _internal_compose(category, merchant, trigger, customer)
    return {
        "body": res.body,
        "cta": res.cta,
        "send_as": res.send_as,
        "suppression_key": res.suppression_key,
        "rationale": res.rationale,
    }
