"""
apps/geofence/views.py — Geofence management for caregivers + location reporting for patients.

Endpoints
─────────
Caregiver:
  POST   /api/v1/geofence/zones/                         — create zone for a patient (with Google Maps coords)
  GET    /api/v1/geofence/zones/?patient_id=<uuid>        — list zones caregiver manages for a patient
  PUT    /api/v1/geofence/zones/<id>/                     — update zone (change center / radius)
  DELETE /api/v1/geofence/zones/<id>/                     — deactivate zone
  POST   /api/v1/geofence/live-location/                  — share caregiver's live GPS → returns address

Patient:
  POST   /api/v1/geofence/location/                       — report current GPS; backend checks all zones
  GET    /api/v1/geofence/my-zones/                       — list all zones set for this patient
  GET    /api/v1/geofence/events/                         — history of entry/exit events
"""
import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from shared.response import APIResponse
from .models import GeofenceZone, GeofenceEvent, MAX_ZONE_RADIUS_METERS, MIN_ZONE_RADIUS_METERS, MAX_POLYGON_POINTS
from .serializers import GeofenceZoneSerializer, GeofenceEventSerializer
from .services import GeofenceService, reverse_geocode, validate_coordinates, haversine_distance

logger = logging.getLogger('medadhere.geofence')


def _parse_points(raw_points, anchor_lat: float, anchor_lng: float):
    """
    Validate a list of [lat, lng] polygon vertices: 3-8 points, each coordinate
    valid, and each within MAX_ZONE_RADIUS_METERS of the anchor point.
    Returns (points, error_response).
    """
    if not isinstance(raw_points, list) or not (3 <= len(raw_points) <= MAX_POLYGON_POINTS):
        return None, APIResponse.error(
            f'points must be a list of 3 to {MAX_POLYGON_POINTS} [latitude, longitude] pairs.', status=400
        )

    parsed = []
    for p in raw_points:
        try:
            p_lat, p_lng = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError, KeyError):
            return None, APIResponse.error('Each point must be a [latitude, longitude] pair of numbers.', status=400)

        if not validate_coordinates(p_lat, p_lng):
            return None, APIResponse.error('Invalid coordinates. lat must be -90–90, lng -180–180.', status=400)

        if haversine_distance(anchor_lat, anchor_lng, p_lat, p_lng) > MAX_ZONE_RADIUS_METERS:
            return None, APIResponse.error(
                f'Each point must be within {MAX_ZONE_RADIUS_METERS}m of the anchor location.', status=400
            )

        parsed.append([p_lat, p_lng])

    return parsed, None


def _get_patient_or_error(user):
    try:
        return user.patient_profile, None
    except Exception:
        return None, APIResponse.error('Patient profile not found.', status=404)


def _get_caregiver_or_error(user):
    try:
        return user.caregiver_profile, None
    except Exception:
        return None, APIResponse.error('Caregiver profile not found.', status=404)


def _caregiver_manages_patient(caregiver, patient_id: str) -> bool:
    """Check caregiver has an active link to this patient."""
    from apps.clinical.models import PatientCaregiverLink
    return PatientCaregiverLink.objects.filter(
        caregiver=caregiver,
        patient_id=patient_id,
        is_active=True,
    ).exists()


# ─── Caregiver: Create / list zones ──────────────────────────────────────────

