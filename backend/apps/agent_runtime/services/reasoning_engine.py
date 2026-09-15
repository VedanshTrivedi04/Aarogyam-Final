"""
Reasoning Engine
================
Gathers context (risk score + SHAP reasons + adherence summary + past
intervention memory), asks Groq what to do, and returns the tool call(s)
it decided on. This is the "why" layer sitting on top of the existing
XGBoost risk model — the model still produces the prediction; the LLM
reasons over that prediction plus history to decide the right intervention.
"""

import logging

from apps.agent_runtime.services import memory_manager
from apps.agent_runtime.services.llm_client import LLMClient
from apps.agent_runtime.services.tool_registry import TOOL_SCHEMAS, get_adherence_summary, get_risk_score

logger = logging.getLogger("medadhere.agent_runtime.reasoning")

SYSTEM_PROMPT = """You are the Aarogyam Adherence Intervention Agent, part of a medication \
adherence app. Your job: decide the single most appropriate next action to help one \
specific patient take their medication, based on their AI risk score, SHAP explanation, \
recent adherence history, and what has (or hasn't) worked for them before.

Rules:
- Prefer the least intrusive effective action. Start gentle (send_notification), escalate \
(send_reminder) only if risk is elevated or gentler nudges already failed, escalate to \
caregivers only if patient-facing actions have failed before or risk is high/critical, and \
only flag a doctor review if risk stays critical despite escalation or you suspect a \
clinical (not just behavioral) cause.
- You may call at most one tool. If no action is warranted (patient's risk is low and \
stable), do not call any tool.
- You NEVER decide on medication, dosage, or prescription changes — that is out of scope \
for you entirely.
- Keep any message/reason/summary text short, specific to this patient's actual pattern \
(e.g. mention which time of day or day of week if that's the driver), and non-alarming for \
patient-facing text."""


def decide_action(patient_id: str, agent_name: str) -> dict:
    """
    Returns:
        {
            "risk": <risk_score dict from RiskEngine>,
            "llm_result": <LLMResult>,
            "chosen_tool": {"name": str, "arguments": dict} | None,
        }
    """
    risk = get_risk_score(patient_id)
    adherence = get_adherence_summary(patient_id)
    memory_summary = memory_manager.summarize_for_prompt(agent_name, patient_id)

    user_prompt = (
        f"Patient ID: {patient_id}\n"
        f"Current risk score: {risk.get('risk_score')} ({risk.get('risk_level')})\n"
        f"Why the model thinks this: {risk.get('reasons')}\n"
        f"Last 90 days: {adherence.get('taken')} doses taken, {adherence.get('missed')} missed "
        f"out of {adherence.get('total_events')} scheduled.\n"
        f"{memory_summary}\n\n"
        "Decide the single best next action for this patient, or take no action if none is "
        "warranted."
    )

    result = LLMClient.reason_with_tools(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        tools=TOOL_SCHEMAS,
    )

    # The Groq HTTP call can take a few seconds; cloud Postgres (Neon) closes
    # idle connections aggressively, and a bare management command / Celery
    # task doesn't get Django's automatic per-request connection health
    # check. Explicitly refresh here so every DB call after this point
    # (planner, action_executor, ...) gets a live connection instead of
    # failing with "the connection is closed".
    from django.db import close_old_connections
    close_old_connections()

    chosen = None
    if result.success and result.tool_calls:
        first = result.tool_calls[0]
        args = dict(first.arguments)
        args.setdefault("patient_id", patient_id)
        chosen = {"name": first.name, "arguments": args}

    return {"risk": risk, "llm_result": result, "chosen_tool": chosen}
