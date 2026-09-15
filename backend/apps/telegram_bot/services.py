import hmac
import logging
import re
import secrets

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone

from apps.identity.models import User
from .i18n import t, btn

logger = logging.getLogger('medadhere')

OTP_TTL_SECONDS = 5 * 60
OTP_MAX_ATTEMPTS = 3
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


# ── Keyboards ────────────────────────────────────────────────────────

def language_keyboard():
    return [[
        {"text": "हिंदी", "callback_data": "lang:hi"},
        {"text": "English", "callback_data": "lang:en"},
    ]]


def main_menu_keyboard(lang):
    return [
        [{"text": btn(lang, 'status'), "callback_data": "menu:status"}],
        [{"text": btn(lang, 'report'), "callback_data": "menu:report"}],
        [{"text": btn(lang, 'help'), "callback_data": "menu:help"}],
        [{"text": btn(lang, 'change_lang'), "callback_data": "menu:lang"}],
    ]


def dose_keyboard(lang):
    return [[
        {"text": btn(lang, 'dose_yes'), "callback_data": "dose:yes"},
        {"text": btn(lang, 'dose_no'), "callback_data": "dose:no"},
        {"text": btn(lang, 'dose_skip'), "callback_data": "dose:skip"},
    ]]


class TelegramService:
    """Thin wrapper around the Telegram Bot API. https://core.telegram.org/bots/api"""

    @staticmethod
    def _api_url(method: str) -> str:
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        return f"https://api.telegram.org/bot{token}/{method}"

    @staticmethod
    def send_message(chat_id, text: str, inline_keyboard=None) -> dict:
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not token:
            logger.warning(f"[MOCK] Telegram to {chat_id}: {text}")
            return {"status": "mocked"}

        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if inline_keyboard:
            payload["reply_markup"] = {"inline_keyboard": inline_keyboard}

        try:
            response = requests.post(TelegramService._api_url("sendMessage"), json=payload, timeout=10)
            if response.status_code >= 400:
                logger.error(f"Telegram send failed ({response.status_code}): {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return {"error": str(e)}

    @staticmethod
    def answer_callback_query(callback_query_id, text: str = None) -> dict:
        """Required after handling a button tap, or the client shows a loading spinner forever."""
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not token:
            return {"status": "mocked"}
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            return requests.post(TelegramService._api_url("answerCallbackQuery"), json=payload, timeout=10).json()
        except Exception as e:
            logger.error(f"Telegram answerCallbackQuery error: {e}")
            return {"error": str(e)}

    @staticmethod
    def verify_secret_token(header_value: str) -> bool:
        secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')
        if not secret:
            logger.warning("TELEGRAM_WEBHOOK_SECRET not set; skipping webhook auth check.")
            return True
        return hmac.compare_digest(header_value or '', secret)


class TelegramEmailOTPService:
    """
    Links a Telegram chat to an existing MedAdhere account by email. Unlike
    a phone number, Telegram gives no built-in way to prove someone owns an
    email address, so the OTP is sent to that real email inbox (not back
    over Telegram) — only the actual account owner can read it there.
    """

    @staticmethod
    def find_matching_user(email: str):
        email = (email or '').strip().lower()
        if not EMAIL_RE.match(email):
            return None
        return User.objects.filter(email__iexact=email).first()

    @staticmethod
    def generate_and_send_otp(chat_id, user) -> bool:
        code = f"{secrets.randbelow(1_000_000):06d}"
        cache.set(
            f"tg_otp:{chat_id}",
            {"code": code, "user_id": str(user.id), "attempts": 0},
            timeout=OTP_TTL_SECONDS,
        )
        try:
            send_mail(
                subject="Your MedAdhere verification code",
                message=(
                    f"Your MedAdhere Telegram verification code is: {code}\n"
                    f"This code expires in {OTP_TTL_SECONDS // 60} minutes.\n\n"
                    f"If you didn't request this, you can ignore this email."
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=[user.email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"OTP email send failed for {user.email}: {e}")
            return False

    @staticmethod
    def verify_otp(chat_id, submitted_code: str):
        """Returns the User on success, or 'expired'|'invalid'|'locked' on failure."""
        key = f"tg_otp:{chat_id}"
        entry = cache.get(key)
        if not entry:
            return 'expired'

        if entry['attempts'] >= OTP_MAX_ATTEMPTS:
            cache.delete(key)
            return 'locked'

        if (submitted_code or '').strip() != entry['code']:
            entry['attempts'] += 1
            cache.set(key, entry, timeout=OTP_TTL_SECONDS)
            return 'invalid'

        cache.delete(key)
        try:
            user = User.objects.get(id=entry['user_id'])
        except User.DoesNotExist:
            return 'invalid'

        if not user.is_phone_verified:
            # Reused as a general "identity confirmed via OTP" flag.
            user.is_phone_verified = True
            user.save(update_fields=['is_phone_verified'])
        return user


class TelegramAdherenceService:
    @staticmethod
    def get_today_summary(user_id: str, lang: str) -> str:
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
                return t(lang, 'no_schedule_today')

            lines = [t(lang, 'status_header')]
            for e in events:
                icon = "✅" if e.status == 'TAKEN' else "❌" if e.status == 'MISSED' else "⏳"
                med_name = e.schedule.prescription.medication.name
                time_str = e.scheduled_at.strftime("%I:%M %p")
                lines.append(f"{icon} {med_name} - {time_str}")
            return "\n".join(lines)
        except Patient.DoesNotExist:
            return t(lang, 'no_schedule_today')
        except Exception as e:
            logger.error(f"Telegram Status Error: {e}")
            return t(lang, 'no_schedule_today')

    @staticmethod
    def get_adherence_report(user_id: str, lang: str, days: int = 7) -> str:
        """
        Built directly against ReminderJob (NOT AdherenceAgent.get_adherence_rate,
        which references a non-existent apps.telemetry.models.AdherenceEvent and
        would crash) — same fix pattern as the status lookup above.
        """
        from datetime import timedelta
        from apps.clinical.models import Patient
        from apps.scheduling.models import ReminderJob

        try:
            patient = Patient.objects.get(user_id=user_id)
        except Patient.DoesNotExist:
            return t(lang, 'report_no_data')

        since = timezone.now() - timedelta(days=days)
        qs = ReminderJob.objects.filter(
            schedule__prescription__patient=patient,
            scheduled_at__gte=since,
            scheduled_at__lte=timezone.now(),
        )
        total = qs.count()
        if total == 0:
            return t(lang, 'report_header', days=days) + "\n" + t(lang, 'report_no_data')

        taken = qs.filter(status='TAKEN').count()
        missed = qs.filter(status='MISSED').count()
        skipped = qs.filter(status='SKIPPED').count()
        pct = round((taken / total) * 100, 1) if total else 0

        header = t(lang, 'report_header', days=days)
        body = t(lang, 'report_body', taken=taken, missed=missed, skipped=skipped, pct=pct)
        return f"{header}\n{body}"


class TelegramConversationHandler:
    """Entry point + state machine for inbound Telegram updates."""

    # ── Dispatch ─────────────────────────────────────────────────────

    @staticmethod
    def handle_message(chat_id, text: str, update_id) -> dict:
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
            session=session, direction='INBOUND', message_body=text or '',
            telegram_update_id=str(update_id) if update_id else None,
        )

        if session.state == 'IDLE' and not session.onboarding_done:
            return TelegramConversationHandler._start_language_selection(session)

        if session.state == 'AWAITING_EMAIL':
            return TelegramConversationHandler._handle_email_input(session, text)

        if session.state == 'AWAITING_OTP':
            return TelegramConversationHandler._complete_verification(session, text)

        if session.onboarding_done:
            # Free text while verified — just show the menu again instead of
            # requiring exact keywords (this bot is button-driven now).
            TelegramService.send_message(
                session.chat_id, t(session.language, 'menu_prompt'),
                inline_keyboard=main_menu_keyboard(session.language),
            )
            return {'status': 'menu_shown'}

        # Not verified and not in a known input state (e.g. AWAITING_LANGUAGE
        # but they typed instead of tapping) — nudge them back to the buttons.
        return TelegramConversationHandler._start_language_selection(session)

    @staticmethod
    def handle_callback(chat_id, callback_data: str, update_id, callback_query_id) -> dict:
        from .models import TelegramSession, TelegramInteractionLog

        if update_id and TelegramInteractionLog.objects.filter(telegram_update_id=str(update_id)).exists():
            TelegramService.answer_callback_query(callback_query_id)
            return {'status': 'duplicate_ignored'}

        session, _ = TelegramSession.objects.get_or_create(
            chat_id=str(chat_id),
            defaults={'state': 'IDLE', 'last_activity_at': timezone.now()},
        )
        session.last_activity_at = timezone.now()
        session.save(update_fields=['last_activity_at', 'updated_at'])

        TelegramInteractionLog.objects.create(
            session=session, direction='INBOUND', message_body=f'[button: {callback_data}]',
            telegram_update_id=str(update_id) if update_id else None,
        )
        TelegramService.answer_callback_query(callback_query_id)

        if callback_data.startswith('lang:'):
            return TelegramConversationHandler._set_language(session, callback_data.split(':', 1)[1])

        if callback_data.startswith('menu:') and session.onboarding_done:
            return TelegramConversationHandler._handle_menu_action(session, callback_data.split(':', 1)[1])

        if callback_data.startswith('dose:') and session.state == 'AWAITING_DOSE_RESPONSE':
            intent = {'yes': 'DOSE_YES', 'no': 'DOSE_NO', 'skip': 'DOSE_SKIP'}.get(callback_data.split(':', 1)[1])
            return TelegramConversationHandler._process_dose_response(session, intent)

        return {'status': 'ignored'}

    # ── Language & verification ──────────────────────────────────────

    @staticmethod
    def _start_language_selection(session) -> dict:
        session.state = 'AWAITING_LANGUAGE'
        session.save(update_fields=['state', 'updated_at'])
        TelegramService.send_message(
            session.chat_id, t(session.language, 'choose_language'),
            inline_keyboard=language_keyboard(),
        )
        return {'status': 'awaiting_language'}

    @staticmethod
    def _set_language(session, lang) -> dict:
        if lang not in ('hi', 'en'):
            lang = 'hi'
        session.language = lang

        if session.onboarding_done:
            # Changing language later, already verified — just go to menu.
            session.state = 'IDLE'
            session.save(update_fields=['language', 'state', 'updated_at'])
            TelegramService.send_message(
                session.chat_id, t(lang, 'menu_prompt'),
                inline_keyboard=main_menu_keyboard(lang),
            )
            return {'status': 'language_changed'}

        session.state = 'AWAITING_EMAIL'
        session.save(update_fields=['language', 'state', 'updated_at'])
        TelegramService.send_message(session.chat_id, t(lang, 'ask_email'))
        return {'status': 'awaiting_email'}

    @staticmethod
    def _handle_email_input(session, text) -> dict:
        lang = session.language
        email = (text or '').strip()

        if not EMAIL_RE.match(email):
            TelegramService.send_message(session.chat_id, t(lang, 'invalid_email_format'))
            return {'status': 'invalid_email_format'}

        user = TelegramEmailOTPService.find_matching_user(email)
        if not user:
            TelegramService.send_message(session.chat_id, t(lang, 'email_not_found'))
            return {'status': 'no_account_match'}

        session.email = email
        session.state = 'AWAITING_OTP'
        session.state_data['pending_user_id'] = str(user.id)
        session.save(update_fields=['email', 'state', 'state_data', 'updated_at'])

        TelegramEmailOTPService.generate_and_send_otp(session.chat_id, user)
        TelegramService.send_message(
            session.chat_id, t(lang, 'otp_sent', email=email, minutes=OTP_TTL_SECONDS // 60)
        )
        return {'status': 'otp_sent'}

    @staticmethod
    def _complete_verification(session, code) -> dict:
        lang = session.language
        result = TelegramEmailOTPService.verify_otp(session.chat_id, code or '')

        if result == 'invalid':
            TelegramService.send_message(session.chat_id, t(lang, 'otp_invalid'))
            return {'status': 'invalid_otp'}

        if result in ('expired', 'locked'):
            session.state = 'AWAITING_EMAIL'
            session.state_data = {}
            session.save(update_fields=['state', 'state_data', 'updated_at'])
            key = 'otp_expired' if result == 'expired' else 'otp_locked'
            TelegramService.send_message(session.chat_id, t(lang, key))
            return {'status': result}

        user = result
        session.user = user
        session.onboarding_done = True
        session.state = 'IDLE'
        session.state_data = {}
        session.save(update_fields=['user', 'onboarding_done', 'state', 'state_data', 'updated_at'])

        try:
            from agenthandover import AgentRegistry, AgentName, HandoverPayload, AgentNotFoundError
            AgentRegistry.get(AgentName.NOTIFICATION).send_welcome_notification(HandoverPayload(user_id=str(user.id)))
        except AgentNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Welcome notification broadcast failed (non-fatal): {e}")

        TelegramService.send_message(
            session.chat_id,
            t(lang, 'welcome_verified', name=user.full_name or user.email),
            inline_keyboard=main_menu_keyboard(lang),
        )
        return {'status': 'onboarding_complete', 'user_id': str(user.id)}

    # ── Main menu ────────────────────────────────────────────────────

    @staticmethod
    def _handle_menu_action(session, action) -> dict:
        lang = session.language

        if action == 'status':
            text = TelegramAdherenceService.get_today_summary(session.user_id, lang)
        elif action == 'report':
            text = TelegramAdherenceService.get_adherence_report(session.user_id, lang, days=7)
        elif action == 'help':
            text = t(lang, 'help_text')
        elif action == 'lang':
            return TelegramConversationHandler._start_language_selection(session)
        else:
            text = t(lang, 'unknown_input')

        TelegramService.send_message(session.chat_id, text, inline_keyboard=main_menu_keyboard(lang))
        return {'status': f'menu_{action}_shown'}

    # ── Dose response ────────────────────────────────────────────────

    @staticmethod
    def _process_dose_response(session, intent) -> dict:
        """
        Logs the dose directly against ReminderJob/DoseLog (apps.scheduling) —
        NOT via AdherenceAgent.log_dose(), which references a non-existent
        apps.telemetry.models.AdherenceEvent and would crash.
        """
        from apps.scheduling.models import ReminderJob, DoseLog, ReminderStatus, DoseSource
        lang = session.language

        context = session.state_data or {}
        reminder_id = context.get('reminder_job_id')
        if not reminder_id:
            session.state = 'IDLE'
            session.state_data = {}
            session.save(update_fields=['state', 'state_data', 'updated_at'])
            TelegramService.send_message(session.chat_id, t(lang, 'no_reminder_context'))
            return {'status': 'no_reminder_context'}

        try:
            reminder = ReminderJob.objects.select_related('schedule__prescription').get(id=reminder_id)
        except ReminderJob.DoesNotExist:
            session.state = 'IDLE'
            session.state_data = {}
            session.save(update_fields=['state', 'state_data', 'updated_at'])
            TelegramService.send_message(session.chat_id, t(lang, 'reminder_not_found'))
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
                'taken_at':     timezone.now() if status == ReminderStatus.TAKEN else None,
                'dose_value':   reminder.dose_value,
                'dose_unit':    reminder.dose_unit,
            }
        )

        session.state = 'IDLE'
        session.state_data = {}
        session.save(update_fields=['state', 'state_data', 'updated_at'])

        confirm_key = (
            'dose_recorded_taken' if status == ReminderStatus.TAKEN
            else 'dose_recorded_skipped' if status == ReminderStatus.SKIPPED
            else 'dose_recorded_missed'
        )
        TelegramService.send_message(session.chat_id, t(lang, confirm_key))
        return {'status': 'dose_response_processed', 'intent': intent}

    @staticmethod
    def set_session_awaiting_dose(chat_id, context: dict) -> None:
        """Called when a dose reminder is sent, so the next reply is parsed as Y/N/skip."""
        from .models import TelegramSession
        session = TelegramSession.objects.filter(chat_id=str(chat_id)).first()
        if not session:
            return
        session.state = 'AWAITING_DOSE_RESPONSE'
        session.state_data = context
        session.last_activity_at = timezone.now()
        session.save(update_fields=['state', 'state_data', 'last_activity_at', 'updated_at'])
        TelegramService.send_message(
            session.chat_id, t(session.language, 'dose_reminder_prompt'),
            inline_keyboard=dose_keyboard(session.language),
        )
