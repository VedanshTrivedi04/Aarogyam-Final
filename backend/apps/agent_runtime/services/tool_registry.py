"""
Tool Registry
=============
Everything the Agentic AI Agent can do, split into two kinds:

- Read helpers (get_risk_score, get_adherence_summary): call
  apps.ai_engine directly — read-only, safe, used to build the LLM's
  context up front rather than as LLM-callable tools (cheaper and more
  reliable than round-tripping reads through tool calls).

- Action tools (the ones in TOOL_SCHEMAS, callable by the LLM): go through
  the EXISTING agent system via AgentRegistry — never a raw import of
  another agent's business logic — matching the "no direct agent-to-agent
  calls" rule the rest of agenthandover.py follows. We resolve + invoke the
  target agent's method directly (the same primitive
  AgentOrchestrator._safe_call uses internally) rather than routing through
  orchestrator.handover()'s static per-event routing table, because the LLM
  picks which tool to call per-situation — that's inherently not the fixed
  event-to-handler mapping the shared table is designed for. Every call is
  still logged as an auditable AgentAction row by action_executor.py.
"""

import logging
from typing import Optional

logger = logging.getLogger("medadhere.agent_runtime.tools")


# ── Context helpers (not LLM tools — used to build the reasoning prompt) ──


def get_risk_score(patient_id: str) -> dict:
    from apps.ai_engine.services.risk_engine import RiskEngine
    return RiskEngine.get_risk_score(patient_id)


def get_adherence_summary(patient_id: str) -> dict:
    from apps.ai_engine.services.risk_engine import _fetch_patient_data
    events_df, _, _, _ = _fetch_patient_data(patient_id)
    if events_df.empty:
        return {"total_events": 0, "missed": 0, "taken": 0}
    taken_statuses = {"TAKEN", "TAKEN_LATE", "TAKEN_EARLY"}
    taken = int(events_df["status"].isin(taken_statuses).sum())
    missed = int((events_df["status"] == "MISSED").sum())
    return {"total_events": int(len(events_df)), "missed": missed, "taken": taken}


def _resolve_user_id(patient_id: str) -> Optional[str]:
    from apps.clinical.models import Patient
    patient = Patient.objects.filter(id=patient_id).only("user_id").first()
    return str(patient.user_id) if patient else None


# ── Action tools (LLM-callable) ────────────────────────────────────────────


def send_notification(patient_id: str, message: str, urgency: str = "medium") -> dict:
    from agenthandover import AgentName, AgentRegistry, HandoverPayload

    user_id = _resolve_user_id(patient_id)
    if not user_id:
        return {"error": "patient_or_user_not_found"}
    agent = AgentRegistry.get(AgentName.NOTIFICATION)
    payload = HandoverPayload(
        patient_id=patient_id,
        user_id=user_id,
        data={"type": "AI_ADHERENCE_NUDGE", "message": message, "urgency": urgency},
    )
    return agent.dispatch(payload)


def send_reminder(patient_id: str, urgency: str = "medium") -> dict:
    """A stronger, explicit reminder — same delivery path as send_notification
    but tagged distinctly so channel/copy selection can differ later without
    changing this tool's contract."""
    from agenthandover import AgentName, AgentRegistry, HandoverPayload

    user_id = _resolve_user_id(patient_id)
    if not user_id:
        return {"error": "patient_or_user_not_found"}
    agent = AgentRegistry.get(AgentName.NOTIFICATION)
    payload = HandoverPayload(
        patient_id=patient_id,
        user_id=user_id,
        data={"type": "AI_ADHERENCE_REMINDER", "urgency": urgency},
    )
    return agent.dispatch(payload)


def request_caregiver_alert(patient_id: str, reason: str) -> dict:
    from agenthandover import AgentName, AgentRegistry, HandoverPayload

    risk = get_risk_score(patient_id)
    agent = AgentRegistry.get(AgentName.CAREGIVER)
    payload = HandoverPayload(
        patient_id=patient_id,
        data={
            "risk_level": risk.get("risk_level"),
            "risk_score": risk.get("risk_score"),
            "reasons": (risk.get("reasons") or []) + ([reason] if reason else []),
        },
    )
    return agent.send_high_risk_alert_to_caregivers(payload)


def create_doctor_review(patient_id: str, summary: str) -> dict:
    from agenthandover import AgentRegistry, HandoverPayload
    from medadhere_extensions_handover import DOCTOR_AGENT

    risk = get_risk_score(patient_id)
    agent = AgentRegistry.get(DOCTOR_AGENT)
    payload = HandoverPayload(
        patient_id=patient_id,
        data={
            "risk_level": (risk.get("risk_level") or "high").upper(),
            "patient_name": summary[:200],
            "missed_doses": None,
        },
    )
    return agent.alert_doctor_high_risk(payload)


TOOLS = {
    "send_reminder": send_reminder,
    "send_notification": send_notification,
    "request_caregiver_alert": request_caregiver_alert,
    "create_doctor_review": create_doctor_review,
}


# OpenAI/Groq tool-calling schema — the vocabulary the LLM chooses from.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": (
                "Send a gentle adherence nudge notification to the patient "
                "through their preferred channel. Use for early-stage or "
                "low/medium risk situations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "message": {
                        "type": "string",
                        "description": "Short, patient-friendly nudge message",
                    },
                    "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["patient_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_reminder",
            "description": (
                "Send a stronger, explicit reminder to the patient. Use "
                "when risk is elevated or a gentle nudge already failed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_caregiver_alert",
            "description": (
                "Escalate to the patient's caregivers. Use when "
                "patient-facing reminders have not worked before and risk "
                "remains high or critical."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "reason": {
                        "type": "string",
                        "description": "Why escalation is needed now",
                    },
                },
                "required": ["patient_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_doctor_review",
            "description": (
                "Flag this patient for doctor review. Use when risk stays "
                "critical despite reminders and caregiver escalation, or a "
                "clinical concern (not just forgetfulness) is suspected."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "summary": {
                        "type": "string",
                        "description": "One-sentence clinical summary for the doctor",
                    },
                },
                "required": ["patient_id", "summary"],
            },
        },
    },
]
