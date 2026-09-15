"""apps/geofence/models.py — Caregiver-managed geofencing with Google Maps integration."""
from django.db import models
from shared.models import BaseModel

ZONE_TYPES  = [('HOME', 'Home'), ('WORK', 'Work'), ('GYM', 'Gym'), ('CUSTOM', 'Custom')]
SHAPE_TYPES = [('CIRCLE', 'Circle'), ('POLYGON', 'Custom Shape')]
GEO_EVENT_TYPES = [('EXIT', 'Zone Exit'), ('ENTRY', 'Zone Entry')]

# Zones are small, walking-distance safe areas: no minimum size, capped at 100m
# from the anchor/center point (whether measured as a circle radius or as the
# distance of each custom-shape point from the anchor).
MAX_ZONE_RADIUS_METERS = 100
MIN_ZONE_RADIUS_METERS = 1
MAX_POLYGON_POINTS = 8


class GeofenceZone(BaseModel):
    patient          = models.ForeignKey('clinical.Patient', on_delete=models.CASCADE, related_name='geofence_zones')
    # Caregiver who created this zone (null = patient created their own)
    set_by_caregiver = models.ForeignKey('clinical.Caregiver', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='managed_zones')
    label            = models.CharField(max_length=100)
    address          = models.CharField(max_length=500, blank=True)  # reverse-geocoded via Google Maps
    zone_type        = models.CharField(max_length=10, choices=ZONE_TYPES, default='CUSTOM')
    shape_type       = models.CharField(max_length=10, choices=SHAPE_TYPES, default='CIRCLE')
    latitude         = models.DecimalField(max_digits=10, decimal_places=7)
    longitude        = models.DecimalField(max_digits=10, decimal_places=7)
    radius_meters    = models.PositiveIntegerField(default=100)
    # For shape_type=POLYGON: up to 8 [lat, lng] vertices, each within
    # MAX_ZONE_RADIUS_METERS of (latitude, longitude). Null/empty for circles.
    points           = models.JSONField(default=list, blank=True)
    is_active        = models.BooleanField(default=True)
    # Alert when patient exits with pending doses
    alert_on_exit_with_pending_dose = models.BooleanField(default=True)

    class Meta:
        db_table = 'geofence_zones'
        indexes  = [models.Index(fields=['patient', 'is_active'])]

    def __str__(self):
        if self.shape_type == 'POLYGON':
            return f'{self.label} (custom shape, {len(self.points)} pts)'
        return f'{self.label} ({self.zone_type}) r={self.radius_meters}m'


class GeofenceEvent(BaseModel):
    patient       = models.ForeignKey('clinical.Patient', on_delete=models.CASCADE, related_name='geofence_events')
    zone          = models.ForeignKey(GeofenceZone, on_delete=models.CASCADE, related_name='events')
    event_type    = models.CharField(max_length=10, choices=GEO_EVENT_TYPES)
    triggered_at  = models.DateTimeField()
    # Patient location at time of event
    patient_lat   = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    patient_lng   = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    # Which pending meds triggered the alert (populated on EXIT)
    pending_meds  = models.JSONField(default=list)
    alert_sent    = models.BooleanField(default=False)
    call_placed   = models.BooleanField(default=False)

    class Meta:
        db_table = 'geofence_events'
        indexes  = [models.Index(fields=['patient', 'triggered_at'])]

    def __str__(self):
        return f'{self.event_type} — {self.patient} @ {self.zone.label}'
