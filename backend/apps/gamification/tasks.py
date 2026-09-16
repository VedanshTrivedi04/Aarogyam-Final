import logging
from datetime import timedelta

from celery import shared_task
from django.utils.timezone import localdate

logger = logging.getLogger('medadhere')


@shared_task
def update_all_patient_scores():
    """
    Daily refresh of each active patient's current-week adherence score.
    Delegates to GamificationAgent.compute_weekly_score — the single
    canonical implementation of streak/badge/score logic (see
    medadhere_extensions_handover.py) — rather than duplicating the math here.
    """
    from agenthandover import AgentRegistry
    from apps.clinical.models import Patient

    agent = AgentRegistry.get('GamificationAgent')
    today = localdate()
    week_start = today - timedelta(days=today.weekday())  # Monday of this week

    count = 0
    for patient in Patient.objects.filter(is_active=True):
        try:
            agent.compute_weekly_score(patient_id=str(patient.id), week_start=week_start)
            count += 1
        except Exception:
            logger.warning('Weekly score update failed for patient %s', patient.id, exc_info=True)

    return {'updated': count, 'week_start': str(week_start)}
