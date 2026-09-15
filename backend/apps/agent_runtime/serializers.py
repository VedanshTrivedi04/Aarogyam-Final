"""
apps/agent_runtime/serializers.py
"""
from rest_framework import serializers

from apps.agent_runtime.models import AgentAction, AgentOutcome


class AgentOutcomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentOutcome
        fields = ["success", "outcome", "evaluation", "evaluated_at"]


class AgentActionSerializer(serializers.ModelSerializer):
    goal_type = serializers.CharField(source="goal.goal_type", default=None, read_only=True)
    outcome = AgentOutcomeSerializer(read_only=True)

    class Meta:
        model = AgentAction
        fields = [
            "id",
            "goal_type",
            "agent_name",
            "tool_name",
            "input",
            "output",
            "status",
            "created_at",
            "outcome",
        ]
