"""
Pharmacy Pipeline
=================
The full Observe -> Reason -> Plan -> Act -> Observe Outcome loop for the
Pharmacy Agent, wired from the individual runtime services. Mirrors
pipeline.py's run_adherence_intervention, but for refills — this is what
apps.agent_runtime.tasks.evaluate_refill_needed and the agent_test_refill
management command call. Deliberately not wired into the live
REFILL_THRESHOLD_REACHED event yet — see the architecture doc; run this
manually via agent_test_refill until that follow-up is done.
"""

import logging

from apps.agent_runtime.models import AgentAction
from apps.agent_runtime.services import goal_manager, pharmacy_outcome_monitor, pharmacy_reasoning_engine, planner
from apps.agent_runtime.services.action_executor import execute

logger = logging.getLogger("medadhere.agent_runtime.pharmacy_pipeline")

GOAL_TYPE_PREVENT_STOCKOUT = "PREVENT_STOCKOUT"
OUTCOME_CHECK_DELAY_SECONDS = 24 * 60 * 60  # 24h — delivery takes hours/days, not minutes


def run_pharmacy_refill(
    prescription_id: str,
    patient_id: str,
    agent_name: str = "PharmacyAgent",
    trace_id: str = "",
    dry_run: bool = False,
) -> dict:
    """Never raises — any failure is captured in the returned summary dict."""
    try:
        goal = goal_manager.get_or_create_active(
            agent_name=agent_name,
            patient_id=patient_id,
            goal_type=GOAL_TYPE_PREVENT_STOCKOUT,
            description="Prevent medication stockout for this prescription",
        )

        decision = pharmacy_reasoning_engine.decide_action(prescription_id, agent_name)
        plan = planner.record(goal, decision["chosen_tool"])

        summary = {
            "goal_id": str(goal.id),
            "plan_id": str(plan.id),
            "remaining_quantity": decision["stock"].get("remaining_quantity"),
            "days_remaining": decision["stock"].get("days_remaining"),
            "llm_success": decision["llm_result"].success,
            "llm_error": decision["llm_result"].error,
            "action_taken": False,
            "action_id": None,
            "tool_name": None,
            "action_status": None,
        }

        if decision["chosen_tool"] is None:
            logger.info(f"No refill action warranted for prescription {prescription_id}")
            return summary

        tool = decision["chosen_tool"]
        policy_context = {
            "auto_refill_enabled": decision["pharmacy_context"].get("auto_refill_enabled", False),
            "prescription_active": decision["stock"].get("is_active", False),
            "quantity_unusual": False,
        }
        action = execute(
            goal=goal,
            agent_name=agent_name,
            tool_name=tool["name"],
            tool_input=tool["arguments"],
            trace_id=trace_id,
            dry_run=dry_run,
            policy_context=policy_context,
        )

        summary.update(
            {
                "action_taken": True,
                "action_id": str(action.id),
                "tool_name": action.tool_name,
                "action_status": action.status,
            }
        )

        if action.status == AgentAction.Status.FAILED:
            planner.mark_failed(plan)
        else:
            planner.mark_step_done(plan)

        if (
            action.status == AgentAction.Status.EXECUTED
            and not dry_run
            and action.tool_name == "create_refill_order"
            and "order_id" in (action.output or {})
        ):
            outcome = pharmacy_outcome_monitor.schedule_check(action, decision["stock"])
            summary["outcome_id"] = str(outcome.id)
            from apps.agent_runtime.tasks import check_refill_outcome
            check_refill_outcome.apply_async(
                args=[str(outcome.id)], countdown=OUTCOME_CHECK_DELAY_SECONDS
            )

        return summary

    except Exception as e:
        logger.error(f"Pharmacy refill pipeline failed for prescription {prescription_id}: {e}")
        return {"error": str(e)}
