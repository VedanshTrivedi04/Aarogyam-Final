from django.contrib import admin

from apps.agent_runtime.models import (
    AgentAction,
    AgentApproval,
    AgentGoal,
    AgentMemory,
    AgentOutcome,
    AgentPlan,
)


@admin.register(AgentGoal)
class AgentGoalAdmin(admin.ModelAdmin):
    list_display = ("id", "agent_name", "patient_id", "goal_type", "priority", "status", "created_at")
    list_filter = ("agent_name", "goal_type", "priority", "status")
    search_fields = ("patient_id",)


@admin.register(AgentPlan)
class AgentPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "goal", "current_step", "status", "created_at")
    list_filter = ("status",)


@admin.register(AgentAction)
class AgentActionAdmin(admin.ModelAdmin):
    list_display = ("id", "agent_name", "tool_name", "status", "trace_id", "created_at")
    list_filter = ("agent_name", "tool_name", "status")
    search_fields = ("trace_id",)


@admin.register(AgentMemory)
class AgentMemoryAdmin(admin.ModelAdmin):
    list_display = ("id", "agent_name", "patient_id", "memory_type", "importance", "confidence", "created_at")
    list_filter = ("agent_name", "memory_type")
    search_fields = ("patient_id",)


@admin.register(AgentOutcome)
class AgentOutcomeAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "success", "evaluated_at", "created_at")
    list_filter = ("success",)


@admin.register(AgentApproval)
class AgentApprovalAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "approval_type", "status", "approved_by", "approved_at")
    list_filter = ("status", "approval_type")
