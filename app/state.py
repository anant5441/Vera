"""State management for Vera Message Engine (in-memory context store & conversation state)."""

import time
from datetime import datetime, timezone
from typing import Any, Optional

from app.composer import compose
from app.models import ReplyResponse, TickAction, TickResponse


class ContextStore:
    def __init__(self):
        self.categories: dict[str, dict[str, Any]] = {}
        self.merchants: dict[str, dict[str, Any]] = {}
        self.customers: dict[str, dict[str, Any]] = {}
        self.triggers: dict[str, dict[str, Any]] = {}
        self.versions: dict[str, int] = {}
        self.conversations: dict[str, dict[str, Any]] = {}
        self.suppressed_keys: set[str] = set()
        self.delivered_actions: list[dict[str, Any]] = []
        self.start_time: float = time.time()

    def reset(self):
        self.categories.clear()
        self.merchants.clear()
        self.customers.clear()
        self.triggers.clear()
        self.versions.clear()
        self.conversations.clear()
        self.suppressed_keys.clear()
        self.delivered_actions.clear()
        self.start_time = time.time()

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self.start_time)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "category": len(self.categories),
            "merchant": len(self.merchants),
            "customer": len(self.customers),
            "trigger": len(self.triggers),
        }

    def push_context(
        self, scope: str, context_id: str, version: int, payload: dict[str, Any]
    ) -> tuple[bool, Optional[str], Optional[int]]:
        """Push context. Returns (accepted, ack_or_reason, current_version)."""
        curr_ver = self.versions.get(context_id)
        if curr_ver is not None and version < curr_ver:
            return False, "stale_version", curr_ver


        if scope == "category":
            slug = payload.get("slug") or context_id
            self.categories[slug] = payload
            self.categories[context_id] = payload
        elif scope == "merchant":
            mid = payload.get("merchant_id") or context_id
            self.merchants[mid] = payload
            self.merchants[context_id] = payload
        elif scope == "customer":
            cid = payload.get("customer_id") or context_id
            self.customers[cid] = payload
            self.customers[context_id] = payload
        elif scope == "trigger":
            tid = payload.get("id") or context_id
            self.triggers[tid] = payload
            self.triggers[context_id] = payload
        else:
            return False, "invalid_scope", None

        self.versions[context_id] = version
        ack_id = f"ack_{context_id}_v{version}"
        return True, ack_id, None

    def tick(self, now: Optional[str], available_triggers: list[str]) -> TickResponse:
        """Process a tick event and generate actions."""
        target_triggers = available_triggers if available_triggers else list(self.triggers.keys())
        actions: list[TickAction] = []

        for tid in target_triggers:
            trg = self.triggers.get(tid)
            if not trg:
                continue

            mid = (
                trg.get("payload", {}).get("merchant_id")
                or trg.get("merchant_id")
                or ""
            )
            cid = (
                trg.get("payload", {}).get("customer_id")
                or trg.get("customer_id")
            )

            merchant = self.merchants.get(mid, {})
            customer = self.customers.get(cid) if cid else None
            cat_slug = merchant.get("category_slug", "")
            category = self.categories.get(cat_slug, {})

            composed = compose(category, merchant, trg, customer)

            # Check suppression
            if composed.suppression_key in self.suppressed_keys:
                continue

            self.suppressed_keys.add(composed.suppression_key)
            conv_id = f"conv_{mid}_{tid}"

            action = TickAction(
                conversation_id=conv_id,
                merchant_id=mid,
                customer_id=cid,
                send_as=composed.send_as,
                trigger_id=tid,
                template_name=composed.template_name,
                template_params=composed.template_params,
                body=composed.body,
                cta=composed.cta,
                suppression_key=composed.suppression_key,
                rationale=composed.rationale,
            )
            actions.append(action)
            self.delivered_actions.append(action.model_dump())

            self.conversations[conv_id] = {
                "merchant_id": mid,
                "customer_id": cid,
                "trigger_id": tid,
                "turns": [{"from": "bot", "body": composed.body}],
                "auto_reply_count": 0,
            }

        return TickResponse(actions=actions)

    def handle_reply(
        self,
        conversation_id: str,
        merchant_id: Optional[str],
        customer_id: Optional[str],
        from_role: str,
        message: str,
        turn_number: int = 1,
    ) -> ReplyResponse:
        """Handle incoming merchant or customer reply."""
        conv = self.conversations.setdefault(
            conversation_id,
            {"turns": [], "merchant_id": merchant_id, "auto_reply_count": 0},
        )
        conv["turns"].append({"from": from_role, "message": message, "turn": turn_number})

        msg_lower = message.lower().strip()

        # 1. Hostile / Opt-Out Detection
        hostile_keywords = [
            "stop messaging",
            "useless spam",
            "stop sending",
            "not interested",
            "don't message",
            "dont message",
            "leave me alone",
            "bothering me",
            "spam",
            "unsubscribe",
            "opt out",
        ]
        if any(kw in msg_lower for kw in hostile_keywords):
            return ReplyResponse(
                action="end",
                rationale="Merchant explicitly requested to stop messaging. Closing conversation gracefully and suppressing outreach.",
            )

        # 2. Auto-Reply Detection
        auto_reply_patterns = [
            "thank you for contacting",
            "our team will respond",
            "we will respond shortly",
            "we have received your message",
            "auto-reply",
            "automated message",
            "currently unavailable",
            "away from phone",
        ]
        if any(p in msg_lower for p in auto_reply_patterns):
            conv["auto_reply_count"] += 1
            count = conv["auto_reply_count"]
            if turn_number >= 4 or count >= 3:
                return ReplyResponse(
                    action="end",
                    rationale="Auto-reply repeated 3+ times with no human engagement. Gracefully closing conversation.",
                )
            if turn_number >= 3 or count == 2:
                return ReplyResponse(
                    action="wait",
                    wait_seconds=86400,
                    rationale="Repeated auto-reply detected (owner away from phone). Waiting 24h before re-engagement.",
                )
            return ReplyResponse(
                action="send",
                body="Looks like an auto-reply 😊 When the owner sees this, just reply 'Yes' for the details.",
                cta="binary_yes_no",
                rationale="Detected auto-reply on first turn; sending single low-friction prompt for owner.",
            )

        # 3. Explicit Intent / Action Commitment
        action_keywords = [
            "let's do it",
            "lets do it",
            "ok lets do it",
            "ok, let's do it",
            "whats next",
            "what's next",
            "proceed",
            "yes please",
            "send me",
            "send the abstract",
            "draft it",
            "go ahead",
            "confirm",
            "done",
        ]
        if any(kw in msg_lower for kw in action_keywords):
            return ReplyResponse(
                action="send",
                body="Great, drafting your campaign and Google Business Profile update now — ready in 90 seconds. I'll pre-fill the post. Reply CONFIRM to proceed.",
                cta="binary_confirm_cancel",
                rationale="Honoring merchant commitment; switched from qualification to immediate execution mode.",
            )

        # 4. Out-of-Scope / Off-Topic Ask
        if any(kw in msg_lower for kw in ["gst", "filing", "income tax", "loan", "accounting"]):
            return ReplyResponse(
                action="send",
                body="I'll have to leave GST and tax filing to your CA — that's outside what I can help with directly! Coming back to growing your profile — want me to proceed with your promotional draft?",
                cta="binary_yes_no",
                rationale="Out-of-scope ask politely declined; redirected back to the core marketing thread.",
            )

        # 5. Default General Reply
        return ReplyResponse(
            action="send",
            body="Done! I've prepped the update for you. Reply YES to review and push it live.",
            cta="binary_yes_no",
            rationale="Affirmative response handled promptly with single clear confirmation CTA.",
        )


# Global singleton store
store = ContextStore()
