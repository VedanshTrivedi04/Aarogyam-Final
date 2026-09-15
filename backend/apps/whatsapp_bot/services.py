import logging
import re
import secrets

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.identity.models import User

logger = logging.getLogger('medadhere')

OTP_TTL_SECONDS = 5 * 60
OTP_MAX_ATTEMPTS = 3


def normalize_phone(phone: str) -> str:
    """
    Reduce a phone number to its last 10 digits so numbers stored with/without
    '+91', spaces, dashes, etc. can still be matched against Twilio's 'From'
    address (which arrives as 'whatsapp:+919876543210').
    """
    digits = re.sub(r'\D', '', phone or '')
    return digits[-10:] if len(digits) >= 10 else digits


def to_e164(phone: str) -> str:
    """
    Convert a phone number in whatever format it's stored in (DB entries are
    unvalidated free text) into '+<countrycode><digits>' for Twilio's To/From
    fields, e.g. '+919876543210'. Assumes India (+91) when no country code
    is present.
    """
    digits = re.sub(r'\D', '', phone or '')
    if len(digits) == 10:
        digits = '91' + digits
    elif len(digits) == 11 and digits.startswith('0'):
        digits = '91' + digits[1:]
    return '+' + digits


class TwilioWhatsAppService:
    """
    Thin wrapper around Twilio's WhatsApp API (Sandbox or an approved Sender).
    Docs: https://www.twilio.com/docs/whatsapp/api
    """

    @staticmethod
    def send_text(to_phone: str, body: str) -> dict:
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        from_number = getattr(settings, 'TWILIO_WHATSAPP_FROM', '')

        if not account_sid or not auth_token:
            logger.warning(f"[MOCK] WhatsApp (Twilio) to {to_phone}: {body}")
            return {"status": "mocked"}

        try:
            from twilio.rest import Client
            from twilio.base.exceptions import TwilioRestException

            client = Client(account_sid, auth_token)
            msg = client.messages.create(
                body=body,
                from_=f"whatsapp:{to_e164(from_number)}",
                to=f"whatsapp:{to_e164(to_phone)}",
            )
            return {"sid": msg.sid, "status": msg.status}
        except TwilioRestException as e:
            logger.error(f"Twilio WhatsApp send failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Twilio WhatsApp Error: {e}")
            return {"error": str(e)}

    @staticmethod
    def verify_signature(url: str, params: dict, signature_header: str) -> bool:
        """
        Validate the X-Twilio-Signature header Twilio sends on every webhook
        POST, using the Auth Token. Rejects spoofed/forged webhook calls.
        `url` must be the exact URL Twilio requested (scheme+host+path+query,
        no trailing modifications) and `params` the parsed form-encoded body.
        """
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        if not auth_token:
            logger.warning("TWILIO_AUTH_TOKEN not set; skipping webhook signature check.")
            return True

        from twilio.request_validator import RequestValidator
        validator = RequestValidator(auth_token)
        return validator.validate(url, params, signature_header or '')


class WhatsAppMessageService:
    """Provider-agnostic facade used by the bot/agent layer."""

    @staticmethod
    def send(phone_number: str, text: str):
        return TwilioWhatsAppService.send_text(phone_number, text)


class WhatsAppVerificationService:
    """
    Links an inbound WhatsApp number to an existing MedAdhere account by
    matching it against User.phone_number already on file, then confirming
    ownership with an OTP sent over WhatsApp (no separate app step needed).
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
    def generate_and_send_otp(phone_number: str, user) -> None:
        code = f"{secrets.randbelow(1_000_000):06d}"
        cache.set(
            f"wa_otp:{phone_number}",
            {"code": code, "user_id": str(user.id), "attempts": 0},
            timeout=OTP_TTL_SECONDS,
        )
        WhatsAppMessageService.send(
            phone_number,
            f"Aapka MedAdhere verification code hai: *{code}*\n"
            f"Yeh {OTP_TTL_SECONDS // 60} minute mein expire ho jayega. Kisi ke saath share na karein."
        )

    @staticmethod
    def verify_otp(phone_number: str, submitted_code: str):
        """Returns the User on success, or a string reason on failure ('expired'|'invalid'|'locked')."""
        key = f"wa_otp:{phone_number}"
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


class WhatsAppStatusService:
    @staticmethod
    def get_today_summary(user_id: str):
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
            logger.error(f"WhatsApp Status Error: {e}")
            return "Maafi chahte hain, status fetch karne mein problem hui."
