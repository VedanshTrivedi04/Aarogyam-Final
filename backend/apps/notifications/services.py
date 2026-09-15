"""
apps/notifications/services.py — Multi-channel notification dispatcher.
"""
import logging
import os
from django.utils import timezone
from .models import Notification, NotificationStatus

logger = logging.getLogger('medadhere')


class NotificationDispatcher:
    """
    Routes notifications to the correct channel based on user preferences
    and subscription plan. Falls back gracefully if a channel fails.
    """

    CHANNEL_HANDLERS = {}  # populated lazily

    @classmethod
    def dispatch(cls, user, notification_type: str, title: str, body: str,
                 data: dict = None, channels: list = None,
                 idempotency_key: str = None) -> list:
        """
        Dispatch to one or more channels. Returns list of Notification objects.
        """
        from apps.subscriptions.gates import SubscriptionGate

        if idempotency_key:
            existing = Notification.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return [existing]

        if not channels:
            channels = cls._resolve_channels(user, notification_type)

        created = []
        for channel in channels:
            notif = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                channel=channel,
                title=title,
                body=body,
                data=data or {},
                status=NotificationStatus.PENDING,
                idempotency_key=idempotency_key,
            )
            # IN_APP is already persisted — no external send needed
            if channel != 'IN_APP':
                from .tasks import send_notification_async
                send_notification_async.delay(str(notif.id))
            created.append(notif)

        return created

    @staticmethod
    def _resolve_channels(user, notification_type: str) -> list:
        """Pick channels based on user prefs and subscription."""
        from apps.identity.models import NotificationPreferences
        from apps.subscriptions.gates import SubscriptionGate

        try:
            prefs = user.notification_preferences
        except NotificationPreferences.DoesNotExist:
            prefs = None

        channels = ['IN_APP']  # always

        # Push
        if (prefs is None or prefs.push_enabled) and user.devices.filter(is_active=True).exists():
            channels.append('PUSH')

        # Email
        if prefs is None or prefs.email_enabled:
            channels.append('EMAIL')

        # SMS — freemium+
        if SubscriptionGate.has_feature(user, 'sms_reminders') and (prefs is None or prefs.sms_enabled):
            channels.append('SMS')

        # Telegram — premium. Reuses the 'whatsapp_enabled'/'whatsapp_reminders'
        # preference & feature-gate names (schema/plan-config rename is out of
        # scope for now); also requires an actual linked+verified chat, since
        # sending needs a Telegram chat_id, not a phone number.
        if SubscriptionGate.has_feature(user, 'whatsapp_reminders') and (prefs is None or getattr(prefs, 'whatsapp_enabled', False)):
            from apps.telegram_bot.models import TelegramSession
            if TelegramSession.objects.filter(user=user, onboarding_done=True).exists():
                channels.append('TELEGRAM')

        # Voice — premium
        if SubscriptionGate.has_feature(user, 'voice_reminders') and notification_type == 'DOSE_REMINDER':
            channels.append('VOICE')

        return channels

    @staticmethod
    def send_push(notification: Notification) -> bool:
        """Send via Firebase Cloud Messaging."""
        from django.conf import settings
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging

            if not firebase_admin._apps:
                cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
                if not cred_path or not os.path.exists(cred_path):
                    logger.warning('Push skipped: FIREBASE_CREDENTIALS_PATH not set or file missing')
                    return False
                firebase_admin.initialize_app(credentials.Certificate(cred_path))

            user = notification.user
            # UserDevice (apps.identity.models), not apps.iot's Device — that's
            # the IoT smart pillbox, unrelated to mobile push registration.
            devices = user.push_devices.filter(is_active=True)
            tokens = list(devices.values_list('fcm_token', flat=True)) + list(
                devices.values_list('apns_token', flat=True)
            )
            tokens = [t for t in tokens if t]
            if not tokens:
                return False

            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=notification.title,
                    body=notification.body,
                ),
                data={k: str(v) for k, v in notification.data.items()},
                tokens=tokens,
            )
            response = messaging.send_each_for_multicast(message)
            notification.external_id = f'fcm:{response.success_count}/{len(tokens)}'
            notification.status      = NotificationStatus.SENT
            notification.sent_at     = timezone.now()
            notification.save(update_fields=['status', 'sent_at', 'external_id', 'updated_at'])
            return response.success_count > 0
        except Exception as e:
            logger.error(f'Push send failed for notif={notification.id}: {e}')
            notification.status        = NotificationStatus.FAILED
            notification.failed_reason = str(e)
            notification.save(update_fields=['status', 'failed_reason', 'updated_at'])
            return False

    @staticmethod
    def send_email(notification: Notification) -> bool:
        """Send email via Django SMTP (Gmail) with branded HTML template."""
        from django.conf import settings
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string

        try:
            html_body = render_to_string('emails/notification_email.html', {
                'title':             notification.title,
                'body':              notification.body,
                'user_name':         notification.user.full_name or notification.user.email,
                'notification_type': notification.notification_type,
            })
            msg = EmailMultiAlternatives(
                subject=notification.title,
                body=notification.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[notification.user.email],
            )
            msg.attach_alternative(html_body, 'text/html')
            msg.send(fail_silently=False)

            notification.external_id = 'django_mail'
            notification.status      = NotificationStatus.SENT
            notification.sent_at     = timezone.now()
            notification.save(update_fields=['status', 'sent_at', 'external_id', 'updated_at'])
            return True
        except Exception as e:
            logger.error(f'Email send failed for notif={notification.id}: {e}')
            notification.status        = NotificationStatus.FAILED
            notification.failed_reason = str(e)
            notification.save(update_fields=['status', 'failed_reason', 'updated_at'])
            return False

    @staticmethod
    def send_sms(notification: Notification) -> bool:
        """Send via Twilio SMS."""
        from django.conf import settings
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            phone  = notification.user.phone_number
            if not phone:
                return False
            # Use Messaging Service SID if available for better delivery management
            msg_params = {
                'body': f'{notification.title}: {notification.body}',
                'to': phone,
            }
            if getattr(settings, 'TWILIO_MESSAGING_SERVICE_SID', ''):
                msg_params['messaging_service_sid'] = settings.TWILIO_MESSAGING_SERVICE_SID
            else:
                msg_params['from_'] = settings.TWILIO_FROM_NUMBER

            msg = client.messages.create(**msg_params)

            notification.external_id = msg.sid
            notification.status      = NotificationStatus.SENT
            notification.sent_at     = timezone.now()
            notification.save(update_fields=['status', 'sent_at', 'external_id', 'updated_at'])
            return True
        except Exception as e:
            logger.error(f'SMS send failed for notif={notification.id}: {e}')
            notification.status        = NotificationStatus.FAILED
            notification.failed_reason = str(e)
            notification.save(update_fields=['status', 'failed_reason', 'updated_at'])
            return False

    @staticmethod
    def send_telegram(notification: Notification) -> bool:
        """
        Send via the Telegram Bot API. Unlike Twilio/Meta, sending needs the
        recipient's chat_id (from a linked, onboarding-complete TelegramSession),
        not a phone number — the user must have messaged the bot at least once.
        If this is a dose reminder (data.reminder_job_id present), also tags the
        session so the next reply is parsed as a Y/N/skip dose response.
        """
        from apps.telegram_bot.models import TelegramSession
        from apps.telegram_bot.services import TelegramService, TelegramConversationHandler
        try:
            session = TelegramSession.objects.filter(
                user=notification.user, onboarding_done=True
            ).first()
            if not session:
                return False

            result = TelegramService.send_message(
                session.chat_id, f'*{notification.title}*\n{notification.body}'
            )
            if 'error' in result:
                raise RuntimeError(result['error'])

            reminder_job_id = notification.data.get('reminder_job_id')
            if reminder_job_id:
                TelegramConversationHandler.set_session_awaiting_dose(session.chat_id, {
                    'reminder_job_id': reminder_job_id,
                    'patient_id':      notification.data.get('patient_id'),
                    'prescription_id': notification.data.get('prescription_id'),
                })

            notification.external_id = str((result.get('result') or {}).get('message_id', ''))
            notification.status      = NotificationStatus.SENT
            notification.sent_at     = timezone.now()
            notification.save(update_fields=['status', 'sent_at', 'external_id', 'updated_at'])
            return True
        except Exception as e:
            logger.error(f'Telegram send failed for notif={notification.id}: {e}')
            notification.status        = NotificationStatus.FAILED
            notification.failed_reason = str(e)
            notification.save(update_fields=['status', 'failed_reason', 'updated_at'])
            return False

    @staticmethod
    def send_voice(notification: Notification) -> bool:
        """Send via Twilio Voice TwiML."""
        from django.conf import settings
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            phone  = notification.user.phone_number
            if not phone:
                return False
            twiml = f'<Response><Say>{notification.body}</Say></Response>'
            call  = client.calls.create(
                twiml=twiml,
                from_=settings.TWILIO_FROM_NUMBER,
                to=phone,
            )
            notification.external_id = call.sid
            notification.status      = NotificationStatus.SENT
            notification.sent_at     = timezone.now()
            notification.save(update_fields=['status', 'sent_at', 'external_id', 'updated_at'])
            return True
        except Exception as e:
            logger.error(f'Voice call failed for notif={notification.id}: {e}')
            notification.status        = NotificationStatus.FAILED
            notification.failed_reason = str(e)
            notification.save(update_fields=['status', 'failed_reason', 'updated_at'])
            return False
