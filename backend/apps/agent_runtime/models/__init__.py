"""
Agent Runtime Models
=====================
Persistent state for the goal-driven Agentic AI layer (Phase 1+2: AI Agent
adherence-intervention pilot). Every goal, plan, action, approval and
outcome is a DB row — this is the audit trail for autonomous agent
behavior, per the "Auditability" requirement in the architecture doc.
"""
import uuid

from django.conf import settings
from django.db import models

from shared.models import BaseModel


class AgentGoal(BaseModel):
    """What an agent is trying to accomplish for a patient."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        ABANDONED = "ABANDONED", "Abandoned"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    agent_name = models.CharField(max_length=50)
    patient_id = models.UUIDField(db_index=True)
    goal_type = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_runtime_goals"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.goal_type} for {self.patient_id} ({self.status})"


class AgentPlan(BaseModel):
    """Ordered steps an agent intends to take to reach a goal."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        DONE = "DONE", "Done"
        FAILED = "FAILED", "Failed"

    goal = models.ForeignKey(AgentGoal, on_delete=models.CASCADE, related_name="plans")
    steps = models.JSONField(default=list)
    current_step = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)

    class Meta:
        db_table = "agent_runtime_plans"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Plan for {self.goal_id} ({self.status})"


class AgentAction(BaseModel):
    """A single tool call the agent made (or attempted)."""

    class Status(models.TextChoices):
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Approval"
        EXECUTED = "EXECUTED", "Executed"
        FAILED = "FAILED", "Failed"
        SKIPPED = "SKIPPED", "Skipped (dry run)"

    goal = models.ForeignKey(
        AgentGoal, on_delete=models.CASCADE, related_name="actions", null=True, blank=True
    )
    agent_name = models.CharField(max_length=50)
    tool_name = models.CharField(max_length=100)
    input = models.JSONField(default=dict)
    output = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EXECUTED)
    trace_id = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        db_table = "agent_runtime_actions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tool_name} ({self.status})"


class AgentMemory(BaseModel):
    """What an agent has learned about a patient from past interventions."""

    agent_name = models.CharField(max_length=50)
    patient_id = models.UUIDField(db_index=True)
    memory_type = models.CharField(max_length=50)
    content = models.JSONField(default=dict)
    importance = models.FloatField(default=0.5)
    confidence = models.FloatField(default=0.5)

    class Meta:
        db_table = "agent_runtime_memories"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.memory_type} for {self.patient_id}"


class AgentOutcome(BaseModel):
    """Whether an executed action actually worked."""

    action = models.OneToOneField(AgentAction, on_delete=models.CASCADE, related_name="outcome")
    outcome = models.CharField(max_length=200, blank=True)
    success = models.BooleanField(null=True)  # null = not yet evaluated
    metric_before = models.JSONField(default=dict, blank=True)
    metric_after = models.JSONField(default=dict, blank=True)
    evaluation = models.TextField(blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_runtime_outcomes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Outcome for {self.action_id} (success={self.success})"


class AgentApproval(BaseModel):
    """Human sign-off gate for policy-sensitive actions (not used by AI Agent
    in Phase 2 — every tool it has is policy-ALLOWED — but wired end-to-end
    so a future Pharmacy/Doctor agent can flip specific tools to
    REQUIRES_APPROVAL without new plumbing)."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    action = models.OneToOneField(AgentAction, on_delete=models.CASCADE, related_name="approval")
    approval_type = models.CharField(max_length=100)
    required_role = models.CharField(max_length=50, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    class Meta:
        db_table = "agent_runtime_approvals"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Approval for {self.action_id} ({self.status})"
