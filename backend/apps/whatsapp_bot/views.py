import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from agenthandover import AgentRegistry, AgentNotFoundError
from .services import TwilioWhatsAppService

logger = logging.getLogger('medadhere')


class WhatsAppWebhookView(APIView):
    """
    Twilio WhatsApp webhook — POST-only. Twilio form-encodes the body, so
    DRF's request.data already gives us a flat dict (no GET verification
    handshake like Meta's Cloud API requires).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        params = request.data
        signature = request.headers.get('X-Twilio-Signature', '')
        # Twilio signs the exact URL it called — must match scheme+host+path+query.
        url = request.build_absolute_uri()

        if not TwilioWhatsAppService.verify_signature(url, dict(params.items()), signature):
            logger.warning("Twilio webhook signature verification failed.")
            return Response({"status": "invalid_signature"}, status=403)

        phone = params.get('From', '').replace('whatsapp:', '')
        body = params.get('Body', '')
        wa_msg_id = params.get('MessageSid') or params.get('SmsMessageSid', '')

        if not phone or not wa_msg_id:
            return Response({"status": "invalid_data"}, status=400)

        try:
            agent = AgentRegistry.get('WhatsAppBotAgent')
        except AgentNotFoundError:
            logger.error("WhatsAppBotAgent not registered; is apps.core bootstrapped?")
            return Response({"status": "agent_not_ready"}, status=200)

        logger.info(f"WhatsApp Inbound from {phone}: {body[:50]!r}")
        try:
            res = agent.handle_inbound_message(phone, body, wa_msg_id)
            return Response({"status": "ok", "result": res})
        except Exception as e:
            logger.exception(f"WhatsApp Agent Error for {phone}: {e}")
            return Response({"status": "agent_error", "detail": str(e)}, status=200)