class CaregiverZoneListCreateView(APIView):
    """
    POST /api/v1/geofence/zones/
    GET  /api/v1/geofence/zones/?patient_id=<uuid>

    Caregiver uses Google Maps to pick a location; the frontend sends lat/lng.
    Backend auto-fetches the address via Google Maps Geocoding API.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        caregiver, err = _get_caregiver_or_error(request.user)
        if err:
            return err

        patient_id = request.query_params.get('patient_id')
        qs = GeofenceZone.objects.filter(set_by_caregiver=caregiver, is_active=True)
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        return APIResponse.success(GeofenceZoneSerializer(qs, many=True).data)

    def post(self, request):
        caregiver, err = _get_caregiver_or_error(request.user)
        if err:
            return err

        patient_id = request.data.get('patient_id')
        if not patient_id:
            return APIResponse.error('patient_id is required.', status=400)

        if not _caregiver_manages_patient(caregiver, patient_id):
            return APIResponse.error('You are not linked to this patient.', status=403)

        from apps.clinical.models import Patient
        patient = get_object_or_404(Patient, id=patient_id)

        lat       = request.data.get('latitude')
        lng       = request.data.get('longitude')
        label     = request.data.get('label', 'Home Zone')
        zone_type = request.data.get('zone_type', 'CUSTOM')
        shape_type = request.data.get('shape_type', 'CIRCLE')

        if lat is None or lng is None:
            return APIResponse.error('latitude and longitude are required.', status=400)

        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            return APIResponse.error('latitude and longitude must be numbers.', status=400)

        if not validate_coordinates(lat, lng):
            return APIResponse.error('Invalid coordinates. lat must be -90–90, lng -180–180.', status=400)

        if shape_type not in ('CIRCLE', 'POLYGON'):
            return APIResponse.error('shape_type must be CIRCLE or POLYGON.', status=400)

        points = []
        if shape_type == 'POLYGON':
            points, err = _parse_points(request.data.get('points'), lat, lng)
            if err:
                return err
            # radius_meters kept in sync for map rendering / legacy consumers
            radius = round(max(haversine_distance(lat, lng, p[0], p[1]) for p in points))
        else:
            try:
                radius = int(request.data.get('radius_meters', MAX_ZONE_RADIUS_METERS))
            except (TypeError, ValueError):
                return APIResponse.error('radius_meters must be a number.', status=400)
            if radius < MIN_ZONE_RADIUS_METERS or radius > MAX_ZONE_RADIUS_METERS:
                return APIResponse.error(
                    f'radius_meters must be between {MIN_ZONE_RADIUS_METERS} and {MAX_ZONE_RADIUS_METERS}.', status=400
                )

        zone = GeofenceService.create_zone(
            patient=patient,
            caregiver=caregiver,
            lat=lat,
            lng=lng,
            radius=radius,
            label=label,
            zone_type=zone_type,
            shape_type=shape_type,
            points=points,
        )
        return APIResponse.created(GeofenceZoneSerializer(zone).data)


class CaregiverZoneDetailView(APIView):
    """PUT/DELETE /api/v1/geofence/zones/<id>/"""
    permission_classes = [IsAuthenticated]

    def _get_zone(self, request, zone_id):
        caregiver, err = _get_caregiver_or_error(request.user)
        if err:
            return None, None, err
        zone = get_object_or_404(GeofenceZone, id=zone_id, set_by_caregiver=caregiver)
        return caregiver, zone, None

    def put(self, request, zone_id):
        """Update zone center, radius/points, or label. Re-geocodes address if coords change."""
        _, zone, err = self._get_zone(request, zone_id)
        if err:
            return err

        lat        = request.data.get('latitude')
        lng        = request.data.get('longitude')
        radius     = request.data.get('radius_meters')
        label      = request.data.get('label')
        shape_type = request.data.get('shape_type')
        raw_points = request.data.get('points')

        if lat is not None and lng is not None:
            try:
                lat, lng = float(lat), float(lng)
            except (TypeError, ValueError):
                return APIResponse.error('Invalid coordinates.', status=400)
            if not validate_coordinates(lat, lng):
                return APIResponse.error('Coordinates out of valid range.', status=400)
            zone.latitude  = lat
            zone.longitude = lng
            zone.address   = reverse_geocode(lat, lng)

        if shape_type is not None:
            if shape_type not in ('CIRCLE', 'POLYGON'):
                return APIResponse.error('shape_type must be CIRCLE or POLYGON.', status=400)
            zone.shape_type = shape_type

        anchor_lat, anchor_lng = float(zone.latitude), float(zone.longitude)

        if zone.shape_type == 'POLYGON' and raw_points is not None:
            points, err = _parse_points(raw_points, anchor_lat, anchor_lng)
            if err:
                return err
            zone.points = points
            zone.radius_meters = round(max(haversine_distance(anchor_lat, anchor_lng, p[0], p[1]) for p in points))
        elif radius is not None:
            try:
                r = int(radius)
            except (TypeError, ValueError):
                return APIResponse.error('radius_meters must be a number.', status=400)
            if not (MIN_ZONE_RADIUS_METERS <= r <= MAX_ZONE_RADIUS_METERS):
                return APIResponse.error(
                    f'radius_meters must be between {MIN_ZONE_RADIUS_METERS} and {MAX_ZONE_RADIUS_METERS}.', status=400
                )
            zone.radius_meters = r
            zone.points = []

        if label:
            zone.label = label

        zone.save()
        return APIResponse.success(GeofenceZoneSerializer(zone).data, message='Zone updated.')

    def delete(self, request, zone_id):
        """Deactivate (soft-delete) the zone."""
        _, zone, err = self._get_zone(request, zone_id)
        if err:
            return err
        zone.is_active = False
        zone.save(update_fields=['is_active', 'updated_at'])
        return APIResponse.no_content('Zone deactivated.')


# ─── Caregiver: view a patient's geofence event history ──────────────────────

class CaregiverZoneEventsView(APIView):
    """GET /api/v1/geofence/zones/events/?patient_id=<uuid>&limit=20"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        caregiver, err = _get_caregiver_or_error(request.user)
        if err:
            return err

        patient_id = request.query_params.get('patient_id')
        if not patient_id:
            return APIResponse.error('patient_id is required.', status=400)

        if not _caregiver_manages_patient(caregiver, patient_id):
            return APIResponse.error('You are not linked to this patient.', status=403)

        limit  = min(int(request.query_params.get('limit', 20)), 100)
        events = (
            GeofenceEvent.objects
            .filter(patient_id=patient_id)
            .select_related('zone', 'patient__user')
            .order_by('-triggered_at')[:limit]
        )
        return APIResponse.success(GeofenceEventSerializer(events, many=True).data)


