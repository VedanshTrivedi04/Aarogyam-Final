from celery import shared_task
from django.db import models
from agenthandover import get_orchestrator
from medadhere_extensions_handover import ExtAgentEvent, HandoverPayload

@shared_task(bind=True, max_retries=3)
def call_pharmacy_api(self, refill_order_id: str):
    """
    Async call to pharmacy partner API.
    Retries on failure with exponential backoff.
    """
    from apps.pharmacy.models import RefillOrder
    from apps.pharmacy.services import PharmacyAPIService

    try:
        order = RefillOrder.objects.select_related(
            'partner', 'prescription__medication', 'patient'
        ).get(id=refill_order_id)

        partner_order_id = PharmacyAPIService(order.partner).place_order(order)
        order.partner_order_id = partner_order_id
        order.status = 'PARTNER_CONFIRMED'
        order.save(update_fields=['partner_order_id', 'status', 'updated_at'])

    except Exception as exc:
        RefillOrder.objects.filter(id=refill_order_id, status='PENDING').update(
            status='FAILED', failure_reason=str(exc)
        )
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)

@shared_task
def check_refill_thresholds():
    """
    Daily Celery Beat — check all active prescriptions for refill threshold.
    """
    from apps.clinical.models import Prescription

    low_stock = Prescription.objects.filter(
        is_active=True,
        deleted_at__isnull=True,
        remaining_quantity__lte=models.F('refill_alert_days'),
    ).select_related('patient')

    orchestrator = get_orchestrator()
    for rx in low_stock:
        payload = HandoverPayload(
            patient_id     = str(rx.patient_id),
            prescription_id= str(rx.id),
            data           = {'remaining_quantity': rx.remaining_quantity},
        )
        orchestrator.broadcast('ClinicalApp', ExtAgentEvent.REFILL_THRESHOLD_REACHED, payload)
        
    return {'prescriptions_checked': low_stock.count()}
