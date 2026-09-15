import hashlib
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


def normalize_phone(phone: str) -> str:
    """
    Reduce a phone number to its last 10 digits so numbers stored with/without
    '+91', spaces, dashes, etc. can still be matched against Meta's wa_id
    (which arrives as bare digits with country code, e.g. '919876543210').
    """
    digits = re.sub(r'\D', '', phone or '')
    return digits[-10:] if len(digits) >= 10 else digits


def to_whatsapp_id(phone: str) -> str:
    """
    Convert a phone number in whatever format it's stored in (DB entries are
    unvalidated free text) into the bare digits-with-country-code format the
    Meta Cloud API expects for the "to" field, e.g. '919876543210'.
    Assumes India (+91) when no country code is present.
    """
    digits = re.sub(r'\D', '', phone or '')
    if len(digits) == 10:
        return '91' + digits
    if len(digits) == 11 and digits.startswith('0'):
        return '91' + digits[1:]
    return digits


class MetaWhatsAppService:
    """
    Thin wrapper around the Meta WhatsApp Cloud API (Graph API).
    Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
    """

    @staticmethod
    def _api_url() -> str:
        version = getattr(settings, 'WHATSAPP_API_VERSION', 'v21.0')
        phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
        return f"https://graph.facebook.com/{version}/{phone_number_id}/messages"

    @staticmethod
    def send_text(to_phone: str, body: str) -> dict:
        """
        Send a free-form text message. Only deliverable within the 24h
        customer-service window opened by an inbound message from the user —
        fine for replies (OTP, status, dose confirmations), NOT guaranteed
        for cold outbound reminders (those need an approved message template).
        """
        token = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', None)
        phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', None)

        if not token or not phone_number_id:
            logger.warning(f"[MOCK] WhatsApp (Meta) to {to_phone}: {body}")
            return {"status": "mocked"}

        payload = {
            "messaging_product": "whatsapp",
            "to": to_whatsapp_id(to_phone),
            "type": "text",
            "text": {"body": body, "preview_url": False},
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                MetaWhatsAppService._api_url(),
                json=payload,
                headers=headers,
                timeout=10,
            )
            if response.status_code >= 400:
                logger.error(f"Meta WhatsApp send failed ({response.status_code}): {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Meta WhatsApp Error: {e}")
            return {"error": str(e)}

    @staticmethod
    def verify_signature(raw_body: bytes, signature_header: str) -> bool:
        """
        Validate the X-Hub-Signature-256 header Meta sends on every webhook
        POST, using the App Secret. Rejects spoofed/forged webhook calls.
        """
        app_secret = getattr(settings, 'WHATSAPP_APP_SECRET', '')
        if not app_secret:
            # No secret configured (e.g. local dev without a real Meta app yet) —
            # can't verify, so don't silently pretend it's safe.
            logger.warning("WHATSAPP_APP_SECRET not set; skipping webhook signature check.")
            return True

        if not signature_header or not signature_header.startswith('sha256='):
            return False

        expected = hmac.new(
            app_secret.encode('utf-8'), raw_body, hashlib.sha256
        ).hexdigest()
        provided = signature_header.split('sha256=', 1)[1]
        return hmac.compare_digest(expected, provided)


class WhatsAppMessageService:
    """Provider-agnostic facade used by the bot/agent layer."""

    @staticmethod
    def send(phone_number: str, text: str):
        return MetaWhatsAppService.send_text(phone_number, text)


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
