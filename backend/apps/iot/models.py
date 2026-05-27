"""
apps/iot/models.py — IoT Device management, heartbeats, event ingestion, command queue,
                     meal tracking, and smart compartment inventory.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from shared.models import BaseModel


class Device(BaseModel):
    """
    A physical IoT pill dispenser linked to a user/patient.
    Auth: api_key (X-Device-Key header) — firmware never uses JWT.
    """
    DEVICE_TYPES = [
        ('CIRCULAR_PILL_DISPENSER', 'Circular Pill Dispenser'),
        ('PILLBOX', 'Smart Pillbox'),
        ('WEARABLE', 'Wearable'),
        ('MONITOR', 'Vital Monitor'),
        ('OTHER', 'Other'),
    ]
    HARDWARE_STATUS = [('ok', 'OK'), ('warning', 'Warning'), ('error', 'Error')]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='smart_devices'
    )
    linked_patient = models.ForeignKey(
        'clinical.Patient', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='smart_devices'
    )
    unique_id_record = models.OneToOneField(
        'store.DeviceUniqueID', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='linked_device'
    )
    device_name = models.CharField(max_length=200)
    device_type = models.CharField(max_length=40, choices=DEVICE_TYPES, default='CIRCULAR_PILL_DISPENSER')
    api_key = models.CharField(max_length=255, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    battery_level = models.PositiveSmallIntegerField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    total_doses_dispensed = models.PositiveIntegerField(default=0)

    # Caregiver contact for missed-dose alerts
    caregiver_name = models.CharField(max_length=200, blank=True)
    caregiver_phone = models.CharField(max_length=20, blank=True)   # WhatsApp/SMS
    caregiver_email = models.EmailField(blank=True)

    # Chemist contact for auto-refill orders
    chemist_name = models.CharField(max_length=200, blank=True)
    chemist_phone = models.CharField(max_length=20, blank=True)

    # Hardware component health (populated from heartbeats)
    stepper_status = models.CharField(max_length=20, choices=HARDWARE_STATUS, default='ok')
    servo_status = models.CharField(max_length=20, choices=HARDWARE_STATUS, default='ok')
    ultrasonic_status = models.CharField(max_length=20, choices=HARDWARE_STATUS, default='ok')

    # Fill mode state tracking
    fill_mode_active = models.BooleanField(default=False)
    fill_mode_compartment = models.PositiveSmallIntegerField(null=True, blank=True)

    # Dispenser state (new)
    is_gate_locked = models.BooleanField(default=False)
    current_compartment_position = models.PositiveSmallIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=['api_key'], name='idx_iot_device_api_key')]

    def __str__(self):
        return f"{self.device_name} ({self.device_type})"

    def is_online(self) -> bool:
        """True if last heartbeat was within the last 15 minutes."""
        if not self.last_seen_at:
            return False
        return (timezone.now() - self.last_seen_at).total_seconds() < 900


class DeviceHeartbeat(models.Model):
    """Health history — one row per heartbeat ping from firmware."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='heartbeats')
    battery_level = models.PositiveSmallIntegerField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    wifi_strength = models.IntegerField(null=True, blank=True)
    uptime_seconds = models.PositiveIntegerField(default=0)
    stepper_status = models.CharField(max_length=20, default='ok')
    servo_status = models.CharField(max_length=20, default='ok')
    ultrasonic_status = models.CharField(max_length=20, default='ok')

    class Meta:
        ordering = ['-created_at']


