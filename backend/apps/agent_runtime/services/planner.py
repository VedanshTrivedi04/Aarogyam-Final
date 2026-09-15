"""
Planner
=======
Records the plan the reasoning engine decided on as an AgentPlan row, so
even a single-step decision is auditable and future multi-step plans (the
doc's Section 7 example) fit the same model without a schema change.
"""

from apps.agent_runtime.models import AgentGoal, AgentPlan


def record(goal: AgentGoal, chosen_tool: dict | None) -> AgentPlan:
    steps = [chosen_tool] if chosen_tool else []
    return AgentPlan.objects.create(
        goal=goal,
        steps=steps,
        current_step=0,
        status=AgentPlan.Status.PENDING if steps else AgentPlan.Status.DONE,
    )


def mark_step_done(plan: AgentPlan) -> None:
    plan.current_step += 1
    plan.status = AgentPlan.Status.DONE
    plan.save(update_fields=["current_step", "status", "updated_at"])


def mark_failed(plan: AgentPlan) -> None:
    plan.status = AgentPlan.Status.FAILED
    plan.save(update_fields=["status", "updated_at"])
