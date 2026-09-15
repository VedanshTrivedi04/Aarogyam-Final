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


# ── Pharmacy context helpers (not LLM tools) ───────────────────────────────


def _doses_per_day(prescription) -> int:
    """Real per-day dose count, summed from the prescription's active
    MedicationSchedule.times_of_day (e.g. [{"time": "08:00", "dose": 1.0}, ...]).
    Defaults to 1 if no active schedule exists — never raises."""
    from apps.clinical.models import MedicationSchedule

    total = 0.0
    for schedule in MedicationSchedule.objects.filter(prescription=prescription, is_active=True):
        for entry in (schedule.times_of_day or []):
            total += float(entry.get("dose", 1) or 1)
    return int(total) if total > 0 else 1


def get_prescription_stock(prescription_id: str) -> dict:
    from apps.clinical.models import Prescription

    prescription = Prescription.objects.select_related("medication").filter(id=prescription_id).first()
    if not prescription:
        return {"error": "prescription_not_found"}

    doses_per_day = _doses_per_day(prescription)
    remaining = prescription.remaining_quantity
    days_remaining = int(remaining // doses_per_day) if remaining is not None else None

    return {
        "prescription_id": str(prescription.id),
        "patient_id": str(prescription.patient_id),
        "medication_name": prescription.medication.name,
        "is_active": prescription.is_active,
        "remaining_quantity": float(remaining) if remaining is not None else None,
        "doses_per_day": doses_per_day,
        "days_remaining": days_remaining,
        "refill_alert_days": prescription.refill_alert_days,
    }


def get_pharmacy_context(patient_id: str) -> dict:
    from apps.pharmacy.models import PharmacyIntegration

    integration = PharmacyIntegration.objects.select_related("preferred_partner").filter(
        patient_id=patient_id
    ).first()
    if not integration:
        return {"has_integration": False, "auto_refill_enabled": False, "preferred_partner": None}

    partner = integration.preferred_partner
    return {
        "has_integration": True,
        "auto_refill_enabled": integration.auto_refill_enabled,
        "preferred_partner": (
            {"id": str(partner.id), "name": partner.name, "slug": partner.slug} if partner else None
        ),
        "has_delivery_address": bool(integration.delivery_address),
    }


def get_active_refill_orders(prescription_id: str) -> list:
    from apps.pharmacy.models import RefillOrder

    qs = RefillOrder.objects.filter(
        prescription_id=prescription_id,
        status__in=["PENDING", "PARTNER_CONFIRMED", "DISPATCHED"],
    ).values("id", "status", "quantity_ordered", "estimated_delivery")
    return [
        {
            "id": str(o["id"]),
            "status": o["status"],
            "quantity_ordered": o["quantity_ordered"],
            "estimated_delivery": o["estimated_delivery"].isoformat() if o["estimated_delivery"] else None,
        }
        for o in qs
    ]


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


# ── Pharmacy action tools (LLM-callable) ───────────────────────────────────


def create_refill_order(patient_id: str, prescription_id: str, quantity: Optional[int] = None,
                         partner_id: Optional[str] = None) -> dict:
    """Places a refill order — mirrors medadhere_extensions_handover.PharmacyAgent
    ._place_refill_order's real logic, but computes quantity from the actual
    MedicationSchedule (see _doses_per_day) instead of the non-existent
    Prescription.dosage_per_day field the old deterministic path references."""
    from django.db import transaction

    from apps.clinical.models import Prescription
    from apps.pharmacy.models import PharmacyIntegration, PharmacyPartner, RefillOrder
    from apps.pharmacy.services import PharmacyAPIService
    from apps.pharmacy.tasks import call_pharmacy_api

    prescription = Prescription.objects.select_related("patient", "medication").filter(
        id=prescription_id
    ).first()
    if not prescription or not prescription.is_active:
        return {"error": "prescription_not_found_or_inactive"}

    if RefillOrder.objects.filter(
        prescription=prescription, status__in=["PENDING", "PARTNER_CONFIRMED", "DISPATCHED"]
    ).exists():
        return {"error": "refill_already_in_progress"}

    partner = None
    if partner_id:
        partner = PharmacyPartner.objects.filter(id=partner_id, is_active=True).first()
    if not partner:
        integration = PharmacyIntegration.objects.select_related("preferred_partner").filter(
            patient_id=patient_id
        ).first()
        partner = integration.preferred_partner if integration else None
    if not partner:
        return {"error": "no_pharmacy_partner_available"}

    final_quantity = quantity or (_doses_per_day(prescription) * 30)

    with transaction.atomic():
        order = RefillOrder.objects.create(
            prescription=prescription,
            patient=prescription.patient,
            partner=partner,
            quantity_ordered=final_quantity,
            status="PENDING",
            auto_triggered=True,
            total_amount=PharmacyAPIService.estimate_cost(partner, prescription.medication, final_quantity),
        )
        call_pharmacy_api.delay(str(order.id))

    return {
        "order_id": str(order.id),
        "partner": partner.name,
        "quantity_ordered": final_quantity,
        "total_amount": str(order.total_amount),
        "status": order.status,
    }


def track_order(order_id: str) -> dict:
    from apps.pharmacy.models import RefillOrder

    order = RefillOrder.objects.filter(id=order_id).first()
    if not order:
        return {"error": "order_not_found"}
    return {
        "order_id": str(order.id),
        "status": order.status,
        "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
    }


def search_pharmacies(patient_id: str) -> dict:
    from apps.pharmacy.models import PharmacyIntegration, PharmacyPartner

    partners = PharmacyPartner.objects.filter(is_active=True)
    integration = PharmacyIntegration.objects.filter(patient_id=patient_id).first()
    state = None
    if integration and integration.delivery_address:
        state = integration.delivery_address.get("state")
    if state:
        matching = [p for p in partners if not p.supported_states or state in p.supported_states]
        if matching:
            partners = matching

    return {
        "partners": [
            {"id": str(p.id), "name": p.name, "slug": p.slug, "avg_delivery_hrs": p.avg_delivery_hrs}
            for p in partners
        ]
    }


def request_refill_approval(patient_id: str, prescription_id: str, reason: str) -> dict:
    from agenthandover import AgentName, AgentRegistry, HandoverPayload

    user_id = _resolve_user_id(patient_id)
    if not user_id:
        return {"error": "patient_or_user_not_found"}
    agent = AgentRegistry.get(AgentName.NOTIFICATION)
    payload = HandoverPayload(
        patient_id=patient_id,
        user_id=user_id,
        prescription_id=prescription_id,
        data={"type": "PHARMACY_REFILL_APPROVAL_NEEDED", "message": reason, "urgency": "medium"},
    )
    return agent.dispatch(payload)


TOOLS = {
    "send_reminder": send_reminder,
    "send_notification": send_notification,
    "request_caregiver_alert": request_caregiver_alert,
    "create_doctor_review": create_doctor_review,
    "create_refill_order": create_refill_order,
    "track_order": track_order,
    "search_pharmacies": search_pharmacies,
    "request_refill_approval": request_refill_approval,
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


# Separate schema list for the Pharmacy Agent's reasoning engine — kept apart
# from TOOL_SCHEMAS so each agent's LLM call only sees its own tool vocabulary
# (the LLM tool_choice="auto" call in llm_client.py passes whichever list its
# caller hands it; TOOLS above stays one shared dispatch table since
# action_executor.py resolves by name regardless of which agent chose it).
PHARMACY_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "create_refill_order",
            "description": (
                "Place a medication refill order with the patient's pharmacy "
                "partner. Use when stock is low, auto-refill is enabled, and "
                "no refill is already in progress."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "prescription_id": {"type": "string"},
                    "quantity": {
                        "type": "integer",
                        "description": "Units to order; omit to use a standard 30-day supply",
                    },
                    "partner_id": {
                        "type": "string",
                        "description": "Pharmacy partner id; omit to use the patient's preferred partner",
                    },
                },
                "required": ["patient_id", "prescription_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "track_order",
            "description": "Check the current status of an existing refill order.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_pharmacies",
            "description": (
                "List available pharmacy partners for the patient. Use when "
                "the patient has no preferred partner set yet."
            ),
            "parameters": {
                "type": "object",
                "properties": {"patient_id": {"type": "string"}},
                "required": ["patient_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_refill_approval",
            "description": (
                "Notify the patient that a refill needs their manual "
                "confirmation. Use when auto-refill is disabled, no partner "
                "is available, or the situation is otherwise unclear."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "prescription_id": {"type": "string"},
                    "reason": {
                        "type": "string",
                        "description": "Short, patient-friendly explanation of why confirmation is needed",
                    },
                },
                "required": ["patient_id", "prescription_id", "reason"],
            },
        },
    },
]
