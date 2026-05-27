"""
apps/iot/serializers.py
"""
from rest_framework import serializers
from .models import (
    Device, DeviceCommand, DeviceEvent, DeviceHeartbeat,
    DeviceCompartmentMapping, MealLog,
    PhysicalCompartment, SubCompartment, DoseSession, WeightHistory, GateEvent,
)


class DeviceSerializer(serializers.ModelSerializer):
    is_online              = serializers.SerializerMethodField()
    linked_patient_id      = serializers.SerializerMethodField()
    linked_patient_name    = serializers.SerializerMethodField()
    linked_patient_code    = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            'id', 'device_name', 'device_type', 'api_key',
            'is_active', 'is_online', 'last_seen_at',
            'battery_level', 'firmware_version',
            'total_doses_dispensed',
            'stepper_status', 'servo_status', 'ultrasonic_status',
            'caregiver_name', 'caregiver_phone', 'caregiver_email',
            'chemist_name', 'chemist_phone',
            'fill_mode_active', 'fill_mode_compartment',
            'linked_patient_id', 'linked_patient_name', 'linked_patient_code',
        ]
        read_only_fields = ['api_key', 'last_seen_at', 'total_doses_dispensed']

    def get_is_online(self, obj):
        return obj.is_online()

    def get_linked_patient_id(self, obj):
        return str(obj.linked_patient_id) if obj.linked_patient_id else None

    def get_linked_patient_name(self, obj):
        if obj.linked_patient_id:
            try:
                return obj.linked_patient.user.full_name
            except Exception:
                return None
        return None

    def get_linked_patient_code(self, obj):
        if obj.linked_patient_id:
            try:
                return obj.linked_patient.patient_code
            except Exception:
                return None
        return None


class DeviceEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceEvent
        fields = [
            'id', 'event_uuid', 'event_type', 'compartment_num',
            'raw_payload', 'processed', 'created_at',
        ]


class DeviceHeartbeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceHeartbeat
        fields = [
            'id', 'battery_level', 'firmware_version', 'wifi_strength',
            'uptime_seconds', 'stepper_status', 'servo_status',
            'ultrasonic_status', 'created_at',
        ]


class CompartmentMappingSerializer(serializers.ModelSerializer):
    medication_name_display = serializers.SerializerMethodField()
    prescription_detail = serializers.SerializerMethodField()
    pills_days_remaining = serializers.SerializerMethodField()
    needs_refill = serializers.SerializerMethodField()

    class Meta:
        model = DeviceCompartmentMapping
        fields = [
            'id', 'compartment_number',
            'prescription', 'medication_name', 'medication_name_display',
            'prescription_detail', 'scheduled_times', 'next_scheduled_time',
            # Smart fields
            'priority', 'meal_dependency',
            # Inventory
            'total_pills', 'pills_remaining', 'pills_days_remaining', 'needs_refill',
            # Fill status
            'is_filled', 'last_filled_at',
        ]

    def get_medication_name_display(self, obj):
        if obj.medication_name:
            return obj.medication_name
        try:
            return obj.prescription.medication.name
        except Exception:
            return None

    def get_prescription_detail(self, obj):
        try:
            p = obj.prescription
            return {
                'id': str(p.id),
                'dosage_value': p.dosage_value,
                'dosage_unit': p.dosage_unit,
            }
        except Exception:
            return None

    def get_pills_days_remaining(self, obj):
        return obj.pills_days_remaining()

    def get_needs_refill(self, obj):
        return obj.needs_refill_alert()


class DeviceCommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceCommand
        fields = [
            'id', 'command_type', 'payload', 'status',
            'expires_at', 'acknowledged_at', 'executed_at', 'created_at',
        ]


class MealLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealLog
        fields = [
            'id', 'date',
            'breakfast_done', 'breakfast_time',
            'lunch_done', 'lunch_time',
            'dinner_done', 'dinner_time',
        ]
        read_only_fields = ['id']


class EventIngestSerializer(serializers.Serializer):
    """Used for optional pre-validation — views also accept raw payload."""
    event_uuid = serializers.CharField(max_length=64)
    event_type = serializers.CharField(max_length=40)
    compartment_num = serializers.IntegerField(required=False, allow_null=True)

    def to_internal_value(self, data):
        val = super().to_internal_value(data)
        val['raw_payload'] = data
        return val


# ─── New: Dispenser Architecture Serializers ────────────────────────────────

class SubCompartmentSerializer(serializers.ModelSerializer):
    dose_weight_grams = serializers.SerializerMethodField()

    class Meta:
        model = SubCompartment
        fields = [
            'id', 'medicine_name',
            'pill_weight_grams', 'quantity_per_dose', 'duration_days',
            'total_pills', 'total_weight_grams', 'dose_weight_grams',
            'instructions', 'ai_analysis_data', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'total_pills', 'total_weight_grams', 'ai_analysis_data', 'created_at']

    def get_dose_weight_grams(self, obj):
        return round(obj.dose_weight(), 3)


class PhysicalCompartmentSerializer(serializers.ModelSerializer):
    sub_compartments = serializers.SerializerMethodField()
    time_slot_display = serializers.SerializerMethodField()
    total_medicines = serializers.SerializerMethodField()
    dose_expected_reduction_grams = serializers.SerializerMethodField()

    class Meta:
        model = PhysicalCompartment
        fields = [
            'id', 'compartment_number', 'time_slot', 'time_slot_display',
            'scheduled_time',
            'expected_weight_grams', 'current_balance_weight_grams',
            'is_active', 'last_filled_at',
            'total_medicines', 'dose_expected_reduction_grams',
            'sub_compartments',
        ]
        read_only_fields = ['id', 'last_filled_at']

    def get_sub_compartments(self, obj):
        active_subs = obj.sub_compartments.filter(is_active=True)
        return SubCompartmentSerializer(active_subs, many=True).data

    def get_time_slot_display(self, obj):
        return obj.get_time_slot_display_name()

    def get_total_medicines(self, obj):
        return obj.sub_compartments.filter(is_active=True).count()

    def get_dose_expected_reduction_grams(self, obj):
        active = obj.sub_compartments.filter(is_active=True)
        return round(sum(s.pill_weight_grams * s.quantity_per_dose for s in active), 3)


class PhysicalCompartmentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer — no nested sub_compartments for list views."""
    time_slot_display = serializers.SerializerMethodField()

    class Meta:
        model = PhysicalCompartment
        fields = [
            'id', 'compartment_number', 'time_slot', 'time_slot_display',
            'scheduled_time',
            'expected_weight_grams', 'current_balance_weight_grams',
            'is_active', 'last_filled_at',
        ]

    def get_time_slot_display(self, obj):
        return obj.get_time_slot_display_name()


class DoseSessionSerializer(serializers.ModelSerializer):
    compartment_number = serializers.SerializerMethodField()
    time_slot = serializers.SerializerMethodField()

    class Meta:
        model = DoseSession
        fields = [
            'id', 'compartment_number', 'time_slot',
            'scheduled_time',
            'expected_weight_before', 'actual_weight_after',
            'weight_reduction_actual', 'weight_reduction_expected',
            'dose_status', 'gate_open_count', 'is_gate_locked',
            'completed_at', 'created_at',
        ]

    def get_compartment_number(self, obj):
        return obj.compartment.compartment_number

    def get_time_slot(self, obj):
        return obj.compartment.time_slot


class WeightHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightHistory
        fields = ['id', 'compartment_number', 'weight_grams', 'recorded_at']


class GateEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = GateEvent
        fields = ['id', 'compartment_number', 'event_type', 'recorded_at']
