"""
apps/geofence/services.py — Geofence check logic with Google Maps + dose-aware exit alerts.
"""
import math
import logging
import datetime
import requests

from django.conf import settings
from django.utils import timezone

from .models import GeofenceZone, GeofenceEvent

logger = logging.getLogger('medadhere.geofence')


# ─── Haversine distance ────────────────────────────────────────────────────────

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Returns straight-line distance in meters between two GPS coordinates."""
    R = 6_371_000  # Earth radius metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─── Google Maps helpers ───────────────────────────────────────────────────────

def reverse_geocode(lat: float, lng: float) -> str:
    """Return human-readable address for coordinates using Google Maps Geocoding API."""
    api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    if not api_key:
        return ''
    try:
        resp = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={'latlng': f'{lat},{lng}', 'key': api_key},
            timeout=5,
        )
        data = resp.json()
        if data.get('status') == 'OK' and data.get('results'):
            return data['results'][0]['formatted_address']
    except Exception as e:
        logger.warning(f'reverse_geocode failed for ({lat},{lng}): {e}')
    return ''


def validate_coordinates(lat: float, lng: float) -> bool:
    """Basic range check for latitude/longitude values."""
    return -90 <= lat <= 90 and -180 <= lng <= 180


def offset_meters(lat: float, lng: float, dx_m: float, dy_m: float) -> tuple[float, float]:
    """Approximate a lat/lng point offset by dx_m (east) / dy_m (north) meters."""
    R = 6_371_000
    d_lat = (dy_m / R) * (180 / math.pi)
    d_lng = (dx_m / (R * math.cos(math.pi * lat / 180))) * (180 / math.pi)
    return lat + d_lat, lng + d_lng


def point_in_polygon(lat: float, lng: float, points: list) -> bool:
    """
    Ray-casting point-in-polygon test. `points` is a list of [lat, lng] pairs.
    Treats lng as x and lat as y — fine at the small (<=100m) scale these zones use.
    """
    if len(points) < 3:
        return False
    inside = False
    x, y = lng, lat
    x1, y1 = points[-1][1], points[-1][0]
    for point in points:
        x2, y2 = point[1], point[0]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1):
            inside = not inside
        x1, y1 = x2, y2
    return inside


# ─── GeofenceService ──────────────────────────────────────────────────────────

class GeofenceService:

    @staticmethod
    def create_zone(patient, caregiver, lat: float, lng: float, radius: int,
                    label: str, zone_type: str = 'CUSTOM',
                    shape_type: str = 'CIRCLE', points: list | None = None) -> GeofenceZone:
        """
        Create a geofence zone for a patient, optionally set by a caregiver.
        Auto-populates the address via Google Maps reverse geocoding.
        """
        address = reverse_geocode(lat, lng)
        zone = GeofenceZone.objects.create(
            patient=patient,
            set_by_caregiver=caregiver,
            label=label,
            address=address,
            zone_type=zone_type,
            shape_type=shape_type,
            latitude=lat,
            longitude=lng,
            radius_meters=radius,
            points=points or [],
            is_active=True,
            alert_on_exit_with_pending_dose=True,
        )
        logger.info(
            f'GeofenceZone created: id={zone.id} patient={patient.patient_code} '
            f'label={label} shape={shape_type} radius={radius}m address="{address}"'
        )
        return zone

    @staticmethod
    def get_pending_doses(patient) -> list[dict]:
        """
        Returns upcoming dose reminders in the next 2 hours that are still PENDING.
        Used to decide whether to fire a geofence exit alert.
        """
        from apps.scheduling.models import ReminderJob
        now     = timezone.now()
        horizon = now + datetime.timedelta(hours=2)

        jobs = ReminderJob.objects.filter(
            schedule__prescription__patient=patient,
            status='PENDING',
            scheduled_at__gte=now,
            scheduled_at__lte=horizon,
        ).select_related('schedule__prescription__medication')

        return [
            {
                'name':  job.schedule.prescription.medication.name,
                'time':  job.scheduled_at.strftime('%I:%M %p'),
                'dose':  f'{job.dose_value} {job.dose_unit}',
            }
            for job in jobs
        ]

    @staticmethod
    def check_patient_location(patient, lat: float, lng: float) -> dict:
        """
        Main entry point called when the patient app reports a GPS location update.
        For every active geofence zone:
          - Compute distance from zone center
          - If patient just crossed the boundary (inside→outside): EXIT event
          - If patient crossed back (outside→inside): ENTRY event
          - On EXIT with pending doses → fire notification + Twilio voice call

        Returns a summary dict with any alerts that were triggered.
        """
        if not validate_coordinates(lat, lng):
            return {'error': 'Invalid coordinates', 'alerts': []}

        zones   = GeofenceZone.objects.filter(patient=patient, is_active=True)
        alerts  = []

        for zone in zones:
            distance = haversine_distance(lat, lng, float(zone.latitude), float(zone.longitude))
            if zone.shape_type == 'POLYGON' and zone.points:
                is_inside = point_in_polygon(lat, lng, zone.points)
            else:
                is_inside = distance <= zone.radius_meters

            # Determine previous state from most-recent event
            last_event = (
                GeofenceEvent.objects
                .filter(patient=patient, zone=zone)
                .order_by('-triggered_at')
                .first()
            )
            # No event history → assume patient was inside (zone was just created)
            was_inside = (last_event is None or last_event.event_type == 'ENTRY')

            if was_inside and not is_inside:
                # ── ZONE EXIT ────────────────────────────────────────────────
                pending = GeofenceService.get_pending_doses(patient) if zone.alert_on_exit_with_pending_dose else []

                event = GeofenceEvent.objects.create(
                    patient=patient,
                    zone=zone,
                    event_type='EXIT',
                    triggered_at=timezone.now(),
                    patient_lat=lat,
                    patient_lng=lng,
                    pending_meds=[m['name'] for m in pending],
                )

                if pending:
                    GeofenceService._fire_exit_alerts(patient, zone, pending, event)
                    alerts.append({
                        'zone':         zone.label,
                        'distance_m':   round(distance),
                        'pending_meds': [m['name'] for m in pending],
                    })

                logger.info(
                    f'GEOFENCE EXIT: patient={patient.patient_code} zone={zone.label} '
                    f'distance={distance:.0f}m pending_doses={len(pending)}'
                )

            elif not was_inside and is_inside:
                # ── ZONE ENTRY ───────────────────────────────────────────────
                GeofenceEvent.objects.create(
                    patient=patient,
                    zone=zone,
                    event_type='ENTRY',
                    triggered_at=timezone.now(),
                    patient_lat=lat,
                    patient_lng=lng,
                )
                logger.info(
                    f'GEOFENCE ENTRY: patient={patient.patient_code} zone={zone.label} '
                    f'distance={distance:.0f}m'
                )

        return {
            'zones_checked': zones.count(),
            'alerts':        alerts,
            'has_alerts':    bool(alerts),
        }

    @staticmethod
    def _fire_exit_alerts(patient, zone: GeofenceZone, pending_meds: list[dict],
                          event: GeofenceEvent):
        """
        Fire notification + Twilio voice call to patient when they exit a zone
        with pending doses. Also alert caregivers.
        """
        from apps.notifications.services import NotificationDispatcher
        from apps.clinical.models import PatientCaregiverLink

        med_names = ', '.join(m['name'] for m in pending_meds)

        # ── Patient notification (in-app + email) ─────────────────────────
        NotificationDispatcher.dispatch(
            user=patient.user,
            notification_type='GEOFENCE_EXIT',
            title='⚠️ Dawai liye bina bahar mat jaiye!',
            body=(
                f'Aap "{zone.label}" se bahar ja rahe hain lekin aapki '
                f'upcoming medicine abhi baaki hai: {med_names}. '
                f'Kripya pehle apni dawai lein!'
            ),
            data={
                'zone_id':     str(zone.id),
                'zone_label':  zone.label,
                'pending_meds': [m['name'] for m in pending_meds],
            },
            idempotency_key=f'geofence_exit:{event.id}:patient',
        )

        # ── Twilio voice call to patient ──────────────────────────────────
        patient_phone = getattr(patient.user, 'phone_number', None)
        call_placed   = False
        if patient_phone:
            try:
                from apps.notifications.twilio_service import call_patient_geofence_exit
                call_patient_geofence_exit(
                    patient_phone=patient_phone,
                    patient_name=patient.user.full_name,
                    pending_meds=pending_meds,
                    zone_label=zone.label,
                )
                call_placed = True
            except Exception as e:
                logger.error(f'Twilio call failed for patient={patient.patient_code}: {e}')

        # Update event record
        event.alert_sent  = True
        event.call_placed = call_placed
        event.save(update_fields=['alert_sent', 'call_placed', 'updated_at'])

        # ── Caregiver notifications ───────────────────────────────────────
        caregiver_links = PatientCaregiverLink.objects.filter(
            patient=patient, is_active=True, can_receive_alerts=True
        ).select_related('caregiver__user')

        for link in caregiver_links:
            NotificationDispatcher.dispatch(
                user=link.caregiver.user,
                notification_type='CAREGIVER_ALERT',
                title=f'🚨 {patient.user.full_name} zone se bahar gaye!',
                body=(
                    f'{patient.user.full_name} "{zone.label}" zone se bahar gaye hain '
                    f'bina dawai liye. Baaki medicines: {med_names}.'
                ),
                data={
                    'patient_id':  str(patient.id),
                    'zone_id':     str(zone.id),
                    'pending_meds': [m['name'] for m in pending_meds],
                },
                idempotency_key=f'geofence_exit:{event.id}:cg:{link.caregiver.id}',
            )

        logger.info(
            f'Geofence exit alerts fired: patient={patient.patient_code} '
            f'zone={zone.label} meds={med_names} call_placed={call_placed}'
        )
