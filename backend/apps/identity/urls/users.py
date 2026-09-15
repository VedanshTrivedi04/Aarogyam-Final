"""
apps/identity/urls/users.py — User profile URL patterns.
"""
from django.urls import path
from ..views.users import (
    UserMeView, UserAvatarUploadView, UserSessionListView, UserSessionRevokeView,
    NotificationPreferencesView, UserDeviceListCreateView, UserDeviceDeleteView,
)

urlpatterns = [
    path('me/',                          UserMeView.as_view(),                  name='user-me'),
    path('me/avatar/',                   UserAvatarUploadView.as_view(),        name='user-avatar-upload'),
    path('me/sessions/',                 UserSessionListView.as_view(),          name='user-sessions'),
    path('me/sessions/<uuid:session_id>/', UserSessionRevokeView.as_view(),     name='user-session-revoke'),
    path('me/notifications/',            NotificationPreferencesView.as_view(), name='user-notifications'),
    path('me/devices/',                  UserDeviceListCreateView.as_view(),     name='user-devices'),
    path('me/devices/<uuid:device_id>/', UserDeviceDeleteView.as_view(),         name='user-device-delete'),
]
