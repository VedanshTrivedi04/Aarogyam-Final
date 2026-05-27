"""
apps/iot/views.py — JWT user endpoints + Device-key firmware endpoints.
Includes: Fill Mode, Meal Log, Inventory, Priority Scheduling, Command Queue,
          Dispenser (4-compartment + sub-compartment), Weight verification,
          Gate events, Dose history/alerts, Sync time.
"""
import uuid
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from shared.response import APIResponse
from .models import (
    Device, DeviceCommand, DeviceEvent, DeviceCompartmentMapping, MealLog,
    PhysicalCompartment, SubCompartment, DoseSession,
)
from .serializers import (
    DeviceSerializer, DeviceEventSerializer, CompartmentMappingSerializer,
    DeviceCommandSerializer, EventIngestSerializer, DeviceHeartbeatSerializer,
    MealLogSerializer,
    PhysicalCompartmentSerializer, PhysicalCompartmentListSerializer,
    SubCompartmentSerializer, DoseSessionSerializer,
    WeightHistorySerializer, GateEventSerializer,
)
from .services import DeviceService, get_device_schedule, check_firmware_update
from apps.identity.authentication import MedAdhereJWTAuthentication
from .authentication import DeviceAPIKeyAuthentication


# ──────────────────────────────────────────────────────────────────
# JWT User views
# ──────────────────────────────────────────────────────────────────

class DeviceListView(APIView):
    """GET /api/v1/iot/devices/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = Device.objects.filter(user=request.user, deleted_at__isnull=True)
        return APIResponse.success(DeviceSerializer(devices, many=True).data)


class ValidateDeviceCodeView(APIView):
    """POST /api/v1/iot/devices/validate-code/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.store.models import DeviceUniqueID
        code = request.data.get('unique_code', '').strip().upper()
        if not code:
            return APIResponse.error("unique_code is required", status=400)
        try:
            uid = DeviceUniqueID.objects.get(unique_code=code)
        except DeviceUniqueID.DoesNotExist:
            return APIResponse.error("Invalid device code", code='INVALID_CODE', status=404)
        if uid.is_provisioned:
            return APIResponse.error("Device already registered", code='ALREADY_LINKED', status=409)
        return APIResponse.success({'valid': True, 'unique_code': code})


class DeviceLinkView(APIView):
    """POST /api/v1/iot/devices/link/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.store.models import DeviceUniqueID
        patient = getattr(request.user, 'patient_profile', None)
        device_name = request.data.get('device_name', 'My Device')
        device_type = request.data.get('device_type', 'CIRCULAR_PILL_DISPENSER')
        unique_code = request.data.get('unique_code', '').strip().upper()

        uid_record = None
        if unique_code:
            try:
                uid_record = DeviceUniqueID.objects.get(unique_code=unique_code)
                if uid_record.is_provisioned:
                    return APIResponse.error("Device code already registered", code='ALREADY_LINKED', status=409)
            except DeviceUniqueID.DoesNotExist:
                return APIResponse.error("Invalid device code", code='INVALID_CODE', status=404)

        device = DeviceService.link_device(request.user, patient, device_name, device_type)

        if uid_record:
            device.unique_id_record = uid_record
            device.save(update_fields=['unique_id_record'])
            uid_record.is_provisioned = True
            uid_record.save(update_fields=['is_provisioned'])

        return APIResponse.success(DeviceSerializer(device).data, status=201)


class DeviceProvisionView(APIView):
    """POST /api/v1/iot/devices/provision/  (no auth — ESP32 calls this on first boot)
    Body: { "product_key": "MEDA-XXXX-XXXX-XXXX" }
    Returns: { device_id, api_key }
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        from apps.store.models import DeviceUniqueID
        product_key = request.data.get('product_key', '').strip().upper()
        if not product_key:
            return APIResponse.error("product_key is required", status=400)
        try:
            uid = DeviceUniqueID.objects.get(unique_code=product_key)
        except DeviceUniqueID.DoesNotExist:
            return APIResponse.error("Invalid product key", status=404)
        try:
            device = uid.linked_device
        except Device.RelatedObjectDoesNotExist:
            return APIResponse.error("Device not yet linked by caregiver. Please complete setup in the app first.", status=404)
        return APIResponse.success({
            'device_id': str(device.id),
            'api_key': device.api_key,
        })


class DeviceDetailView(APIView):
    """GET / DELETE /api/v1/iot/devices/{pk}/"""
    permission_classes = [IsAuthenticated]

    def _get_device(self, request, pk):
        return get_object_or_404(Device, id=pk, user=request.user)

    def get(self, request, pk):
        device = self._get_device(request, pk)
        return APIResponse.success(DeviceSerializer(device).data)

    def patch(self, request, pk):
        """Update caregiver/chemist info."""
        device = self._get_device(request, pk)
        allowed = ['device_name', 'caregiver_name', 'caregiver_phone',
                   'caregiver_email', 'chemist_name', 'chemist_phone']
        for field in allowed:
            if field in request.data:
                setattr(device, field, request.data[field])
        device.save()
        return APIResponse.success(DeviceSerializer(device).data)

    def delete(self, request, pk):
        device = self._get_device(request, pk)
        device.is_active = False
        device.save(update_fields=['is_active'])
        return APIResponse.success(message='Device deactivated.')


class DeviceLinkPatientView(APIView):
    """
    PATCH /api/v1/iot/devices/{pk}/link-patient/
    Body: { "patient_id": "<uuid>" }  — or { "patient_id": null } to unlink.
    Links or unlinks a patient from the device.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        patient_id = request.data.get('patient_id')

        if patient_id:
            from apps.clinical.models import Patient
            patient = get_object_or_404(Patient, id=patient_id, deleted_at__isnull=True)
            device.linked_patient = patient
        else:
            device.linked_patient = None

        device.save(update_fields=['linked_patient'])
        return APIResponse.success(DeviceSerializer(device).data,
                                   message='Patient linked.' if patient_id else 'Patient unlinked.')


class DeviceUnlinkView(APIView):
    """DELETE /api/v1/iot/devices/{pk}/unlink/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        device.is_active = False
        device.save(update_fields=['is_active'])
        return APIResponse.success(message='Device unlinked.')


