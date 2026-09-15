from rest_framework import serializers
from .models import GeofenceZone, GeofenceEvent


class GeofenceZoneSerializer(serializers.ModelSerializer):
    caregiver_name = serializers.SerializerMethodField()

    class Meta:
        model  = GeofenceZone
        fields = [
            'id', 'label', 'address', 'zone_type', 'shape_type',
            'latitude', 'longitude', 'radius_meters', 'points',
            'is_active', 'alert_on_exit_with_pending_dose',
            'caregiver_name', 'created_at',
        ]
        read_only_fields = ['id', 'address', 'caregiver_name', 'created_at']

    def get_caregiver_name(self, obj):
        if obj.set_by_caregiver:
            return obj.set_by_caregiver.user.full_name
        return None


class GeofenceEventSerializer(serializers.ModelSerializer):
    zone_label   = serializers.CharField(source='zone.label', read_only=True)
    patient_name = serializers.CharField(source='patient.user.full_name', read_only=True)

    class Meta:
        model  = GeofenceEvent
        fields = [
            'id', 'event_type', 'zone_label', 'patient_name',
            'patient_lat', 'patient_lng',
            'pending_meds', 'alert_sent', 'call_placed',
            'triggered_at',
        ]
        read_only_fields = fields
