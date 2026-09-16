"""
config/ws_routing.py — WebSocket URL patterns.
"""
from django.urls import path
from apps.communications.consumers import (
    ChatConsumer, CallConsumer, DoctorChatConsumer, DoctorCallConsumer, NotificationConsumer,
)
from apps.iot.consumers import DeviceCommandConsumer

websocket_urlpatterns = [
    path('ws/chat/<uuid:room_id>/',            ChatConsumer.as_asgi()),
    path('ws/call/<uuid:room_id>/',            CallConsumer.as_asgi()),
    path('ws/doctor-chat/<uuid:session_id>/',  DoctorChatConsumer.as_asgi()),
    path('ws/doctor-call/<uuid:session_id>/',  DoctorCallConsumer.as_asgi()),
    path('ws/notifications/',                  NotificationConsumer.as_asgi()),
    # Dispenser firmware command channel (device_key auth, not JWT)
    path('ws/iot/device/<uuid:device_id>/',    DeviceCommandConsumer.as_asgi()),
]
