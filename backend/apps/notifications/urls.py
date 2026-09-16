"""
apps/notifications/urls.py
"""
from django.urls import path
from .views import (
    NotificationListView, NotificationMarkReadView,
    NotificationMarkAllReadView, NotificationDeleteView,
    SMSWebhookView, SOSTriggerView,
)

urlpatterns = [
    path('',                NotificationListView.as_view(),        name='notifications'),
    path('read-all/',       NotificationMarkAllReadView.as_view(), name='notification-read-all'),
    path('read-all',        NotificationMarkAllReadView.as_view(), name='notification-read-all-alt'),
    path('<uuid:notification_id>/read/', NotificationMarkReadView.as_view(), name='notification-read'),
    path('<uuid:notification_id>/read',  NotificationMarkReadView.as_view(), name='notification-read-alt'),
    path('<uuid:notification_id>/',      NotificationDeleteView.as_view(),   name='notification-delete'),
    path('<uuid:notification_id>',       NotificationDeleteView.as_view(),   name='notification-delete-alt'),
    path('sms/webhook/',    SMSWebhookView.as_view(),              name='sms-webhook'),
    path('sos/trigger/',    SOSTriggerView.as_view(),              name='sos-trigger'),
]
