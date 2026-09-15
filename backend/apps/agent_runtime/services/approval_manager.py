"""
Approval Manager
================
Creates/resolves AgentApproval records for policy-REQUIRES_APPROVAL
actions. Not exercised by the AI Agent in Phase 2 (its whole tool set is
policy-ALLOWED — see policy_engine.py) but wired end-to-end so a future
Pharmacy/Doctor agent can gate specific tools without new plumbing.
"""

from django.utils import timezone

from apps.agent_runtime.models import AgentAction, AgentApproval


def request_approval(action: AgentAction, approval_type: str, required_role: str = "") -> AgentApproval:
    action.status = AgentAction.Status.PENDING_APPROVAL
    action.save(update_fields=["status", "updated_at"])
    return AgentApproval.objects.create(
        action=action,
        approval_type=approval_type,
        required_role=required_role,
        status=AgentApproval.Status.PENDING,
    )


def approve(approval: AgentApproval, user) -> AgentApproval:
    approval.status = AgentApproval.Status.APPROVED
    approval.approved_by = user
    approval.approved_at = timezone.now()
    approval.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return approval


def reject(approval: AgentApproval, user) -> AgentApproval:
    approval.status = AgentApproval.Status.REJECTED
    approval.approved_by = user
    approval.approved_at = timezone.now()
    approval.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return approval