class DeviceEvent(BaseModel):
    """
    Immutable log of every hardware event.
    Clinical record — NEVER deleted or updated after creation.
    """
    EVENT_TYPES = [
        ('DEVICE_BOOT', 'Device Boot'),
        ('HEARTBEAT', 'Heartbeat'),
        ('COMPARTMENT_ROTATED', 'Compartment Rotated'),
        ('HAND_DETECTED', 'Hand Detected'),
        ('LID_OPENED', 'Lid Opened'),
        ('LID_CLOSED', 'Lid Closed'),
        ('DOSE_TAKEN', 'Dose Taken'),
        ('DOSE_TIMEOUT', 'Dose Timeout (Missed)'),
        ('DOSE_SKIPPED', 'Dose Skipped'),
        ('DOSE_DUPLICATE_BLOCKED', 'Duplicate Dose Blocked'),
        ('COMMAND_ACKNOWLEDGED', 'Command Acknowledged'),
        ('FILL_STARTED', 'Fill Mode Started'),
        ('FILL_CONFIRMED', 'Fill Confirmed by User'),
        ('FILL_COMPLETED', 'Fill Mode Completed'),
        ('DOSE_MISSED', 'Dose Missed'),
        ('COMPARTMENT_OPEN', 'Compartment Opened'),
        ('LOW_BATTERY', 'Low Battery'),
        ('TAMPER', 'Tamper Detected'),
        ('DEVICE_ON', 'Device Powered On'),
        ('DEVICE_OFF', 'Device Powered Off'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='events')
    event_uuid = models.CharField(max_length=64, unique=True, db_index=True)
    event_type = models.CharField(max_length=40, choices=EVENT_TYPES)
    compartment_num = models.PositiveSmallIntegerField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    adherence_event = models.ForeignKey(
        'telemetry.TelemetryEvent', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='iot_source_events'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.event_type}] device={self.device_id} uuid={self.event_uuid}"


class DeviceCompartmentMapping(models.Model):
    """
    Maps a physical compartment slot (1-12) to a prescription.
    Tracks inventory, meal dependency, priority, and fill status.
    """
    PRIORITY_CHOICES = [
        ('HIGH', 'High Priority'),
        ('NORMAL', 'Normal'),
    ]
    MEAL_DEPENDENCY_CHOICES = [
        ('NONE', 'No Dependency'),
        ('BEFORE_BREAKFAST', 'Before Breakfast'),
        ('AFTER_BREAKFAST', 'After Breakfast'),
        ('BEFORE_LUNCH', 'Before Lunch'),
        ('AFTER_LUNCH', 'After Lunch'),
        ('BEFORE_DINNER', 'Before Dinner'),
        ('AFTER_DINNER', 'After Dinner'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='compartments')
    compartment_number = models.PositiveSmallIntegerField()   # 1–12
    prescription = models.ForeignKey(
        'clinical.Prescription', on_delete=models.CASCADE, related_name='iot_compartments'
    )
    scheduled_times = models.JSONField(default=list)          # e.g. ["08:00", "20:00"]
    next_scheduled_time = models.DateTimeField(null=True, blank=True)

    # Smart fields
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    meal_dependency = models.CharField(
        max_length=20, choices=MEAL_DEPENDENCY_CHOICES, default='NONE'
    )
    medication_name = models.CharField(max_length=200, blank=True)  # For OLED display

    # Inventory tracking
    total_pills = models.PositiveIntegerField(default=0)
    pills_remaining = models.PositiveIntegerField(default=0)
    refill_alert_sent = models.BooleanField(default=False)

    # Fill mode tracking
    is_filled = models.BooleanField(default=False)
    last_filled_at = models.DateTimeField(null=True, blank=True)

    # Missed dose tracking (for caregiver alerts)
    last_dose_prepared_at = models.DateTimeField(null=True, blank=True)
    missed_dose_alert_sent = models.BooleanField(default=False)

    class Meta:
        unique_together = ('device', 'compartment_number')
        ordering = ['compartment_number']

    def __str__(self):
        return f"Device {self.device_id} | Compartment {self.compartment_number} | {self.medication_name}"

    def get_next_scheduled_time(self):
        """Return the next scheduled datetime for today."""
        now = timezone.localtime()
        for t in sorted(self.scheduled_times):
            h, m = map(int, t.split(':'))
            candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if candidate > now:
                return candidate
        return None

    def calculate_total_pills(self, doses_per_day: int, total_days: int) -> int:
        """Calculate total pills needed based on frequency and duration."""
        return doses_per_day * total_days

    def pills_days_remaining(self) -> int:
        """How many days of pills remain based on daily dose count."""
        doses_per_day = len(self.scheduled_times) if self.scheduled_times else 1
        if doses_per_day == 0:
            return 0
        return self.pills_remaining // doses_per_day

    def needs_refill_alert(self) -> bool:
        """True if less than 3 days of pills remain and alert not sent yet."""
        return self.pills_days_remaining() <= 3 and not self.refill_alert_sent


class DeviceCommand(BaseModel):
    """
    Backend-to-device command queue.
    Device polls GET /api/v1/iot/devices/{id}/commands/ every 30 seconds.
    """
    COMMAND_TYPES = [
        # Schedule sync
        ('SYNC_SCHEDULE', 'Sync Schedule'),
        # Dispense commands
        ('PREPARE_COMPARTMENT', 'Prepare Compartment'),
        ('FORCE_OPEN_LID', 'Force Open Lid'),
        ('CANCEL_DISPENSE', 'Cancel Dispense'),
        # Fill Mode (guided loading)
        ('START_FILL_MODE', 'Start Fill Mode'),
        ('NEXT_COMPARTMENT', 'Next Compartment (Fill)'),
        ('END_FILL_MODE', 'End Fill Mode'),
        # Safety
        ('RESET_FLAGS', 'Reset Daily Dispense Flags'),
        # Device control
        ('LOCK_DEVICE', 'Lock Device'),
        ('UPDATE_DISPLAY', 'Update Display'),
        ('FIRMWARE_UPDATE', 'Firmware Update'),
        ('SYNC_TIME', 'Sync Time'),
        # Gate control (new)
        ('GATE_LOCK', 'Lock Gate'),
        ('GATE_UNLOCK', 'Unlock Gate'),
        ('OPEN_GATE', 'Open Gate'),
        # Fill-mode weight measurement
        ('READ_FILL_WEIGHT', 'Read Fill Weight'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('EXECUTED', 'Executed'),
        ('FAILED', 'Failed'),
        ('EXPIRED', 'Expired'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='commands')
    command_type = models.CharField(max_length=30, choices=COMMAND_TYPES)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='issued_device_commands'
    )
    expires_at = models.DateTimeField()
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.command_type}] → {self.device.device_name} ({self.status})"