class DeviceStatusView(APIView):
    """GET /api/v1/iot/devices/{pk}/status/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        return APIResponse.success({
            'device_id': str(device.id),
            'device_name': device.device_name,
            'is_active': device.is_active,
            'is_online': device.is_online(),
            'battery_level': device.battery_level,
            'last_seen_at': device.last_seen_at,
            'firmware_version': device.firmware_version,
            'stepper_status': device.stepper_status,
            'servo_status': device.servo_status,
            'ultrasonic_status': device.ultrasonic_status,
            'total_doses_dispensed': device.total_doses_dispensed,
            'fill_mode_active': device.fill_mode_active,
            'caregiver_phone': device.caregiver_phone,
            'chemist_phone': device.chemist_phone,
        })


class DeviceEventsView(APIView):
    """GET /api/v1/iot/devices/{pk}/events/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        events = DeviceEvent.objects.filter(device=device).order_by('-created_at')[:50]
        return APIResponse.success(DeviceEventSerializer(events, many=True).data)


class DeviceCompartmentMappingView(APIView):
    """GET / PUT /api/v1/iot/devices/{device_id}/compartments/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, device_id):
        device = get_object_or_404(Device, id=device_id, user=request.user)
        mappings = device.compartments.select_related('prescription__medication').all()
        return APIResponse.success(CompartmentMappingSerializer(mappings, many=True).data)

    def put(self, request, device_id):
        """
        Register compartments with smart fields.
        Body: { "compartments": [
            { "compartment_number": 1, "prescription": "<uuid>",
              "scheduled_times": ["08:00"], "priority": "HIGH",
              "meal_dependency": "AFTER_BREAKFAST", "medication_name": "Aspirin 75mg",
              "total_pills": 30 }
        ]}
        """
        device = get_object_or_404(Device, id=device_id, user=request.user)
        mappings = request.data.get('compartments', [])
        DeviceService.update_compartments(device, mappings)
        return APIResponse.success(message='Compartments updated.')


# ──────────────────────────────────────────────────────────────────
# Fill Mode Views
# ──────────────────────────────────────────────────────────────────

class FillModeStartView(APIView):
    """
    POST /api/v1/iot/devices/{pk}/fill/start/
    Start guided fill mode: rotate device to compartment 1 (or specified),
    open lid, display medication name on OLED.
    Device waits for NEXT_COMPARTMENT or END_FILL_MODE command.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        compartment_num = int(request.data.get('compartment_number', 1))

        mapping = device.compartments.filter(compartment_number=compartment_num).first()
        if not mapping:
            return APIResponse.error(
                f"Compartment {compartment_num} not registered.", status=404
            )

        # Mark device fill mode
        device.fill_mode_active = True
        device.fill_mode_compartment = compartment_num
        device.save(update_fields=['fill_mode_active', 'fill_mode_compartment'])

        # Queue command to firmware
        cmd = DeviceCommand.objects.create(
            device=device,
            command_type='START_FILL_MODE',
            payload={
                'compartment': compartment_num,
                'medication_name': mapping.medication_name or 'Unknown',
                'total_pills': mapping.total_pills,
            },
            issued_by=request.user,
            expires_at=timezone.now() + timedelta(minutes=30),
        )

        return APIResponse.success({
            'command_id': str(cmd.id),
            'compartment': compartment_num,
            'medication_name': mapping.medication_name,
            'message': f'Fill mode started for compartment {compartment_num}. '
                       f'Lid opening on device...',
        }, status=201)


