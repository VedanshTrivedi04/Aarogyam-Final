"""
Pharmacy Reasoning Engine
=========================
Gathers stock/prescription/pharmacy-preference context, asks Groq what to
do about it, and returns the tool call it decided on. Mirrors
reasoning_engine.py's shape (same decide_action contract) but with its own
prompt and tool vocabulary — the Pharmacy Agent must never touch dosage,
prescriptions, or medication choice, only refill logistics.
"""

import logging

from apps.agent_runtime.services import memory_manager
from apps.agent_runtime.services.llm_client import LLMClient
from apps.agent_runtime.services.tool_registry import (
    PHARMACY_TOOL_SCHEMAS,
    get_active_refill_orders,
    get_pharmacy_context,
    get_prescription_stock,
)

logger = logging.getLogger("medadhere.agent_runtime.pharmacy_reasoning")

SYSTEM_PROMPT = """You are the Aarogyam Pharmacy Agent, part of a medication \
adherence app. Your job: decide the single most appropriate next action to keep \
one specific patient's prescription stocked, based on their current remaining \
quantity, daily dose count, pharmacy preferences, and any refill already in \
progress.

Rules:
- Prefer create_refill_order when stock is low (days_remaining at or below \
refill_alert_days), auto-refill is enabled, a pharmacy partner is available, \
and no refill order is already in progress.
- Prefer search_pharmacies when stock is low but the patient has no preferred \
pharmacy partner set.
- Prefer request_refill_approval when auto-refill is disabled, or the \
situation is otherwise unclear and a human should confirm before anything is \
ordered.
- Prefer track_order instead of creating a new order when a refill is already \
in progress for this prescription.
- You may call at most one tool. If stock is healthy (well above \
refill_alert_days) and no refill is in progress, do not call any tool.
- You NEVER decide on medication substitution, dosage, or prescription \
changes — that is out of scope for you entirely.
- Keep any message/reason text short, specific to this patient's actual \
situation, and non-alarming for patient-facing text."""


def decide_action(prescription_id: str, agent_name: str = "PharmacyAgent") -> dict:
    """
    Returns:
        {
            "stock": <get_prescription_stock dict>,
            "pharmacy_context": <get_pharmacy_context dict>,
            "llm_result": <LLMResult>,
            "chosen_tool": {"name": str, "arguments": dict} | None,
        }
    """
    stock = get_prescription_stock(prescription_id)
    patient_id = stock.get("patient_id")

    pharmacy_context = get_pharmacy_context(patient_id) if patient_id else {"has_integration": False}
    active_orders = get_active_refill_orders(prescription_id)
    memory_summary = memory_manager.summarize_for_prompt(agent_name, patient_id) if patient_id else ""

    user_prompt = (
        f"Prescription ID: {prescription_id}\n"
        f"Patient ID: {patient_id}\n"
        f"Medication: {stock.get('medication_name')}\n"
        f"Remaining quantity: {stock.get('remaining_quantity')} "
        f"({stock.get('doses_per_day')} doses/day, ~{stock.get('days_remaining')} days remaining)\n"
        f"Refill alert threshold: {stock.get('refill_alert_days')} days\n"
        f"Pharmacy integration: {pharmacy_context}\n"
        f"Refill orders already in progress: {active_orders}\n"
        f"{memory_summary}\n\n"
        "Decide the single best next action for this patient's refill, or take "
        "no action if stock is healthy."
    )

    result = LLMClient.reason_with_tools(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        tools=PHARMACY_TOOL_SCHEMAS,
    )

    # See reasoning_engine.decide_action for why this close_old_connections()
    # call is needed after a Groq round trip in a bare Celery task/mgmt command.
    from django.db import close_old_connections
    close_old_connections()

    # Unlike the adherence tool set (all 4 tools take patient_id), pharmacy
    # tools have different signatures — track_order takes neither patient_id
    # nor prescription_id — so only backfill the ids a given tool actually
    # accepts (per its schema in PHARMACY_TOOL_SCHEMAS) rather than blindly
    # injecting both into every call.
    accepted_params_by_tool = {
        schema["function"]["name"]: set(schema["function"]["parameters"]["properties"])
        for schema in PHARMACY_TOOL_SCHEMAS
    }

    chosen = None
    if result.success and result.tool_calls:
        first = result.tool_calls[0]
        args = dict(first.arguments)
        accepted = accepted_params_by_tool.get(first.name, set())
        if "patient_id" in accepted:
            args.setdefault("patient_id", patient_id)
        if "prescription_id" in accepted:
            args.setdefault("prescription_id", prescription_id)
        chosen = {"name": first.name, "arguments": args}

    return {
        "stock": stock,
        "pharmacy_context": pharmacy_context,
        "llm_result": result,
        "chosen_tool": chosen,
    }
