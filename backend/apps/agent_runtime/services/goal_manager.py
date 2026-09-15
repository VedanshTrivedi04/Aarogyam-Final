"""
Goal Manager
============
Creates/tracks AgentGoal rows — what an agent is trying to accomplish for
a patient, instead of just reacting to one event.
"""

from django.utils import timezone

from apps.agent_runtime.models import AgentGoal


def get_or_create_active(agent_name: str, patient_id: str, goal_type: str, description: str = "",
                          priority: str = AgentGoal.Priority.MEDIUM) -> AgentGoal:
    """
    Reuse an already-ACTIVE goal of this type for this patient instead of
    spawning a duplicate every time the same risk pattern is observed.
    """
    goal = AgentGoal.objects.filter(
        agent_name=agent_name, patient_id=patient_id, goal_type=goal_type, status=AgentGoal.Status.ACTIVE
    ).first()
    if goal:
        return goal
    return AgentGoal.objects.create(
        agent_name=agent_name,
        patient_id=patient_id,
        goal_type=goal_type,
        description=description,
        priority=priority,
        status=AgentGoal.Status.ACTIVE,
    )


def complete(goal: AgentGoal) -> None:
    goal.status = AgentGoal.Status.COMPLETED
    goal.completed_at = timezone.now()
    goal.save(update_fields=["status", "completed_at", "updated_at"])


def abandon(goal: AgentGoal) -> None:
    goal.status = AgentGoal.Status.ABANDONED
    goal.completed_at = timezone.now()
    goal.save(update_fields=["status", "completed_at", "updated_at"])