class FillModeNextView(APIView):
    """
    POST /api/v1/iot/devices/{pk}/fill/next/
    User confirms current compartment is filled → move to next.
    Body: { "current_compartment": 1 }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        current = int(request.data.get('current_compartment', 1))
        pills_added = int(request.data.get('pills_added', 0))

        # Update fill status and inventory for current compartment
        mapping = device.compartments.filter(compartment_number=current).first()
        if mapping:
            mapping.is_filled = True
            mapping.last_filled_at = timezone.now()
            if pills_added > 0:
                mapping.pills_remaining = pills_added
                mapping.refill_alert_sent = False  # reset alert flag on refill
            mapping.save()

        # Find next unfilled compartment
        next_mapping = device.compartments.filter(
            compartment_number__gt=current,
            is_filled=False
        ).order_by('compartment_number').first()

        if not next_mapping:
            # All compartments filled — end fill mode
            device.fill_mode_active = False
            device.fill_mode_compartment = None
            device.save(update_fields=['fill_mode_active', 'fill_mode_compartment'])
            DeviceCommand.objects.create(
                device=device,
                command_type='END_FILL_MODE',
                payload={'message': 'All compartments filled!'},
                issued_by=request.user,
                expires_at=timezone.now() + timedelta(minutes=5),
            )
            return APIResponse.success({
                'done': True,
                'message': 'All compartments filled! Closing lid...',
            })

        # Move to next compartment
        device.fill_mode_compartment = next_mapping.compartment_number
        device.save(update_fields=['fill_mode_compartment'])

        DeviceCommand.objects.create(
            device=device,
            command_type='NEXT_COMPARTMENT',
            payload={
                'compartment': next_mapping.compartment_number,
                'medication_name': next_mapping.medication_name or 'Unknown',
                'total_pills': next_mapping.total_pills,
            },
            issued_by=request.user,
            expires_at=timezone.now() + timedelta(minutes=30),
        )

        return APIResponse.success({
            'done': False,
            'next_compartment': next_mapping.compartment_number,
            'next_medication': next_mapping.medication_name,
            'message': f'Moving to compartment {next_mapping.compartment_number}...',
        })


class FillModeEndView(APIView):
    """
    POST /api/v1/iot/devices/{pk}/fill/end/
    Force-end fill mode. Closes lid and returns to idle.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        device.fill_mode_active = False
        device.fill_mode_compartment = None
        device.save(update_fields=['fill_mode_active', 'fill_mode_compartment'])

        DeviceCommand.objects.create(
            device=device,
            command_type='END_FILL_MODE',
            payload={},
            issued_by=request.user,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        return APIResponse.success({'message': 'Fill mode ended. Lid closing...'})


class CompartmentInventoryView(APIView):
    """
    GET /api/v1/iot/devices/{pk}/inventory/
    Returns inventory status of all compartments with refill alerts.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        mappings = device.compartments.all()

        inventory = []
        for m in mappings:
            inventory.append({
                'compartment': m.compartment_number,
                'medication_name': m.medication_name,
                'priority': m.priority,
                'meal_dependency': m.meal_dependency,
                'total_pills': m.total_pills,
                'pills_remaining': m.pills_remaining,
                'days_remaining': m.pills_days_remaining(),
                'needs_refill': m.needs_refill_alert(),
                'is_filled': m.is_filled,
                'last_filled_at': m.last_filled_at,
                'scheduled_times': m.scheduled_times,
            })

        return APIResponse.success({
            'device_name': device.device_name,
            'compartments': inventory,
            'fill_mode_active': device.fill_mode_active,
            'total_compartments': mappings.count(),
            'filled_count': mappings.filter(is_filled=True).count(),
        })


# ──────────────────────────────────────────────────────────────────
# Meal Log Views
# ──────────────────────────────────────────────────────────────────

class MealLogView(APIView):
    """
    GET  /api/v1/iot/meal-log/         — Today's meal log
    POST /api/v1/iot/meal-log/         — Mark a meal as done
    Body: { "meal": "breakfast" | "lunch" | "dinner" }
    This triggers meal-dependent medication commands automatically.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        log, _ = MealLog.objects.get_or_create(user=request.user, date=today)
        return APIResponse.success(MealLogSerializer(log).data)

    def post(self, request):
        meal = request.data.get('meal', '').lower()
        if meal not in ('breakfast', 'lunch', 'dinner'):
            return APIResponse.error(
                "meal must be 'breakfast', 'lunch', or 'dinner'", status=400
            )

        today = timezone.localdate()
        log, _ = MealLog.objects.get_or_create(user=request.user, date=today)

        now = timezone.now()
        if meal == 'breakfast' and not log.breakfast_done:
            log.breakfast_done = True
            log.breakfast_time = now
        elif meal == 'lunch' and not log.lunch_done:
            log.lunch_done = True
            log.lunch_time = now
        elif meal == 'dinner' and not log.dinner_done:
            log.dinner_done = True
            log.dinner_time = now
        else:
            return APIResponse.success({'message': f'{meal} already marked.'})

        log.save()

        # ── Auto-trigger meal-dependent medications ──────────────
        self._trigger_meal_medications(request.user, meal)

        return APIResponse.success({
            'message': f'{meal.title()} marked as done!',
            'meal_log': MealLogSerializer(log).data,
        })

    def _trigger_meal_medications(self, user, meal):
        """Queue PREPARE_COMPARTMENT for 'After <meal>' medications."""
        meal_map = {
            'breakfast': 'AFTER_BREAKFAST',
            'lunch': 'AFTER_LUNCH',
            'dinner': 'AFTER_DINNER',
        }
        dependency = meal_map.get(meal)
        if not dependency:
            return

        # Find all devices for this user
        devices = Device.objects.filter(user=user, is_active=True)
        for device in devices:
            mappings = device.compartments.filter(
                meal_dependency=dependency,
                is_filled=True,
            )
            for mapping in mappings:
                # Check priority — HIGH first
                DeviceCommand.objects.create(
                    device=device,
                    command_type='PREPARE_COMPARTMENT',
                    payload={
                        'compartment': mapping.compartment_number,
                        'medication_name': mapping.medication_name,
                        'reason': f'After {meal}',
                        'priority': mapping.priority,
                    },
                    issued_by=user,
                    expires_at=timezone.now() + timedelta(hours=2),
                )
                # Track for missed dose alert
                mapping.last_dose_prepared_at = timezone.now()
                mapping.missed_dose_alert_sent = False
                mapping.save(update_fields=['last_dose_prepared_at', 'missed_dose_alert_sent'])


# ──────────────────────────────────────────────────────────────────
# Device Command Queue (User → Device)
# ──────────────────────────────────────────────────────────────────

class DeviceCommandCreateView(APIView):
    """
    POST /api/v1/iot/devices/{pk}/commands/queue/
    Queue any command for the device.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        command_type = request.data.get('command_type')
        payload = request.data.get('payload', {})
        expires_in_minutes = int(request.data.get('expires_in_minutes', 60))

        if not command_type:
            return APIResponse.error("command_type is required", status=400)

        valid_types = [t[0] for t in DeviceCommand.COMMAND_TYPES]
        if command_type not in valid_types:
            return APIResponse.error(
                f"Invalid command_type. Valid: {valid_types}", status=400
            )

        cmd = DeviceCommand.objects.create(
            device=device,
            command_type=command_type,
            payload=payload,
            issued_by=request.user,
            expires_at=timezone.now() + timedelta(minutes=expires_in_minutes),
        )
        return APIResponse.success(DeviceCommandSerializer(cmd).data, status=201)


# ──────────────────────────────────────────────────────────────────
# Device-Key Firmware views
# ──────────────────────────────────────────────────────────────────

class DeviceEventIngestView(APIView):
    """
    POST /api/v1/iot/events/
    Firmware authenticates with X-Device-Key header.
    Handles: DOSE_TAKEN (decrements inventory), DOSE_TIMEOUT (triggers caregiver alert).
    """
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = []

    def post(self, request):
        device = request.auth
        if not device:
            return APIResponse.error("Missing or invalid X-Device-Key header", status=401)

        data = request.data
        if not data.get('event_uuid'):
            data = dict(data)
            data['event_uuid'] = str(uuid.uuid4())

        try:
            event, created, response_data = DeviceService.ingest_event(device, data)
        except ValueError as exc:
            return APIResponse.error(str(exc), status=400)

        if not created:
            return APIResponse.success({'status': 'duplicate_ignored'})

        # ── Post-event processing ────────────────────────────────
        event_type = data.get('event_type', '')
        compartment_num = data.get('compartment_num') or data.get('compartment')

        if event_type == 'DOSE_TAKEN' and compartment_num:
            self._handle_dose_taken(device, int(compartment_num))

        elif event_type in ('DOSE_TIMEOUT', 'DOSE_MISSED') and compartment_num:
            self._handle_dose_missed(device, int(compartment_num))

        return APIResponse.success({'status': 'accepted', **response_data})

    def _handle_dose_taken(self, device, compartment_num):
        """Decrement pill inventory and check refill threshold."""
        try:
            mapping = device.compartments.get(compartment_number=compartment_num)
            if mapping.pills_remaining > 0:
                mapping.pills_remaining -= 1
                mapping.missed_dose_alert_sent = False
                mapping.save(update_fields=['pills_remaining', 'missed_dose_alert_sent'])

                # Check if refill alert needed
                if mapping.needs_refill_alert():
                    from apps.iot.tasks import send_refill_alert
                    send_refill_alert.delay(str(mapping.id))
        except Exception:
            pass

    def _handle_dose_missed(self, device, compartment_num):
        """Trigger 30-min caregiver alert task."""
        try:
            mapping = device.compartments.get(compartment_number=compartment_num)
            if not mapping.missed_dose_alert_sent:
                from apps.iot.tasks import send_caregiver_missed_dose_alert
                send_caregiver_missed_dose_alert.delay(str(mapping.id))
        except Exception:
            pass


class DeviceHeartbeatView(APIView):
    """POST /api/v1/iot/heartbeat/"""
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = []

    def post(self, request):
        device = request.auth
        if not device:
            return APIResponse.error("Missing or invalid X-Device-Key header", status=401)
        result = DeviceService.record_heartbeat(device, request.data)
        return APIResponse.success(result)


class DeviceCommandPollView(APIView):
    """
    GET /api/v1/iot/devices/{device_id}/commands/
    Device polls every 30 seconds. Returns PENDING commands sorted by priority.
    HIGH PRIORITY compartments are always returned first.
    """
    authentication_classes = [DeviceAPIKeyAuthentication, MedAdhereJWTAuthentication]
    permission_classes = []

    def get(self, request, device_id):
        device = request.auth if hasattr(request.auth, 'api_key') else None
        if not device:
            if request.user and request.user.is_authenticated:
                device = Device.objects.filter(id=device_id, user=request.user, is_active=True).first()
                if not device:
                    return APIResponse.error("Forbidden", status=403)
            else:
                return APIResponse.error("Missing or invalid X-Device-Key header", status=401)
        elif str(device.id) != str(device_id):
            return APIResponse.error("Forbidden", status=403)

        pending = DeviceCommand.objects.filter(
            device=device,
            status='PENDING',
            expires_at__gt=timezone.now(),
        ).order_by('created_at')

        command_list = []
        ids_to_mark_sent = []

        # Sort: HIGH priority PREPARE_COMPARTMENT commands first
        high_prio = []
        normal = []
        for cmd in pending:
            priority = cmd.payload.get('priority', 'NORMAL')
            if cmd.command_type == 'PREPARE_COMPARTMENT' and priority == 'HIGH':
                high_prio.append(cmd)
            else:
                normal.append(cmd)

        for cmd in (high_prio + normal):
            command_list.append({
                'command_id': str(cmd.id),
                'type': cmd.command_type,
                'payload': cmd.payload,
            })
            ids_to_mark_sent.append(cmd.id)

        if ids_to_mark_sent:
            DeviceCommand.objects.filter(id__in=ids_to_mark_sent).update(status='SENT')

        return APIResponse.success({'commands': command_list})


# ──────────────────────────────────────────────────────────────────
# Legacy aliases
# ──────────────────────────────────────────────────────────────────
FirmwareEventIngestView = DeviceEventIngestView
FirmwareHeartbeatView = DeviceHeartbeatView


# ══════════════════════════════════════════════════════════════════
# DISPENSER ARCHITECTURE — 4-Compartment + Sub-Compartment System
# ══════════════════════════════════════════════════════════════════

class DispenserCompartmentSetupView(APIView):
    """
    POST /api/v1/iot/devices/<pk>/dispenser/setup/
    Create/reset the 4 physical compartments for a device (idempotent).
    Optionally pass custom times:
      { "times": { "morning_before": "07:30", "night_before": "21:00" } }
    """
    permission_classes = [IsAuthenticated]

    _SLOTS = [
        (1, 'morning_before'),
        (2, 'morning_after'),
        (3, 'night_before'),
        (4, 'night_after'),
    ]

    def post(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)

        # Optional custom times: { "morning_before": "07:30", ... }
        custom_times = request.data.get('times', {})

        compartments = []
        for num, slot in self._SLOTS:
            default_time = PhysicalCompartment.SLOT_DEFAULT_TIMES.get(slot, '08:00')
            scheduled_time = custom_times.get(slot, default_time)

            # Validate HH:MM format
            try:
                h, m = map(int, scheduled_time.split(':'))
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
                scheduled_time = f'{h:02d}:{m:02d}'
            except Exception:
                scheduled_time = default_time

            comp, created = PhysicalCompartment.objects.get_or_create(
                device=device,
                compartment_number=num,
                defaults={'time_slot': slot, 'scheduled_time': scheduled_time},
            )
            update_fields = []
            if comp.time_slot != slot:
                comp.time_slot = slot
                update_fields.append('time_slot')
            # Only overwrite time if caller explicitly passed a custom time
            if slot in custom_times and comp.scheduled_time != scheduled_time:
                comp.scheduled_time = scheduled_time
                update_fields.append('scheduled_time')
            if update_fields:
                comp.save(update_fields=update_fields)
            compartments.append(comp)

        return APIResponse.success(
            PhysicalCompartmentListSerializer(compartments, many=True).data,
            status=201,
        )


class DispenserUpdateSlotTimeView(APIView):
    """
    PATCH /api/v1/iot/devices/<pk>/dispenser/compartments/<compartment_num>/time/
    Caregiver can update the scheduled alarm time for any compartment at any time.
    Body: { "scheduled_time": "07:30" }   (24h HH:MM)
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, compartment_num):
        device = get_object_or_404(Device, id=pk, user=request.user)
        comp = get_object_or_404(
            PhysicalCompartment, device=device, compartment_number=compartment_num
        )
        time_str = request.data.get('scheduled_time', '').strip()
        if not time_str:
            return APIResponse.error('scheduled_time is required (HH:MM format)', status=400)
        try:
            h, m = map(int, time_str.split(':'))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            time_str = f'{h:02d}:{m:02d}'
        except Exception:
            return APIResponse.error('Invalid time format. Use HH:MM (24h), e.g. "07:30"', status=400)

        comp.scheduled_time = time_str
        comp.save(update_fields=['scheduled_time'])

        # Notify device to re-sync schedule
        DeviceCommand.objects.create(
            device=device,
            command_type='SYNC_SCHEDULE',
            payload={
                'reason': 'slot_time_updated',
                'compartment': compartment_num,
                'new_time': time_str,
                'time_slot': comp.time_slot,
            },
            issued_by=request.user,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        return APIResponse.success({
            'compartment_number': comp.compartment_number,
            'time_slot': comp.time_slot,
            'scheduled_time': comp.scheduled_time,
            'message': f'Alarm time updated to {time_str}. Device will sync on next poll.',
        })


class DispenserCompartmentListView(APIView):
    """
    GET /api/v1/iot/devices/<pk>/dispenser/compartments/
    List all 4 compartments with their sub-compartments and weight status.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)
        compartments = PhysicalCompartment.objects.filter(
            device=device, is_active=True
        ).prefetch_related('sub_compartments').order_by('compartment_number')
        return APIResponse.success(
            PhysicalCompartmentSerializer(compartments, many=True).data
        )


class DispenserAddMedicineView(APIView):
    """
    POST /api/v1/iot/devices/<pk>/dispenser/compartments/<num>/medicine/add/
    Add a medicine to a physical compartment.
    Pill weight is NOT estimated — it will be physically measured via load cell
    during filling using the measure-weight endpoint.
    Body: { "medicine_name": "Paracetamol", "total_pills": 30,
            "quantity_per_dose": 2, "duration_days": 7, "instructions": "..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, compartment_num):
        device = get_object_or_404(Device, id=pk, user=request.user)
        compartment = get_object_or_404(
            PhysicalCompartment, device=device, compartment_number=compartment_num
        )

        medicine_name = request.data.get('medicine_name', '').strip()
        if not medicine_name:
            return APIResponse.error("medicine_name is required", status=400)

        try:
            qty = int(request.data.get('quantity_per_dose', 1))
            duration = int(request.data.get('duration_days', 7))
            total_pills = int(request.data.get('total_pills', qty * duration))
        except (TypeError, ValueError):
            return APIResponse.error(
                "quantity_per_dose, duration_days, total_pills must be integers", status=400
            )

        if qty < 1 or duration < 1 or total_pills < 1:
            return APIResponse.error(
                "quantity_per_dose, duration_days, total_pills must be >= 1", status=400
            )

        instructions = request.data.get('instructions', '').strip()

        # Pill weight starts at 0 — will be set after physical load cell measurement
        sub = SubCompartment.objects.create(
            compartment=compartment,
            medicine_name=medicine_name,
            pill_weight_grams=0.0,      # set after measure-weight step
            quantity_per_dose=qty,
            duration_days=duration,
            total_pills=total_pills,
            total_weight_grams=0.0,     # set after measure-weight step
            ai_analysis_data={'source': 'load_cell_pending'},
            instructions=instructions,
        )

        # If this device is linked to a patient, create a prescription + schedule
        try:
            patient = device.linked_patient
            if patient:
                from apps.clinical.models import Medication, Prescription, MedicationSchedule
                from apps.clinical.services import PrescriptionService
                from apps.scheduling.services import ScheduleGenerationService
                # Find or create medication entry (best-effort)
                med, _ = Medication.objects.get_or_create(name__iexact=medicine_name, defaults={'name': medicine_name})

                # Build minimal prescription data — mark indefinite so end_date isn't required
                prescription_data = {
                    'medication': med,
                    'dosage_value': qty,
                    'dosage_unit': getattr(med, 'default_unit', 'tablet') or 'tablet',
                    'start_date': timezone.now().date(),
                    'is_indefinite': True,
                    'compartment_number': compartment_num,
                }

                try:
                    prescription = PrescriptionService.create(patient, prescription_data)

                    # Use the compartment's customisable scheduled_time (not hardcoded)
                    time_str = compartment.scheduled_time or compartment.SLOT_DEFAULT_TIMES.get(compartment.time_slot, '08:00')

                    schedule = MedicationSchedule.objects.create(
                        prescription=prescription,
                        frequency_type='DAILY',
                        times_of_day=[{'time': time_str, 'dose': qty, 'with_food': False, 'label': ''}],
                        days_of_week=list(range(7)),
                        timezone=getattr(patient, 'timezone', 'Asia/Kolkata') or 'Asia/Kolkata',
                    )

                    try:
                        ScheduleGenerationService.generate_upcoming_reminders(schedule, days=2)
                    except Exception:
                        # non-critical — continue
                        pass

                except Exception:
                    # swallow errors to avoid breaking dispenser flow
                    logger.exception('Failed to create prescription/schedule from dispenser add')
        except Exception:
            # Non-fatal — don't block the API call
            pass

        # Notify device about new medicine so it syncs its schedule immediately
        DeviceCommand.objects.create(
            device=device,
            command_type='SYNC_SCHEDULE',
            payload={
                'reason': 'medicine_added',
                'compartment': compartment_num,
                'medicine': medicine_name,
                'time_slot': compartment.time_slot,
            },
            issued_by=request.user,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        return APIResponse.success({
            'sub_compartment': SubCompartmentSerializer(sub).data,
            'message': (
                f'"{medicine_name}" registered. Now put all {total_pills} pills '
                f'into compartment {compartment_num} and call measure-weight.'
            ),
            'next_step': 'measure-weight',
        }, status=201)


class FillWeightMeasureView(APIView):
    """
    POST /api/v1/iot/devices/<pk>/dispenser/compartments/<num>/medicines/<medicine_id>/measure-weight/
    App calls this after caregiver physically adds a medicine's pills to the compartment.
    Backend queues READ_FILL_WEIGHT command → ESP32 reads load cell → posts to /events/fill-weight/.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, compartment_num, medicine_id):
        device = get_object_or_404(Device, id=pk, user=request.user)
        compartment = get_object_or_404(
            PhysicalCompartment, device=device, compartment_number=compartment_num
        )
        sub = get_object_or_404(SubCompartment, id=medicine_id, compartment=compartment, is_active=True)

        cmd = DeviceCommand.objects.create(
            device=device,
            command_type='READ_FILL_WEIGHT',
            payload={
                'medicine_id': str(sub.id),
                'medicine_name': sub.medicine_name,
                'total_pills': sub.total_pills,
                'compartment_number': compartment_num,
            },
            issued_by=request.user,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        return APIResponse.success({
            'command_id': str(cmd.id),
            'medicine_name': sub.medicine_name,
            'total_pills': sub.total_pills,
            'message': (
                f'Command queued. Device will read load cell weight for '
                f'"{sub.medicine_name}" ({sub.total_pills} pills) in compartment {compartment_num}.'
            ),
            'status': 'waiting_for_device',
        }, status=201)


class FillWeightIngestView(APIView):
    """
    POST /api/v1/iot/events/fill-weight/
    ESP32 calls this after reading load cell during fill mode.
    Backend calculates per-pill weight and updates SubCompartment.
    Body: { "compartment_number": 2, "weight_grams": 19.5, "medicine_id": "<uuid>" }
    Authentication: X-Device-Key header.

    Weight calculation logic:
      cumulative = sum of total_weight_grams of all previously measured medicines
      this_medicine_total = weight_grams - cumulative
      pill_weight = this_medicine_total / total_pills
    """
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = []

    def post(self, request):
        device = request.auth
        if not device:
            return APIResponse.error("Missing or invalid X-Device-Key", status=401)

        compartment_num = request.data.get('compartment_number')
        weight_raw = request.data.get('weight_grams')
        medicine_id = request.data.get('medicine_id', '').strip()

        if compartment_num is None or weight_raw is None or not medicine_id:
            return APIResponse.error(
                "compartment_number, weight_grams, and medicine_id are required", status=400
            )

        try:
            weight_grams = float(weight_raw)
            if weight_grams <= 0:
                return APIResponse.error("weight_grams must be > 0", status=400)
        except (TypeError, ValueError):
            return APIResponse.error("weight_grams must be a number", status=400)

        compartment = PhysicalCompartment.objects.filter(
            device=device, compartment_number=int(compartment_num)
        ).first()
        if not compartment:
            return APIResponse.error(f"Compartment {compartment_num} not found.", status=404)

        try:
            sub = SubCompartment.objects.get(id=medicine_id, compartment=compartment, is_active=True)
        except SubCompartment.DoesNotExist:
            return APIResponse.error("Medicine not found in this compartment.", status=404)

        # Sum all already-measured medicines (pill_weight > 0) in this compartment
        cumulative_grams = sum(
            s.total_weight_grams
            for s in compartment.sub_compartments.filter(is_active=True)
            if s.id != sub.id and s.pill_weight_grams > 0
        )

        this_medicine_total = weight_grams - cumulative_grams
        if this_medicine_total <= 0:
            return APIResponse.error(
                f"Measured weight ({weight_grams}g) is not greater than previously "
                f"measured medicines ({cumulative_grams}g). Check that pills were added.",
                status=400
            )

        pill_weight = round(this_medicine_total / sub.total_pills, 4)
        total_weight = round(this_medicine_total, 3)

        sub.pill_weight_grams = pill_weight
        sub.total_weight_grams = total_weight
        sub.ai_analysis_data = {
            'source': 'load_cell_measured',
            'raw_cumulative_weight_grams': cumulative_grams,
            'raw_total_weight_grams': weight_grams,
            'this_medicine_weight_grams': total_weight,
            'total_pills': sub.total_pills,
        }
        sub.save(update_fields=['pill_weight_grams', 'total_weight_grams', 'ai_analysis_data'])

        # Recalculate compartment expected weight from all measured medicines
        measured_subs = compartment.sub_compartments.filter(is_active=True, pill_weight_grams__gt=0)
        compartment.expected_weight_grams = round(
            sum(s.total_weight_grams for s in measured_subs), 3
        )
        compartment.save(update_fields=['expected_weight_grams'])

        return APIResponse.success({
            'medicine_name': sub.medicine_name,
            'total_pills': sub.total_pills,
            'this_medicine_weight_grams': total_weight,
            'pill_weight_grams': pill_weight,
            'cumulative_weight_grams': cumulative_grams,
            'compartment_expected_weight_grams': compartment.expected_weight_grams,
            'message': f'Weight measured: {pill_weight}g per pill for {sub.medicine_name}.',
        })


class DispenserMedicineListView(APIView):
    """
    GET  /api/v1/iot/devices/<pk>/dispenser/compartments/<num>/medicines/
    DELETE /api/v1/iot/devices/<pk>/dispenser/compartments/<num>/medicines/<medicine_id>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, compartment_num):
        device = get_object_or_404(Device, id=pk, user=request.user)
        compartment = get_object_or_404(
            PhysicalCompartment, device=device, compartment_number=compartment_num
        )
        subs = compartment.sub_compartments.filter(is_active=True)
        return APIResponse.success(SubCompartmentSerializer(subs, many=True).data)

    def delete(self, request, pk, compartment_num, medicine_id):
        device = get_object_or_404(Device, id=pk, user=request.user)
        compartment = get_object_or_404(
            PhysicalCompartment, device=device, compartment_number=compartment_num
        )
        sub = get_object_or_404(SubCompartment, id=medicine_id, compartment=compartment)
        sub.is_active = False
        sub.save(update_fields=['is_active'])

        # Recalculate compartment expected weight
        from .weight_service import calculate_compartment_expected_weight
        active_subs = compartment.sub_compartments.filter(is_active=True)
        compartment.expected_weight_grams = round(calculate_compartment_expected_weight(active_subs), 3)
        compartment.save(update_fields=['expected_weight_grams'])

        return APIResponse.success({'message': f'{sub.medicine_name} removed from compartment.'})


class DispenserFillCompleteView(APIView):
    """
    POST /api/v1/iot/devices/<pk>/dispenser/fill/complete/
    Confirm all compartments are filled. Locks in expected weights.
    Body: {} (optional: compartment_number to complete just one)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        device = get_object_or_404(Device, id=pk, user=request.user)

        compartment_num = request.data.get('compartment_number')
        qs = PhysicalCompartment.objects.filter(device=device, is_active=True)
        if compartment_num:
            qs = qs.filter(compartment_number=int(compartment_num))

        now = timezone.now()
        updated = []
        for comp in qs:
            comp.last_filled_at = now
            comp.current_balance_weight_grams = comp.expected_weight_grams
            comp.save(update_fields=['last_filled_at', 'current_balance_weight_grams'])
            updated.append(comp.compartment_number)

        # End fill mode on device
        device.fill_mode_active = False
        device.fill_mode_compartment = None
        device.save(update_fields=['fill_mode_active', 'fill_mode_compartment'])

        DeviceCommand.objects.create(
            device=device,
            command_type='END_FILL_MODE',
            payload={'message': 'Dispenser filled. Closing gate.'},
            issued_by=request.user,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        DeviceCommand.objects.create(
            device=device,
            command_type='SYNC_SCHEDULE',
            payload={
                'reason': 'fill_complete',
                'compartments_updated': updated,
            },
            issued_by=request.user,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        return APIResponse.success({
            'message': 'Fill confirmed. Expected weights locked.',
            'compartments_updated': updated,
        })


# ──────────────────────────────────────────────────────────────────
# Dispenser Schedule — current-schedule for ESP32 firmware
# ──────────────────────────────────────────────────────────────────

class DispenserCurrentScheduleView(APIView):
    """
    GET /api/v1/iot/devices/<device_id>/dispenser/schedule/current/
    Firmware polls this to know what to do right now.
    Returns: compartment_number, voice_text, display_text for current time slot.
    Also creates a DoseSession if within dose window (±10 minutes of slot time).
    Authentication: X-Device-Key header.
    """
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = []

    _SLOT_TIMES = {
        'morning_before': '08:00',
        'morning_after':  '09:00',
        'night_before':   '20:00',
        'night_after':    '21:00',
    }

    def get(self, request, device_id):
        device = request.auth
        if not device or str(device.id) != str(device_id):
            return APIResponse.error("Forbidden", status=403)

        from .ai_service import generate_voice_text, generate_display_text
        from .weight_service import calculate_dose_expected_reduction
        import datetime as dt
        import pytz

        # ── Always use IST for time comparisons ──────────────────────────────
        # TIME_ZONE='UTC' in settings, but caregivers set scheduled_time in IST.
        # So we always compare against IST wall-clock time.
        IST = pytz.timezone('Asia/Kolkata')
        now_utc = timezone.now()                     # UTC-aware
        now = now_utc.astimezone(IST)                # IST-aware
        now_utc_naive = now_utc                      # for DB filter (Django stores in UTC)

        # ── Priority 1: Manual trigger ("Take Medicine Now") ─────────────────
        # DoseSession created in last 30 min → return immediately at any time.
        manual_session = (
            DoseSession.objects
            .filter(
                compartment__device=device,
                dose_status='pending',
                created_at__gte=now_utc_naive - dt.timedelta(minutes=30),
            )
            .select_related('compartment')
            .prefetch_related('compartment__sub_compartments')
            .order_by('-created_at')
            .first()
        )

        if manual_session:
            comp = manual_session.compartment
            active_subs = comp.sub_compartments.filter(is_active=True)
            return APIResponse.success({
                'has_dose': True,
                'compartment_number': comp.compartment_number,
                'time_slot': comp.time_slot,
                'voice_text': generate_voice_text(comp.time_slot, active_subs),
                'display_text': generate_display_text(comp.time_slot, active_subs),
                'expected_weight_before': comp.current_balance_weight_grams,
                'session_id': str(manual_session.id),
                'server_time': now.isoformat(),
                'trigger': 'manual',
            })

        # ── Priority 2: DB-driven time-window check (IST) ────────────────────
        # scheduled_time is stored as HH:MM in IST (caregiver's local time).
        # Compare against current IST wall-clock — ±10 min window.
        active_slot = None
        matched_comp = None
        all_comps = PhysicalCompartment.objects.filter(
            device=device, is_active=True
        ).prefetch_related('sub_compartments')

        for c in all_comps:
            sh, sm = c.get_scheduled_hour_minute()
            # Build slot time in IST
            slot_dt = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
            diff_secs = abs((now - slot_dt).total_seconds())
            if diff_secs <= 600:        # ±10-minute window
                active_slot = c.time_slot
                matched_comp = c
                break

        if not active_slot:
            return APIResponse.success({
                'has_dose': False,
                'message': 'No dose scheduled for current time.',
                'server_time': now.isoformat(),
                'server_time_ist': now.strftime('%H:%M IST'),
            })

        comp = matched_comp
        active_subs = comp.sub_compartments.filter(is_active=True)

        voice_text = generate_voice_text(active_slot, active_subs)
        display_text = generate_display_text(active_slot, active_subs)

        # Create DoseSession if one doesn't exist for this slot today
        sh, sm = comp.get_scheduled_hour_minute()
        slot_dt = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        session, created = DoseSession.objects.get_or_create(
            compartment=comp,
            scheduled_time__date=now.date(),
            dose_status='pending',
            defaults={
                'scheduled_time': slot_dt,
                'expected_weight_before': comp.current_balance_weight_grams,
                'weight_reduction_expected': calculate_dose_expected_reduction(active_subs),
            }
        )

        return APIResponse.success({
            'has_dose': True,
            'compartment_number': comp.compartment_number,
            'time_slot': active_slot,
            'voice_text': voice_text,
            'display_text': display_text,
            'expected_weight_before': comp.current_balance_weight_grams,
            'session_id': str(session.id),
            'server_time': now.isoformat(),
            'trigger': 'scheduled',
        })




# ──────────────────────────────────────────────────────────────────
# Gate Event — firmware reports open/close
# ──────────────────────────────────────────────────────────────────

class GateEventView(APIView):
    """
    POST /api/v1/iot/events/gate-event/
    Firmware sends gate open/close events here.
    Body: { "compartment_number": 2, "event_type": "open" | "close" }
    Returns: { "gate_locked": bool, "gate_open_count": int, "command": str|null }
    Authentication: X-Device-Key header.
    """
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = []

    def post(self, request):
        device = request.auth
        if not device:
            return APIResponse.error("Missing or invalid X-Device-Key", status=401)

        compartment_num = request.data.get('compartment_number')
        event_type = request.data.get('event_type', '').lower()

        if compartment_num is None:
            return APIResponse.error("compartment_number is required", status=400)
        if event_type not in ('open', 'close'):
            return APIResponse.error("event_type must be 'open' or 'close'", status=400)

        from .weight_service import handle_gate_event
        result = handle_gate_event(device, int(compartment_num), event_type)

        return APIResponse.success(result)


# ──────────────────────────────────────────────────────────────────
# Weight Reading — firmware sends load cell value after gate close
# ──────────────────────────────────────────────────────────────────

class WeightReadingView(APIView):
    """
    POST /api/v1/iot/events/weight-reading/
    Firmware sends raw weight after gate closes.
    Body: { "compartment_number": 2, "weight_grams": 87.4 }
    Backend performs ALL verification — ESP32 sends number only.
    Authentication: X-Device-Key header.
    """
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = []

    def post(self, request):
        device = request.auth
        if not device:
            return APIResponse.error("Missing or invalid X-Device-Key", status=401)

        compartment_num = request.data.get('compartment_number')
        weight_raw = request.data.get('weight_grams')

        if compartment_num is None or weight_raw is None:
            return APIResponse.error("compartment_number and weight_grams are required", status=400)

        try:
            weight = float(weight_raw)
        except (TypeError, ValueError):
            return APIResponse.error("weight_grams must be a number", status=400)

        comp = PhysicalCompartment.objects.filter(
            device=device, compartment_number=int(compartment_num)
        ).first()
        if not comp:
            return APIResponse.error(
                f"Compartment {compartment_num} not found for this device.", status=404
            )

        from .weight_service import process_weight_reading
        result = process_weight_reading(comp, weight)

        # Notify caregiver for missed/partial (already done inside weight_service)
        # Queue missed dose event if status is missed
        if result.get('dose_status') in ('missed', 'partial'):
            self._handle_dose_missed_event(device, int(compartment_num))

        return APIResponse.success(result)

    def _handle_dose_missed_event(self, device, compartment_num):
        try:
            from apps.iot.tasks import send_caregiver_missed_dose_alert
            # Use existing task infrastructure — look up old mapping if exists
            mapping = device.compartments.filter(compartment_number=compartment_num).first()
            if mapping and not mapping.missed_dose_alert_sent:
                send_caregiver_missed_dose_alert.delay(str(mapping.id))
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────
# Dose Management — history, missed, alerts, caregiver unlock
# ──────────────────────────────────────────────────────────────────

class DoseHistoryView(APIView):
    """GET /api/v1/iot/dose/history/?device_id=<uuid>&limit=50"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        device_id = request.query_params.get('device_id')
        limit = min(int(request.query_params.get('limit', 50)), 200)

        qs = DoseSession.objects.filter(
            compartment__device__user=request.user
        ).select_related('compartment').order_by('-scheduled_time')

        if device_id:
            qs = qs.filter(compartment__device_id=device_id)

        return APIResponse.success(DoseSessionSerializer(qs[:limit], many=True).data)


class MissedDoseView(APIView):
    """GET /api/v1/iot/dose/missed/?device_id=<uuid>"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        device_id = request.query_params.get('device_id')

        qs = DoseSession.objects.filter(
            compartment__device__user=request.user,
            dose_status__in=['missed', 'partial'],
        ).select_related('compartment').order_by('-scheduled_time')

        if device_id:
            qs = qs.filter(compartment__device_id=device_id)

        return APIResponse.success(DoseSessionSerializer(qs[:100], many=True).data)


class CaregiverUnlockView(APIView):
    """
    POST /api/v1/iot/dose/caregiver-unlock/
    Caregiver remotely unlocks gate. Queues GATE_UNLOCK command for device.
    Body: { "device_id": "<uuid>" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        device_id = request.data.get('device_id')
        if not device_id:
            return APIResponse.error("device_id is required", status=400)

        # Allow caregiver OR device owner to unlock
        device = Device.objects.filter(id=device_id, is_active=True).first()
        if not device:
            return APIResponse.error("Device not found", status=404)

        if str(device.user_id) != str(request.user.id):
            return APIResponse.error("You do not have permission to unlock this device.", status=403)

        from .weight_service import caregiver_unlock
        result = caregiver_unlock(device)

        return APIResponse.success(result)


class DoseAlertsView(APIView):
    """
    GET /api/v1/iot/dose/alerts/
    Returns recent missed/partial/locked sessions as alerts.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = DoseSession.objects.filter(
            compartment__device__user=request.user,
            dose_status__in=['missed', 'partial'],
        ).select_related('compartment', 'compartment__device').order_by('-scheduled_time')[:50]

        alerts = []
        for s in sessions:
            alerts.append({
                'session_id': str(s.id),
                'device_name': s.compartment.device.device_name,
                'compartment_number': s.compartment.compartment_number,
                'time_slot': s.compartment.time_slot,
                'dose_status': s.dose_status,
                'gate_locked': s.is_gate_locked,
                'scheduled_time': s.scheduled_time.isoformat() if s.scheduled_time else None,
                'actual_reduction_grams': s.weight_reduction_actual,
                'expected_reduction_grams': s.weight_reduction_expected,
            })

        return APIResponse.success({'alerts': alerts, 'count': len(alerts)})


# ──────────────────────────────────────────────────────────────────
# Sync Time — ESP32 calls this to sync its RTC
# ──────────────────────────────────────────────────────────────────

class SyncTimeView(APIView):
    """
    GET /api/v1/iot/sync/time/
    Returns server Unix timestamp + ISO string for RTC sync.
    Authentication: X-Device-Key header.
    """
    authentication_classes = [DeviceAPIKeyAuthentication]
    permission_classes = []

    def get(self, request):
        now = timezone.now()
        return APIResponse.success({
            'unix_timestamp': int(now.timestamp()),
            'iso_time': now.isoformat(),
            'utc_offset_seconds': 0,
        })
