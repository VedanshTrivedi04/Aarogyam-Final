"""
Outcome Monitor
===============
Checks whether an executed intervention actually worked — did the patient
take their next scheduled dose after we nudged/reminded/escalated? — and
records the result so future reasoning passes can learn from it.

Uses apps.scheduling.models.ReminderJob (the same data source
apps.ai_engine.services.risk_engine reads adherence from) rather than
apps.telemetry.AdherenceEvent, which agenthandover.py's AdherenceAgent
references but which observed real patient data did not populate reliably.
"""

import logging

from django.utils import timezone

from apps.agent_runtime.models import AgentAction, AgentOutcome
from apps.agent_runtime.services import memory_manager

logger = logging.getLogger("medadhere.agent_runtime.outcome")


def schedule_check(action: AgentAction, risk_before: dict) -> AgentOutcome:
    """Create a pending outcome row right after an action executes."""
    return AgentOutcome.objects.create(
        action=action,
        metric_before={
            "risk_score": risk_before.get("risk_score"),
            "risk_level": risk_before.get("risk_level"),
        },
        success=None,
    )


def evaluate(outcome: AgentOutcome) -> AgentOutcome:
    """
    Never raises. Looks at the patient's ReminderJob history since the
    action was taken: if a dose was scheduled after the action and its
    status is a "taken" status, the intervention is judged successful.
    """
    action = outcome.action
    patient_id = action.goal.patient_id if action.goal_id else action.input.get("patient_id")
    if not patient_id:
        outcome.evaluation = "no_patient_id_on_action"
        outcome.evaluated_at = timezone.now()
        outcome.save(update_fields=["evaluation", "evaluated_at", "updated_at"])
        return outcome

    try:
        from apps.scheduling.models import ReminderJob

        next_dose = (
            ReminderJob.objects.filter(
                schedule__prescription__patient_id=patient_id,
                scheduled_at__gte=action.created_at,
                deleted_at__isnull=True,
            )
            .exclude(status="PENDING")
            .order_by("scheduled_at")
            .first()
        )

        taken_statuses = {"TAKEN", "TAKEN_LATE", "TAKEN_EARLY"}
        if next_dose is None:
            outcome.success = None
            outcome.evaluation = "no_resolved_dose_yet"
        else:
            outcome.success = next_dose.status in taken_statuses
            outcome.evaluation = f"next_dose_status={next_dose.status}"

        from apps.ai_engine.services.risk_engine import RiskEngine
        after = RiskEngine.get_risk_score(str(patient_id))
        outcome.metric_after = {
            "risk_score": after.get("risk_score"),
            "risk_level": after.get("risk_level"),
        }
    except Exception as e:
        logger.error(f"Outcome evaluation failed for action {action.id}: {e}")
        outcome.evaluation = f"evaluation_error: {e}"
    finally:
        outcome.evaluated_at = timezone.now()
        outcome.save(update_fields=["success", "evaluation", "metric_after", "evaluated_at", "updated_at"])

    if outcome.success is not None:
        memory_manager.remember(
            agent_name=action.agent_name,
            patient_id=str(patient_id),
            memory_type="INTERVENTION_OUTCOME",
            content={
                "tool_name": action.tool_name,
                "outcome": "worked" if outcome.success else "did_not_work",
            },
            importance=0.6 if outcome.success else 0.8,
            confidence=0.7,
        )

    return outcome
