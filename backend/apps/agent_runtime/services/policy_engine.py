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
# start/stop — every tool it has today is auto-allowed. This map is where a
# future Pharmacy/Doctor agent would list tools like "substitute_medication"
# or "place_controlled_refill_order" as REQUIRES_APPROVAL, reusing the same
# ApprovalManager/AgentApproval plumbing without touching it again.
TOOL_POLICY = {
    "send_reminder": Policy.ALLOWED,
    "send_notification": Policy.ALLOWED,
    "request_caregiver_alert": Policy.ALLOWED,
    "create_doctor_review": Policy.ALLOWED,
}


def check(tool_name: str) -> Policy:
    """Unknown tools default to REQUIRES_APPROVAL — fail safe, not fail open."""
    return TOOL_POLICY.get(tool_name, Policy.REQUIRES_APPROVAL)
