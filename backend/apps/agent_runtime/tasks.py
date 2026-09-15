"""
Agent Runtime Celery Tasks
==========================
Follows the same guarded-import-then-reach-into-orchestrator pattern as
apps/ai_engine/tasks/__init__.py — the agent system lives in the root
agenthandover.py module, not a normal installed app, so it's imported
lazily/defensively.
"""

import logging

from celery import shared_task

logger = logging.getLogger("medadhere.agent_runtime.tasks")


@shared_task(bind=True, max_retries=2, default_retry_delay=30, name="agent_runtime.evaluate_intervention_needed")
def evaluate_intervention_needed(self, patient_id: str, trace_id: str = ""):
    """
    Runs the full reason -> plan -> act pipeline for one patient. Triggered
    from AIAgent.execute_intervention_goal (itself called when
    HIGH_RISK_DETECTED fires) rather than run inline in the synchronous
    event broadcast, since the LLM call has real latency/failure modes that
    shouldn't block that path.
    """
    try:
        from apps.agent_runtime.services.pipeline import run_adherence_intervention
        result = run_adherence_intervention(patient_id=patient_id, trace_id=trace_id)
        logger.info(f"Intervention pipeline result for {patient_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"evaluate_intervention_needed failed for {patient_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60, name="agent_runtime.check_intervention_outcome")
def check_intervention_outcome(self, outcome_id: str):
    """Evaluates whether a past intervention worked (patient took the next dose)."""
    try:
        from apps.agent_runtime.models import AgentOutcome
        from apps.agent_runtime.services import outcome_monitor

        outcome = AgentOutcome.objects.filter(id=outcome_id).first()
        if not outcome:
            logger.warning(f"AgentOutcome {outcome_id} not found")
            return {"skipped": "not_found"}

        result = outcome_monitor.evaluate(outcome)
        return {"outcome_id": outcome_id, "success": result.success, "evaluation": result.evaluation}
    except Exception as e:
        logger.error(f"check_intervention_outcome failed for {outcome_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=30, name="agent_runtime.evaluate_refill_needed")
def evaluate_refill_needed(self, prescription_id: str, patient_id: str, trace_id: str = ""):
    """
    Runs the full reason -> plan -> act pipeline for one prescription's
    refill decision. Not currently triggered from the live
    REFILL_THRESHOLD_REACHED event — see pharmacy_pipeline.py's module
    docstring — invoke manually (e.g. via agent_test_refill) until that
    wiring is added.
    """
    try:
        from apps.agent_runtime.services.pharmacy_pipeline import run_pharmacy_refill
        result = run_pharmacy_refill(prescription_id=prescription_id, patient_id=patient_id, trace_id=trace_id)
        logger.info(f"Pharmacy refill pipeline result for {prescription_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"evaluate_refill_needed failed for {prescription_id}: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=2, default_retry_delay=60, name="agent_runtime.check_refill_outcome")
def check_refill_outcome(self, outcome_id: str):
    """Evaluates whether a past refill action worked (order delivered)."""
    try:
        from apps.agent_runtime.models import AgentOutcome
        from apps.agent_runtime.services import pharmacy_outcome_monitor

        outcome = AgentOutcome.objects.filter(id=outcome_id).first()
        if not outcome:
            logger.warning(f"AgentOutcome {outcome_id} not found")
            return {"skipped": "not_found"}

        result = pharmacy_outcome_monitor.evaluate(outcome)
        return {"outcome_id": outcome_id, "success": result.success, "evaluation": result.evaluation}
    except Exception as e:
        logger.error(f"check_refill_outcome failed for {outcome_id}: {e}")
        raise self.retry(exc=e)