# ─── New: Dispenser Architecture ────────────────────────────────────────────

class PhysicalCompartment(BaseModel):
    """
    Represents one of the 4 physical compartments on the IoT device.
    Each compartment = a fixed time slot. Backend tracks weight balance here.
    ESP32 only knows compartment numbers (1-4) — never time slots or medicines.
    """
    TIME_SLOT_CHOICES = [
        ('morning_before', 'Morning Before Food'),
        ('morning_after', 'Morning After Food'),
        ('night_before', 'Night Before Food'),
        ('night_after', 'Night After Food'),
    ]

    # Default times used when no custom time is set
    SLOT_DEFAULT_TIMES = {
        'morning_before': '08:00',
        'morning_after':  '09:00',
        'night_before':   '20:00',
        'night_after':    '21:00',
    }

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='physical_compartments')
    compartment_number = models.PositiveSmallIntegerField()     # 1–4 (hardware fixed)
    time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES)
    scheduled_time = models.CharField(
        max_length=5, default='08:00',
        help_text='Custom alarm time in HH:MM format (24h). Caregiver can change this.'
    )
    expected_weight_grams = models.FloatField(default=0.0)      # set after filling mode
    current_balance_weight_grams = models.FloatField(default=0.0)  # updated after each dose
    is_active = models.BooleanField(default=True)
    last_filled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('device', 'compartment_number')
        ordering = ['compartment_number']

    def __str__(self):
        return f"Device {self.device_id} | Compartment {self.compartment_number} ({self.time_slot} @ {self.scheduled_time})"

    def get_time_slot_display_name(self) -> str:
        return dict(self.TIME_SLOT_CHOICES).get(self.time_slot, self.time_slot)

    def get_scheduled_hour_minute(self):
        """Return (hour, minute) from scheduled_time field."""
        try:
            h, m = map(int, self.scheduled_time.split(':'))
            return h, m
        except Exception:
            # Fallback to slot default if field is malformed
            default = self.SLOT_DEFAULT_TIMES.get(self.time_slot, '08:00')
            h, m = map(int, default.split(':'))
            return h, m



