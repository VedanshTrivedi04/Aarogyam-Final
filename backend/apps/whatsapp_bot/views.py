import json
import logging

from django.conf import settings
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from agenthandover import AgentRegistry, AgentNotFoundError
from .services import MetaWhatsAppService

logger = logging.getLogger('medadhere')


class WhatsAppWebhookView(APIView):
    """
    Meta WhatsApp Cloud API webhook.
    GET  — verification handshake performed once when you register the
           webhook URL in the Meta App dashboard.
    POST — inbound messages / delivery status updates.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        mode = request.query_params.get('hub.mode')
        token = request.query_params.get('hub.verify_token')
        challenge = request.query_params.get('hub.challenge')

        expected_token = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', '')
        if mode == 'subscribe' and expected_token and token == expected_token:
            logger.info("WhatsApp webhook verification succeeded.")
            return HttpResponse(challenge, content_type='text/plain', status=200)

        logger.warning("WhatsApp webhook verification failed (token mismatch).")
        return HttpResponse(status=403)

    def post(self, request):
        raw_body = request.body
        signature = request.headers.get('X-Hub-Signature-256', '')

        if not MetaWhatsAppService.verify_signature(raw_body, signature):
            logger.warning("WhatsApp webhook signature verification failed.")
            return Response({"status": "invalid_signature"}, status=403)

        try:
            payload = json.loads(raw_body or b'{}')
        except ValueError:
            return Response({"status": "invalid_json"}, status=400)

        try:
            agent = AgentRegistry.get('WhatsAppBotAgent')
        except AgentNotFoundError:
            logger.error("WhatsAppBotAgent not registered; is apps.core bootstrapped?")
            # Ack with 200 anyway so Meta doesn't disable/retry-storm the webhook.
            return Response({"status": "agent_not_ready"}, status=200)

        results = []
        for entry in payload.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                for message in value.get('messages', []):
                    phone = message.get('from')
                    wa_msg_id = message.get('id')
                    msg_type = message.get('type')

                    if msg_type == 'text':
                        body = message.get('text', {}).get('body', '')
                    elif msg_type == 'button':
                        body = message.get('button', {}).get('text', '')
                    elif msg_type == 'interactive':
                        interactive = message.get('interactive', {})
                        body = (
                            interactive.get('button_reply', {}).get('title')
                            or interactive.get('list_reply', {}).get('title')
                            or ''
                        )
                    else:
                        # Unsupported type (image, audio, location, ...) — ignore content
                        body = ''

                    if not phone or not wa_msg_id:
                        continue

                    logger.info(f"WhatsApp Inbound from {phone}: {body[:50]!r}")
                    try:
                        res = agent.handle_inbound_message(phone, body, wa_msg_id)
                        results.append(res)
                    except Exception as e:
                        logger.exception(f"WhatsApp Agent Error for {phone}: {e}")
                        results.append({"status": "agent_error", "detail": str(e)})
                # Delivery/read status callbacks land in value['statuses'] — nothing to do.

        return Response({"status": "ok", "results": results})
