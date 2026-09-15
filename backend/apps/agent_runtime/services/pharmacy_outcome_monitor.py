"""
Pharmacy Outcome Monitor
========================
Checks whether an executed refill action actually worked — did the order
get delivered? — and records the result so future reasoning passes can
learn from it. Mirrors outcome_monitor.py's shape, but judges success by
RefillOrder delivery status instead of the next dose being taken.
"""

import logging

from django.utils import timezone

from apps.agent_runtime.models import AgentAction, AgentOutcome
from apps.agent_runtime.services import memory_manager
from apps.agent_runtime.services.tool_registry import get_prescription_stock

logger = logging.getLogger("medadhere.agent_runtime.pharmacy_outcome")

TERMINAL_FAILURE_STATUSES = {"FAILED", "CANCELLED"}
STILL_IN_PROGRESS_STATUSES = {"PENDING", "PARTNER_CONFIRMED", "DISPATCHED"}


def schedule_check(action: AgentAction, stock_before: dict) -> AgentOutcome:
    """Create a pending outcome row right after a refill action executes."""
    return AgentOutcome.objects.create(
        action=action,
        metric_before={
            "remaining_quantity": stock_before.get("remaining_quantity"),
            "days_remaining": stock_before.get("days_remaining"),
        },
        success=None,
    )


def evaluate(outcome: AgentOutcome) -> AgentOutcome:
    """
    Never raises. Looks up the RefillOrder created by the action (via
    action.output["order_id"]) and judges success by its delivery status.
    """
    action = outcome.action
    order_id = (action.output or {}).get("order_id")
    if not order_id:
        outcome.evaluation = "no_order_id_on_action"
        outcome.evaluated_at = timezone.now()
        outcome.save(update_fields=["evaluation", "evaluated_at", "updated_at"])
        return outcome

    try:
        from apps.pharmacy.models import RefillOrder

        order = RefillOrder.objects.filter(id=order_id).first()
        if order is None:
            outcome.evaluation = "refill_order_not_found"
        elif order.status == "DELIVERED":
            outcome.success = True
            outcome.evaluation = "order_delivered"
        elif order.status in TERMINAL_FAILURE_STATUSES:
            outcome.success = False
            outcome.evaluation = f"order_status={order.status}"
        elif order.status in STILL_IN_PROGRESS_STATUSES:
            outcome.success = None
            outcome.evaluation = f"order_status={order.status}"
        else:
            outcome.evaluation = f"order_status={order.status}"

        if order is not None:
            after = get_prescription_stock(str(order.prescription_id))
            outcome.metric_after = {
                "remaining_quantity": after.get("remaining_quantity"),
                "days_remaining": after.get("days_remaining"),
            }
    except Exception as e:
        logger.error(f"Refill outcome evaluation failed for action {action.id}: {e}")
        outcome.evaluation = f"evaluation_error: {e}"
    finally:
        outcome.evaluated_at = timezone.now()
        outcome.save(update_fields=["success", "evaluation", "metric_after", "evaluated_at", "updated_at"])

    if outcome.success is not None:
        memory_manager.remember(
            agent_name=action.agent_name,
            patient_id=str(action.goal.patient_id) if action.goal_id else str(action.input.get("patient_id")),
            memory_type="REFILL_OUTCOME",
            content={
                "tool_name": action.tool_name,
                "outcome": "delivered" if outcome.success else "failed_or_cancelled",
            },
            importance=0.6 if outcome.success else 0.8,
            confidence=0.7,
        )

    return outcome