class SubCompartment(BaseModel):
    """
    Backend-only medicine entry within a PhysicalCompartment.
    ESP32 NEVER sees sub-compartments — it only deals with physical compartment numbers.
    """
    compartment = models.ForeignKey(
        PhysicalCompartment, on_delete=models.CASCADE, related_name='sub_compartments'
    )
    medicine_name = models.CharField(max_length=200)
    pill_weight_grams = models.FloatField(default=0.0)          # from AI analysis
    quantity_per_dose = models.PositiveIntegerField(default=1)
    duration_days = models.PositiveIntegerField(default=7)
    total_pills = models.PositiveIntegerField(default=0)        # qty * duration
    total_weight_grams = models.FloatField(default=0.0)         # pill_weight * qty * duration
    ai_analysis_data = models.JSONField(default=dict)           # full AI response stored here
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.medicine_name} in Compartment {self.compartment.compartment_number}"

    def dose_weight(self) -> float:
        """Weight reduction expected when this sub-compartment's dose is taken."""
        return self.pill_weight_grams * self.quantity_per_dose


class DoseSession(BaseModel):
    """
    Tracks one dose event: expected vs actual weight, gate open count, lock state.
    Created when dispensing starts; updated after weight reading arrives from ESP32.
    """
    DOSE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('taken', 'Taken'),
        ('partial', 'Partial'),
        ('missed', 'Missed'),
    ]

    compartment = models.ForeignKey(
        PhysicalCompartment, on_delete=models.CASCADE, related_name='dose_sessions'
    )
    scheduled_time = models.DateTimeField()
    expected_weight_before = models.FloatField(default=0.0)
    actual_weight_after = models.FloatField(null=True, blank=True)
    weight_reduction_actual = models.FloatField(null=True, blank=True)
    weight_reduction_expected = models.FloatField(default=0.0)
    dose_status = models.CharField(max_length=10, choices=DOSE_STATUS_CHOICES, default='pending')
    gate_open_count = models.PositiveSmallIntegerField(default=0)
    is_gate_locked = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-scheduled_time']

    def __str__(self):
        return f"DoseSession Compartment {self.compartment.compartment_number} | {self.dose_status}"


class WeightHistory(models.Model):
    """Raw weight readings from the load cell sent by ESP32."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='weight_history')
    compartment_number = models.PositiveSmallIntegerField()
    weight_grams = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Weight {self.weight_grams}g — Device {self.device_id} | Compartment {self.compartment_number}"


class GateEvent(models.Model):
    """Gate open/close events reported by ultrasonic sensor on ESP32."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='gate_events')
    compartment_number = models.PositiveSmallIntegerField()
    event_type = models.CharField(max_length=10, choices=[('open', 'Open'), ('close', 'Close')])
    session = models.ForeignKey(
        DoseSession, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='gate_events'
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"GateEvent {self.event_type} — Compartment {self.compartment_number}"


class MealLog(models.Model):
    """
    Daily meal check-in per user.
    Used to trigger meal-dependent medication dispensing.
    e.g., "After Breakfast" meds are queued only after patient marks breakfast done.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meal_logs'
    )
    date = models.DateField(default=timezone.now)

    breakfast_done = models.BooleanField(default=False)
    breakfast_time = models.DateTimeField(null=True, blank=True)

    lunch_done = models.BooleanField(default=False)
    lunch_time = models.DateTimeField(null=True, blank=True)

    dinner_done = models.BooleanField(default=False)
    dinner_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"MealLog {self.user_id} | {self.date}"
