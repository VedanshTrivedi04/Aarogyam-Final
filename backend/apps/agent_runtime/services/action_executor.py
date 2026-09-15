"""
Action Executor
===============
Turns one LLM-decided tool call into an actual system action (or, in
dry-run mode, a logged-but-not-executed intent). Every call is recorded as
an AgentAction row regardless of outcome — this is the audit trail.
"""

import logging

from apps.agent_runtime.models import AgentAction, AgentGoal
from apps.agent_runtime.services import approval_manager, policy_engine
from apps.agent_runtime.services.tool_registry import TOOLS

logger = logging.getLogger("medadhere.agent_runtime.executor")


def execute(
    goal: AgentGoal,
    agent_name: str,
    tool_name: str,
    tool_input: dict,
    trace_id: str = "",
    dry_run: bool = False,
    policy_context: dict | None = None,
) -> AgentAction:
    """
    Never raises — a failure is recorded on the AgentAction row (status=FAILED,
    output={'error': ...}), never propagated to the caller. Callers can
    check `action.status` to react.

    `policy_context` is optional and only used by tools with situational
    policy (see policy_engine._CONDITIONAL_POLICY) — omitted by existing
    callers, whose tools all resolve from the static policy map as before.
    """
    policy = policy_engine.check(tool_name, policy_context)

    action = AgentAction.objects.create(
        goal=goal,
        agent_name=agent_name,
        tool_name=tool_name,
        input=tool_input,
        trace_id=trace_id,
        status=AgentAction.Status.EXECUTED,  # updated below
    )

    if policy == policy_engine.Policy.REQUIRES_APPROVAL:
        approval_manager.request_approval(action, approval_type=tool_name)
        logger.info(f"Action {tool_name} requires approval — created pending AgentApproval")
        return action

    if dry_run:
        action.status = AgentAction.Status.SKIPPED
        action.output = {"dry_run": True, "would_call": tool_name, "with": tool_input}
        action.save(update_fields=["status", "output", "updated_at"])
        logger.info(f"[dry-run] would call {tool_name}({tool_input})")
        return action

    tool_fn = TOOLS.get(tool_name)
    if tool_fn is None:
        action.status = AgentAction.Status.FAILED
        action.output = {"error": f"unknown_tool: {tool_name}"}
        action.save(update_fields=["status", "output", "updated_at"])
        return action

    try:
        result = tool_fn(**tool_input)
        action.status = AgentAction.Status.EXECUTED
        action.output = result if isinstance(result, dict) else {"result": result}
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        action.status = AgentAction.Status.FAILED
        action.output = {"error": str(e)}

    action.save(update_fields=["status", "output", "updated_at"])
    return action
