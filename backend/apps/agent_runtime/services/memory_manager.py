"""
Memory Manager
==============
Read/write AgentMemory — what an agent has learned about a patient from
past interventions, so the next reasoning pass doesn't repeat a strategy
that already failed (or ignore one that worked).
"""

import logging

from apps.agent_runtime.models import AgentMemory

logger = logging.getLogger("medadhere.agent_runtime.memory")

RECENT_MEMORY_LIMIT = 5


def recall(agent_name: str, patient_id: str, memory_type: str = "INTERVENTION_OUTCOME") -> list:
    """Most recent memories for this patient, most-recent first."""
    qs = AgentMemory.objects.filter(
        agent_name=agent_name, patient_id=patient_id, memory_type=memory_type
    )[:RECENT_MEMORY_LIMIT]
    return list(qs)


def remember(
    agent_name: str,
    patient_id: str,
    memory_type: str,
    content: dict,
    importance: float = 0.5,
    confidence: float = 0.5,
) -> AgentMemory:
    return AgentMemory.objects.create(
        agent_name=agent_name,
        patient_id=patient_id,
        memory_type=memory_type,
        content=content,
        importance=importance,
        confidence=confidence,
    )


def summarize_for_prompt(agent_name: str, patient_id: str) -> str:
    """Human-readable summary of past interventions, for the LLM prompt."""
    memories = recall(agent_name, patient_id)
    if not memories:
        return "No prior intervention history for this patient."

    lines = []
    for m in memories:
        tool = m.content.get("tool_name", "unknown action")
        outcome = m.content.get("outcome", "unknown outcome")
        lines.append(f"- {tool} on {m.created_at.date()}: {outcome}")
    return "Past interventions:\n" + "\n".join(lines)
