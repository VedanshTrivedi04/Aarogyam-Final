import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import TelegramService, TelegramConversationHandler

logger = logging.getLogger('medadhere')


class TelegramWebhookView(APIView):
    """
    Telegram Bot API webhook — POST-only. Handles two update shapes:
    - message: a typed reply (email, OTP, or stray text)
    - callback_query: a tap on an inline button (language, menu, dose Y/N/skip)
    """
    permission_classes = [AllowAny]

    def post(self, request):
        secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not TelegramService.verify_secret_token(secret):
            logger.warning("Telegram webhook secret token mismatch.")
            return Response({"status": "invalid_secret"}, status=403)

        update = request.data
        update_id = update.get('update_id')

        callback_query = update.get('callback_query')
        if callback_query:
            chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
            callback_data = callback_query.get('data', '')
            callback_query_id = callback_query.get('id')

            if not chat_id or not callback_query_id:
                return Response({"status": "invalid_data"}, status=400)

            logger.info(f"Telegram Callback from {chat_id}: {callback_data!r}")
            try:
                res = TelegramConversationHandler.handle_callback(chat_id, callback_data, update_id, callback_query_id)
                return Response({"status": "ok", "result": res})
            except Exception as e:
                logger.exception(f"Telegram Callback Error for {chat_id}: {e}")
                return Response({"status": "agent_error", "detail": str(e)}, status=200)

        message = update.get('message') or update.get('edited_message')
        if not message:
            # Other update types we don't handle (my_chat_member, ...) — ack and ignore.
            return Response({"status": "ignored"})

        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')

        if not chat_id:
            return Response({"status": "invalid_data"}, status=400)

        logger.info(f"Telegram Inbound from {chat_id}: {text[:50]!r}")
        try:
            res = TelegramConversationHandler.handle_message(chat_id, text, update_id)
            return Response({"status": "ok", "result": res})
        except Exception as e:
            logger.exception(f"Telegram Agent Error for {chat_id}: {e}")
            return Response({"status": "agent_error", "detail": str(e)}, status=200)
