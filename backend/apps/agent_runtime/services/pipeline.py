"""
Pipeline
========
The full Observe -> Reason -> Plan -> Act -> Observe Outcome loop, wired
from the individual runtime services. This is what
agenthandover.AIAgent.execute_intervention_goal (the orchestrator-facing
entry point) and the agent_test_intervention management command both call.
"""

import logging

from apps.agent_runtime.models import AgentAction
from apps.agent_runtime.services import goal_manager, outcome_monitor, planner, reasoning_engine
from apps.agent_runtime.services.action_executor import execute

logger = logging.getLogger("medadhere.agent_runtime.pipeline")

GOAL_TYPE_IMPROVE_ADHERENCE = "IMPROVE_ADHERENCE"
OUTCOME_CHECK_DELAY_SECONDS = 2 * 60 * 60  # 2 hours — give the next dose window time to resolve


def run_adherence_intervention(
    patient_id: str,
    agent_name: str = "AIAgent",
    trace_id: str = "",
    dry_run: bool = False,
) -> dict:
    """Never raises — any failure is captured in the returned summary dict."""
    try:
        goal = goal_manager.get_or_create_active(
            agent_name=agent_name,
            patient_id=patient_id,
            goal_type=GOAL_TYPE_IMPROVE_ADHERENCE,
            description="Reduce missed doses / improve adherence for this patient",
        )

        decision = reasoning_engine.decide_action(patient_id, agent_name)
        plan = planner.record(goal, decision["chosen_tool"])

        summary = {
            "goal_id": str(goal.id),
            "plan_id": str(plan.id),
            "risk_score": decision["risk"].get("risk_score"),
            "risk_level": decision["risk"].get("risk_level"),
            "llm_success": decision["llm_result"].success,
            "llm_error": decision["llm_result"].error,
            "action_taken": False,
            "action_id": None,
            "tool_name": None,
            "action_status": None,
        }

        if decision["chosen_tool"] is None:
            logger.info(f"No intervention warranted for patient {patient_id}")
            return summary

        tool = decision["chosen_tool"]
        action = execute(
            goal=goal,
            agent_name=agent_name,
            tool_name=tool["name"],
            tool_input=tool["arguments"],
            trace_id=trace_id,
            dry_run=dry_run,
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

        if action.status == AgentAction.Status.EXECUTED and not dry_run:
            outcome = outcome_monitor.schedule_check(action, decision["risk"])
            summary["outcome_id"] = str(outcome.id)
            from apps.agent_runtime.tasks import check_intervention_outcome
            check_intervention_outcome.apply_async(
                args=[str(outcome.id)], countdown=OUTCOME_CHECK_DELAY_SECONDS
            )

        return summary

    except Exception as e:
        logger.error(f"Adherence intervention pipeline failed for {patient_id}: {e}")
        return {"error": str(e)}
