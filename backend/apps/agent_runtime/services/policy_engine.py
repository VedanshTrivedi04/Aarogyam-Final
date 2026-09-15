"""
Policy Engine
=============
Decides which tool calls an agent may execute automatically vs which
require human approval. See Section 11 of the architecture doc.
"""

from enum import Enum


class Policy(str, Enum):
    ALLOWED = "ALLOWED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"


# AI Agent (Phase 2) never touches prescriptions, dosage, or medication
# start/stop — every tool it has today is auto-allowed. Pharmacy Agent tools
# that are read-only or just notify are auto-allowed too; create_refill_order
# is handled specially below (doc Section 21: routine refill can auto-execute
# only if conditions are met, otherwise it needs approval).
TOOL_POLICY = {
    "send_reminder": Policy.ALLOWED,
    "send_notification": Policy.ALLOWED,
    "request_caregiver_alert": Policy.ALLOWED,
    "create_doctor_review": Policy.ALLOWED,
    "track_order": Policy.ALLOWED,
    "search_pharmacies": Policy.ALLOWED,
    "request_refill_approval": Policy.ALLOWED,
}

# Tools whose policy depends on the situation, not just the tool name. Each
# entry is (tool_name, condition) — condition receives the `context` dict
# passed to check() and returns True when the action may run automatically.
_CONDITIONAL_POLICY = {
    "create_refill_order": lambda ctx: bool(
        ctx.get("auto_refill_enabled")
        and ctx.get("prescription_active")
        and not ctx.get("quantity_unusual")
    ),
}


def check(tool_name: str, context: dict | None = None) -> Policy:
    """Unknown tools default to REQUIRES_APPROVAL — fail safe, not fail open.

    `context` is optional and only consulted for tools in
    _CONDITIONAL_POLICY; every existing caller that omits it keeps resolving
    purely from the static TOOL_POLICY map, unchanged."""
    if context is not None and tool_name in _CONDITIONAL_POLICY:
        return Policy.ALLOWED if _CONDITIONAL_POLICY[tool_name](context) else Policy.REQUIRES_APPROVAL
    return TOOL_POLICY.get(tool_name, Policy.REQUIRES_APPROVAL)