# ─── Caregiver: share live location ───────────────────────────────────────────

class CaregiverLiveLocationView(APIView):
    """
    POST /api/v1/geofence/live-location/

    Caregiver sends their current GPS coordinates (from Google Maps / device GPS).
    Returns the reverse-geocoded address so the caregiver can confirm the location
    before using it as a geofence center.

    Body: { "latitude": 28.6139, "longitude": 77.2090 }
    Response: { "latitude": ..., "longitude": ..., "address": "Connaught Place, New Delhi..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')

        if lat is None or lng is None:
            return APIResponse.error('latitude and longitude are required.', status=400)

        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            return APIResponse.error('Coordinates must be numeric.', status=400)

        if not validate_coordinates(lat, lng):
            return APIResponse.error('Coordinates out of valid range.', status=400)

        address = reverse_geocode(lat, lng)

        return APIResponse.success({
            'latitude':  lat,
            'longitude': lng,
            'address':   address or 'Address unavailable',
        })


# ─── Patient: report location → geofence check ────────────────────────────────

class PatientLocationUpdateView(APIView):
    """
    POST /api/v1/geofence/location/

    Patient app sends current GPS coordinates (polled every ~30 s by the mobile app).
    Backend checks all active zones, detects EXIT events, and fires alerts + Twilio call
    if the patient has pending upcoming doses.

    Body:   { "latitude": 28.6200, "longitude": 77.2100 }
    Response: { "zones_checked": 2, "alerts": [...], "has_alerts": true }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patient, err = _get_patient_or_error(request.user)
        if err:
            return err

        lat = request.data.get('latitude')
        lng = request.data.get('longitude')

        if lat is None or lng is None:
            return APIResponse.error('latitude and longitude are required.', status=400)

        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            return APIResponse.error('Coordinates must be numeric.', status=400)

        result = GeofenceService.check_patient_location(patient, lat, lng)
        return APIResponse.success(result)


# ─── Patient: view their zones ────────────────────────────────────────────────

class PatientMyZonesView(APIView):
    """GET /api/v1/geofence/my-zones/ — patient sees all active zones set for them."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient, err = _get_patient_or_error(request.user)
        if err:
            return err

        zones = GeofenceZone.objects.filter(patient=patient, is_active=True).select_related('set_by_caregiver__user')
        return APIResponse.success(GeofenceZoneSerializer(zones, many=True).data)


# ─── Patient: geofence event history ─────────────────────────────────────────

class GeofenceEventHistoryView(APIView):
    """GET /api/v1/geofence/events/?limit=20 — patient's zone crossing history."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient, err = _get_patient_or_error(request.user)
        if err:
            return err

        limit  = min(int(request.query_params.get('limit', 20)), 100)
        events = (
            GeofenceEvent.objects
            .filter(patient=patient)
            .select_related('zone')
            .order_by('-triggered_at')[:limit]
        )
        return APIResponse.success(GeofenceEventSerializer(events, many=True).data)
