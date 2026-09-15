"""
apps/notifications/tasks.py
"""
import logging
from celery import shared_task

logger = logging.getLogger('medadhere')


@shared_task(name='apps.notifications.tasks.send_notification_async', bind=True, max_retries=3, default_retry_delay=60)
def send_notification_async(self, notification_id: str):
    """Dispatch a single notification to its channel."""
    from .models import Notification
    from .services import NotificationDispatcher

    try:
        notif = Notification.objects.select_related('user').get(id=notification_id)
    except Notification.DoesNotExist:
        return

    channel  = notif.channel
    handlers = {
        'PUSH':      NotificationDispatcher.send_push,
        'EMAIL':     NotificationDispatcher.send_email,
        'SMS':       NotificationDispatcher.send_sms,
        'TELEGRAM':  NotificationDispatcher.send_telegram,
        'VOICE':     NotificationDispatcher.send_voice,
        'IN_APP':    lambda n: True,  # already persisted
    }
    handler = handlers.get(channel)
    if handler:
        try:
            handler(notif)
        except Exception as exc:
            logger.error(f'Notification send failed [{channel}] id={notification_id}: {exc}')
            raise self.retry(exc=exc)


@shared_task(name='apps.notifications.tasks.purge_old_notifications')
def purge_old_notifications():
    """Weekly: delete READ notifications older than 90 days."""
    from django.utils import timezone
    import datetime
    from .models import Notification

    cutoff = timezone.now() - datetime.timedelta(days=90)
    deleted, _ = Notification.objects.filter(
        status='READ', created_at__lt=cutoff
    ).delete()
    return {'deleted': deleted}
