from django.urls import path
from .views import (
    CaregiverZoneListCreateView,
    CaregiverZoneDetailView,
    CaregiverZoneEventsView,
    CaregiverLiveLocationView,
    PatientLocationUpdateView,
    PatientMyZonesView,
    GeofenceEventHistoryView,
)

urlpatterns = [
    # Caregiver — zone management
    path('zones/',            CaregiverZoneListCreateView.as_view(), name='geofence-zones'),
    path('zones/events/',     CaregiverZoneEventsView.as_view(),     name='geofence-caregiver-events'),
    path('zones/<uuid:zone_id>/', CaregiverZoneDetailView.as_view(), name='geofence-zone-detail'),
    path('live-location/',    CaregiverLiveLocationView.as_view(),   name='geofence-live-location'),

    # Patient — location reporting & zone info
    path('location/',         PatientLocationUpdateView.as_view(),   name='geofence-location'),
    path('my-zones/',         PatientMyZonesView.as_view(),          name='geofence-my-zones'),
    path('events/',           GeofenceEventHistoryView.as_view(),    name='geofence-events'),
]
