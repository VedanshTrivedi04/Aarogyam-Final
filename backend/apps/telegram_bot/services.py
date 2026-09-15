import hmac
import logging
import re
import secrets

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.identity.models import User

logger = logging.getLogger('medadhere')

OTP_TTL_SECONDS = 5 * 60
OTP_MAX_ATTEMPTS = 3

YES_TRIGGERS  = {'1', 'yes', 'haan', 'ha', 'han', 'liya', 'le li', 'le lia', 'ok'}
NO_TRIGGERS   = {'2', 'no', 'nahi', 'nahin', 'nhi', 'nahi li'}
SKIP_TRIGGERS = {'3', 'skip', 'baad mein', 'baad', 'later'}
HELP_TRIGGERS = {'help', 'madad', '?', 'start'}


def normalize_phone(phone: str) -> str:
    """Reduce a phone number to its last 10 digits for tolerant matching."""
    digits = re.sub(r'\D', '', phone or '')
    return digits[-10:] if len(digits) >= 10 else digits


class TelegramService:
    """Thin wrapper around the Telegram Bot API. https://core.telegram.org/bots/api"""

    @staticmethod
    def _api_url(method: str) -> str:
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        return f"https://api.telegram.org/bot{token}/{method}"

    @staticmethod
    def send_message(chat_id, text: str, request_contact: bool = False, remove_keyboard: bool = False) -> dict:
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not token:
            logger.warning(f"[MOCK] Telegram to {chat_id}: {text}")
            return {"status": "mocked"}

        payload = {"chat_id": chat_id, "text": text}
        if request_contact:
            payload["reply_markup"] = {
                "keyboard": [[{"text": "📱 Share My Number", "request_contact": True}]],
                "resize_keyboard": True,
                "one_time_keyboard": True,
            }
        elif remove_keyboard:
            payload["reply_markup"] = {"remove_keyboard": True}

        try:
            response = requests.post(TelegramService._api_url("sendMessage"), json=payload, timeout=10)
            if response.status_code >= 400:
                logger.error(f"Telegram send failed ({response.status_code}): {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return {"error": str(e)}

    @staticmethod
    def verify_secret_token(header_value: str) -> bool:
        """
        Telegram echoes back whatever secret_token you registered via
        setWebhook, in the X-Telegram-Bot-Api-Secret-Token header, on every
        call. Simple shared-secret check — no per-request signing needed.
        """
        secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')
        if not secret:
            logger.warning("TELEGRAM_WEBHOOK_SECRET not set; skipping webhook auth check.")
            return True
        return hmac.compare_digest(header_value or '', secret)


class TelegramVerificationService:
    """
    Links a Telegram chat to an existing MedAdhere account. Telegram doesn't
    expose the user's phone number automatically (unlike WhatsApp/Twilio),
    so the bot asks the user to share it via Telegram's native contact-share
    button, then confirms ownership with an OTP — same idea as the WhatsApp
    flow, just with an extra explicit consent step.
    """

    @staticmethod
    def find_matching_user(phone_number: str):
        target = normalize_phone(phone_number)
        if not target:
            return None
        for user in User.objects.exclude(phone_number__isnull=True).exclude(phone_number=''):
            if normalize_phone(user.phone_number) == target:
                return user
        return None

    @staticmethod
    def generate_and_send_otp(chat_id, user) -> None:
        code = f"{secrets.randbelow(1_000_000):06d}"
        cache.set(
            f"tg_otp:{chat_id}",
            {"code": code, "user_id": str(user.id), "attempts": 0},
            timeout=OTP_TTL_SECONDS,
        )
        TelegramService.send_message(
            chat_id,
            f"Aapka MedAdhere verification code hai: {code}\n"
            f"Yeh {OTP_TTL_SECONDS // 60} minute mein expire ho jayega. Kisi ke saath share na karein.",
            remove_keyboard=True,
        )

    @staticmethod
    def verify_otp(chat_id, submitted_code: str):
        """Returns the User on success, or a string reason on failure ('expired'|'invalid'|'locked')."""
        key = f"tg_otp:{chat_id}"
        entry = cache.get(key)
        if not entry:
            return 'expired'

        if entry['attempts'] >= OTP_MAX_ATTEMPTS:
            cache.delete(key)
            return 'locked'

        if submitted_code.strip() != entry['code']:
            entry['attempts'] += 1
            cache.set(key, entry, timeout=OTP_TTL_SECONDS)
            return 'invalid'

        cache.delete(key)
        try:
            user = User.objects.get(id=entry['user_id'])
        except User.DoesNotExist:
            return 'invalid'

        if not user.is_phone_verified:
            user.is_phone_verified = True
            user.save(update_fields=['is_phone_verified'])
        return user


class TelegramStatusService:
    @staticmethod
    def get_today_summary(user_id: str) -> str:
        from apps.clinical.models import Patient
        from apps.scheduling.models import ReminderJob
        try:
            patient = Patient.objects.get(user_id=user_id)
            today = timezone.localdate()
            events = ReminderJob.objects.filter(
                schedule__prescription__patient=patient,
                scheduled_at__date=today
            ).select_related('schedule__prescription__medication')

            if not events.exists():
                return "Aaj ke liye koi dava schedule nahi hai. 😊"

            lines = ["📋 Aaj ki Medications:"]
            for e in events:
                status_icon = "✅" if e.status == 'TAKEN' else "❌" if e.status == 'MISSED' else "⏳"
                med_name = e.schedule.prescription.medication.name
                time_str = e.scheduled_at.strftime("%I:%M %p")
                lines.append(f"{status_icon} {med_name} - {time_str}")

            return "\n".join(lines)
        except Patient.DoesNotExist:
            return "Patient profile nahi mila."
        except Exception as e:
            logger.error(f"Telegram Status Error: {e}")
            return "Maafi chahte hain, status fetch karne mein problem hui."


class TelegramConversationHandler:
    """Entry point + state machine for inbound Telegram updates."""

    @staticmethod
    def handle_update(chat_id, text: str, contact_phone: str, update_id) -> dict:
        from .models import TelegramSession, TelegramInteractionLog

        if update_id and TelegramInteractionLog.objects.filter(telegram_update_id=str(update_id)).exists():
            return {'status': 'duplicate_ignored'}

        session, _ = TelegramSession.objects.get_or_create(
            chat_id=str(chat_id),
            defaults={'state': 'IDLE', 'last_activity_at': timezone.now()},
        )
        session.last_activity_at = timezone.now()
        session.save(update_fields=['last_activity_at', 'updated_at'])

        TelegramInteractionLog.objects.create(
            session=session, direction='INBOUND',
            message_body=text or '[contact shared]',
            telegram_update_id=str(update_id) if update_id else None,
        )

        if not session.onboarding_done:
            return TelegramConversationHandler._handle_verification(session, text, contact_phone)
        return TelegramConversationHandler._handle_active_session(session, text)

    # ── Verification ────────────────────────────────────────────────

    @staticmethod
    def _handle_verification(session, text, contact_phone) -> dict:
        if contact_phone:
            user = TelegramVerificationService.find_matching_user(contact_phone)
            if not user:
                TelegramService.send_message(
                    session.chat_id,
                    "Yeh number MedAdhere ke kisi patient/caregiver account se match nahi hua.\n"
                    "Kripya app mein registered number se try karein, ya support@medadhere.app se contact karein.",
                    remove_keyboard=True,
                )
                return {'status': 'no_account_match'}

            session.phone_number = contact_phone
            session.state = 'AWAITING_OTP'
            session.state_data['pending_user_id'] = str(user.id)
            session.save(update_fields=['phone_number', 'state', 'state_data', 'updated_at'])
            TelegramVerificationService.generate_and_send_otp(session.chat_id, user)
            return {'status': 'otp_sent'}

        if session.state == 'AWAITING_OTP':
            return TelegramConversationHandler._complete_verification(session, text)

        # First contact from this chat — ask them to share their number.
        session.state = 'AWAITING_CONTACT'
        session.save(update_fields=['state', 'updated_at'])
        TelegramService.send_message(
            session.chat_id,
            "Namaste! 🙏 MedAdhere Telegram bot mein aapka swagat hai.\n"
            "Verify karne ke liye neeche button se apna number share karein:",
            request_contact=True,
        )
        return {'status': 'awaiting_contact'}

    @staticmethod
    def _complete_verification(session, code) -> dict:
        result = TelegramVerificationService.verify_otp(session.chat_id, code or '')

        if result == 'invalid':
            TelegramService.send_message(session.chat_id, "Code galat hai. Dobara try karein.")
            return {'status': 'invalid_otp'}

        if result in ('expired', 'locked'):
            session.state = 'IDLE'
            session.state_data = {}
            session.save(update_fields=['state', 'state_data', 'updated_at'])
            reason = "Code expire ho gaya" if result == 'expired' else "Bohot zyada galat attempts ho gaye"
            TelegramService.send_message(session.chat_id, f"{reason}. Number share karke phir try karein.")
            return {'status': result}

        user = result
        session.user = user
        session.onboarding_done = True
        session.state = 'IDLE'
        session.state_data = {}
        session.save(update_fields=['user', 'onboarding_done', 'state', 'state_data', 'updated_at'])

        try:
            from agenthandover import AgentRegistry, AgentName, HandoverPayload, AgentNotFoundError
            notif_agent = AgentRegistry.get(AgentName.NOTIFICATION)
            notif_agent.send_welcome_notification(HandoverPayload(user_id=str(user.id)))
        except AgentNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Welcome notification broadcast failed (non-fatal): {e}")

        TelegramService.send_message(
            session.chat_id,
            "✅ Verified! Ab aap yahan se apni dawai ka status check kar sakte hain.\n"
            "'help' type karein commands dekhne ke liye."
        )
        return {'status': 'onboarding_complete', 'user_id': str(user.id)}

    # ── Active session ──────────────────────────────────────────────

    @staticmethod
    def _parse_intent(text: str) -> str:
        if text in YES_TRIGGERS:
            return 'DOSE_YES'
        if text in NO_TRIGGERS:
            return 'DOSE_NO'
        if text in SKIP_TRIGGERS:
            return 'DOSE_SKIP'
        if text in HELP_TRIGGERS:
            return 'HELP'
        if 'status' in text or 'aaj' in text:
            return 'STATUS'
        return 'UNKNOWN'

    @staticmethod
    def _handle_active_session(session, text) -> dict:
        intent = TelegramConversationHandler._parse_intent((text or '').strip().lower())

        if session.state == 'AWAITING_DOSE_RESPONSE':
            return TelegramConversationHandler._process_dose_response(session, intent)

        if intent == 'STATUS':
            TelegramService.send_message(session.chat_id, TelegramStatusService.get_today_summary(session.user_id))
            return {'status': 'status_sent'}

        if intent == 'HELP':
            TelegramService.send_message(
                session.chat_id,
                "MedAdhere Help:\n"
                "• 'status' — aaj ki dava status\n"
                "• Reminder aane par 1 = li, 2 = nahi li, 3 = baad mein\n"
                "Support: support@medadhere.app"
            )
            return {'status': 'help_sent'}

        TelegramService.send_message(session.chat_id, "Samajh nahi aaya. 'help' type karein.")
        return {'status': 'unknown_handled'}

    @staticmethod
    def _process_dose_response(session, intent) -> dict:
        """
        Logs the dose directly against ReminderJob/DoseLog (apps.scheduling) —
        NOT via AdherenceAgent.log_dose(), which references a non-existent
        apps.telemetry.models.AdherenceEvent and would crash. This mirrors the
        same fix already made for status lookups.
        """
        from django.utils import timezone as tz
        from apps.scheduling.models import ReminderJob, DoseLog, ReminderStatus, DoseSource

        context = session.state_data or {}
        reminder_id = context.get('reminder_job_id')
        if not reminder_id:
            session.state = 'IDLE'
            session.state_data = {}
            session.save(update_fields=['state', 'state_data', 'updated_at'])
            return {'status': 'no_reminder_context'}

        try:
            reminder = ReminderJob.objects.select_related('schedule__prescription').get(id=reminder_id)
        except ReminderJob.DoesNotExist:
            session.state = 'IDLE'
            session.state_data = {}
            session.save(update_fields=['state', 'state_data', 'updated_at'])
            return {'status': 'reminder_not_found'}

        status = (
            ReminderStatus.TAKEN if intent == 'DOSE_YES'
            else ReminderStatus.SKIPPED if intent == 'DOSE_SKIP'
            else ReminderStatus.MISSED
        )
        reminder.status = status
        reminder.save(update_fields=['status', 'updated_at'])

        DoseLog.objects.update_or_create(
            reminder_job=reminder,
            defaults={
                'prescription': reminder.schedule.prescription,
                'status':       status,
                'source':       DoseSource.APP,
                'taken_at':     tz.now() if status == ReminderStatus.TAKEN else None,
                'dose_value':   reminder.dose_value,
                'dose_unit':    reminder.dose_unit,
            }
        )

        session.state = 'IDLE'
        session.state_data = {}
        session.save(update_fields=['state', 'state_data', 'updated_at'])
        return {'status': 'dose_response_processed', 'intent': intent}

    @staticmethod
    def set_session_awaiting_dose(chat_id, context: dict) -> None:
        """Called when a dose reminder is sent, so the next reply is parsed as Y/N/skip."""
        from .models import TelegramSession
        TelegramSession.objects.filter(chat_id=str(chat_id)).update(
            state='AWAITING_DOSE_RESPONSE',
            state_data=context,
            last_activity_at=timezone.now(),
        )
