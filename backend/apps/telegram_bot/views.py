import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import TelegramService, TelegramConversationHandler

logger = logging.getLogger('medadhere')


class TelegramWebhookView(APIView):
    """
    Telegram Bot API webhook — POST-only. Telegram JSON-encodes an "Update"
    object per call; no verification handshake like Meta, no signed request
    like Twilio — just an optional shared secret header we set via setWebhook.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not TelegramService.verify_secret_token(secret):
            logger.warning("Telegram webhook secret token mismatch.")
            return Response({"status": "invalid_secret"}, status=403)

        update = request.data
        update_id = update.get('update_id')
        message = update.get('message') or update.get('edited_message')

        if not message:
            # Other update types (callback_query, my_chat_member, ...) — ack and ignore.
            return Response({"status": "ignored"})

        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        contact = message.get('contact')
        contact_phone = contact.get('phone_number') if contact else None

        if not chat_id:
            return Response({"status": "invalid_data"}, status=400)

        logger.info(f"Telegram Inbound from {chat_id}: {(text or '[contact]')[:50]!r}")
        try:
            res = TelegramConversationHandler.handle_update(chat_id, text, contact_phone, update_id)
            return Response({"status": "ok", "result": res})
        except Exception as e:
            logger.exception(f"Telegram Agent Error for {chat_id}: {e}")
            return Response({"status": "agent_error", "detail": str(e)}, status=200)
