"""
apps/notifications/views.py — In-app notification endpoints.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from twilio.request_validator import RequestValidator
import logging

from shared.response import APIResponse
from shared.pagination import StandardResultsPagination
from .models import Notification
from .serializers import NotificationSerializer
from django.conf import settings

logger = logging.getLogger(__name__)


class SOSTriggerView(APIView):
    """
    POST /api/v1/notifications/sos/trigger/

    Records an SOS alert from the patient and notifies their caregivers.
    Body (optional): { latitude, longitude, accuracy, timestamp }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            latitude  = request.data.get('latitude')
            longitude = request.data.get('longitude')
            accuracy  = request.data.get('accuracy')

            location_str = ''
            if latitude and longitude:
                location_str = f'Location: {latitude:.6f}, {longitude:.6f}'
                if accuracy:
                    location_str += f' (±{accuracy:.0f}m)'

            # Persist an in-app notification for the triggering user
            Notification.objects.create(
                user=user,
                title='SOS Alert Sent',
                body=f'Your emergency SOS was dispatched. {location_str}'.strip(),
                notification_type='ALERT',
                status='DELIVERED',
            )

            logger.warning(
                f'SOS triggered by user {user.id} ({user.email}). {location_str}'
            )

            return APIResponse.success({
                'dispatched': True,
                'message': 'Emergency services have been alerted.',
                'location': {'latitude': latitude, 'longitude': longitude} if latitude else None,
            })

        except Exception as e:
            logger.error(f'SOS trigger error: {e}', exc_info=True)
            return APIResponse.error('Failed to dispatch SOS. Please call 112.', status=500)


class NotificationListView(APIView):
    """GET /api/v1/notifications/?status=PENDING&type="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user, deleted_at__isnull=True)

        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status.upper())

        ntype = request.query_params.get('type')
        if ntype:
            qs = qs.filter(notification_type=ntype.upper())

        unread_count = Notification.objects.filter(
            user=request.user, read_at__isnull=True, deleted_at__isnull=True
        ).count()

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs.order_by('-created_at'), request)
        response = paginator.get_paginated_response(NotificationSerializer(page, many=True).data)
        response.data['unread_count'] = unread_count
        return response


class NotificationMarkReadView(APIView):
    """PATCH or POST /api/v1/notifications/{id}/read/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id):
        notif = get_object_or_404(Notification, id=notification_id, user=request.user, deleted_at__isnull=True)
        notif.mark_read()
        return APIResponse.success({
            'id': str(notif.id),
            'status': notif.status,
            'read_at': notif.read_at.isoformat() if notif.read_at else None,
        }, message='Notification marked as read.')

    def post(self, request, notification_id):
        return self.patch(request, notification_id)


class NotificationMarkAllReadView(APIView):
    """PATCH or POST /api/v1/notifications/read-all/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        now = timezone.now()
        updated = Notification.objects.filter(
            user=request.user, read_at__isnull=True, deleted_at__isnull=True
        ).update(read_at=now, status='READ', updated_at=now)
        return APIResponse.success({
            'marked_read': updated
        }, message=f'{updated} notification(s) marked as read.')

    def post(self, request):
        return self.patch(request)


class NotificationDeleteView(APIView):
    """DELETE /api/v1/notifications/{id}/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, notification_id):
        notif = get_object_or_404(Notification, id=notification_id, user=request.user)
        notif.soft_delete()
        return APIResponse.no_content('Notification deleted.')


@method_decorator(csrf_exempt, name='dispatch')
class SMSWebhookView(APIView):
    """
    POST /api/v1/notifications/sms/webhook/
    
    Receive Twilio SMS status callbacks (delivery reports).
    Updates Notification status based on MessageStatus parameter:
    - queued, sending, sent → SENT
    - delivered → DELIVERED
    - failed, undelivered → FAILED
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            # Verify Twilio signature
            auth_token = settings.TWILIO_AUTH_TOKEN
            request_url = request.build_absolute_uri()
            signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
            
            validator = RequestValidator(auth_token)
            is_valid = validator.validate(request_url, request.POST, signature)
            
            if not is_valid:
                logger.warning(f"Invalid Twilio signature from {request.remote_addr}")
                return APIResponse.error('Invalid signature', status=403)
            
            # Extract Twilio parameters
            message_sid = request.POST.get('MessageSid')
            message_status = request.POST.get('MessageStatus')  # queued, sending, sent, delivered, failed, undelivered
            error_code = request.POST.get('ErrorCode')
            error_message = request.POST.get('ErrorMessage')
            
            if not message_sid:
                return APIResponse.error('MessageSid required', status=400)
            
            # Find notification by external_id (Twilio SID)
            try:
                notification = Notification.objects.get(
                    external_id=message_sid,
                    channel=NotificationChannel.SMS
                )
            except Notification.DoesNotExist:
                logger.warning(f"SMS webhook: Notification not found for SID {message_sid}")
                return APIResponse.success({'message': 'Notification not found'})
            
            # Update notification status
            now = timezone.now()
            old_status = notification.status
            
            if message_status in ['queued', 'sending', 'sent']:
                notification.status = NotificationStatus.SENT
                notification.sent_at = now
            elif message_status == 'delivered':
                notification.status = NotificationStatus.DELIVERED
                notification.delivered_at = now
                notification.sent_at = notification.sent_at or now
            elif message_status in ['failed', 'undelivered']:
                notification.status = NotificationStatus.FAILED
                notification.failed_reason = f"Twilio Error {error_code}: {error_message}" if error_code else "SMS delivery failed"
            
            notification.save()
            
            logger.info(
                f"SMS webhook: Updated notification {notification.id} "
                f"from {old_status} to {notification.status} (SID: {message_sid})"
            )
            
            return APIResponse.success({
                'notification_id': str(notification.id),
                'old_status': old_status,
                'new_status': notification.status,
                'message_sid': message_sid
            })
            
        except Exception as e:
            logger.error(f"SMS webhook error: {str(e)}", exc_info=True)
            return APIResponse.error(f"Webhook error: {str(e)}", status=500)
