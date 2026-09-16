from rest_framework import serializers
from .models import DoctorProfile, DoctorPatientLink, DigitalPrescription, ConsultationSession, ConsultationMessage


class DoctorProfileSerializer(serializers.ModelSerializer):
    full_name  = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()

    class Meta:
        model  = DoctorProfile
        fields = [
            'id', 'user', 'full_name', 'user_email',
            'registration_number', 'specialization', 'hospital_name',
            'is_verified', 'verified_at',
            'experience_years', 'rating', 'review_count',
            'consultation_fee', 'is_available', 'is_online', 'next_slot', 'languages',
        ]
        read_only_fields = ['id', 'user', 'is_verified', 'verified_at', 'is_online']

    def get_full_name(self, obj):
        try:
            return obj.user.full_name
        except Exception:
            return None

    def get_user_email(self, obj):
        try:
            return obj.user.email
        except Exception:
            return None


class DoctorPatientLinkSerializer(serializers.ModelSerializer):
    doctor_name  = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    patient_code = serializers.SerializerMethodField()

    class Meta:
        model  = DoctorPatientLink
        fields = [
            'id', 'doctor', 'doctor_name',
            'patient', 'patient_name', 'patient_code',
            'linked_at',
            'can_view_adherence', 'can_send_prescriptions',
            'can_receive_alerts', 'alert_threshold',
        ]
        read_only_fields = ['id', 'linked_at', 'doctor']

    def get_doctor_name(self, obj):
        try:
            return obj.doctor.user.full_name
        except Exception:
            return None

    def get_patient_name(self, obj):
        try:
            return obj.patient.user.full_name
        except Exception:
            return None

    def get_patient_code(self, obj):
        try:
            return obj.patient.patient_code
        except Exception:
            return None


class DigitalPrescriptionSerializer(serializers.ModelSerializer):
    doctor_name  = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    # Optional: server fills this in from instruction_points when omitted (see views.perform_create)
    instructions = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model  = DigitalPrescription
        fields = [
            'id', 'doctor', 'doctor_name',
            'patient', 'patient_name',
            'medication_name', 'dosage', 'instructions', 'instruction_points',
            'start_date', 'end_date', 'notes',
            'compartment_number', 'current_pill_count',
            'is_accepted', 'accepted_at', 'session',
            'converted_prescription',
            'created_at',
        ]
        read_only_fields = [
            'id', 'doctor', 'is_accepted', 'accepted_at',
            'converted_prescription', 'created_at',
        ]


class ConsultationMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    is_own      = serializers.SerializerMethodField()
    type        = serializers.SerializerMethodField()

    class Meta:
        model  = ConsultationMessage
        fields = [
            'id', 'session', 'sender', 'sender_name',
            'content', 'type', 'metadata',
            'file_url', 'file_name', 'file_size', 'mime_type',
            'created_at', 'is_own',
        ]
        read_only_fields = ['id', 'sender', 'created_at']

    def get_sender_name(self, obj):
        try:
            return obj.sender.full_name
        except Exception:
            return None

    def get_is_own(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.sender_id == request.user.id
        return False

    def get_type(self, obj):
        return obj.message_type or 'text'


class ConsultationSessionSerializer(serializers.ModelSerializer):
    doctor_name       = serializers.SerializerMethodField()
    doctor_spec       = serializers.SerializerMethodField()
    patient_name      = serializers.SerializerMethodField()
    patient_code      = serializers.SerializerMethodField()
    last_message      = serializers.SerializerMethodField()
    unread_count      = serializers.SerializerMethodField()

    class Meta:
        model  = ConsultationSession
        fields = [
            'id', 'doctor', 'doctor_name', 'doctor_spec',
            'patient', 'patient_name', 'patient_code',
            'status', 'requested_at', 'accepted_at', 'ended_at',
            'doctor_notes', 'last_message', 'unread_count',
        ]
        read_only_fields = ['id', 'requested_at', 'accepted_at', 'ended_at', 'doctor', 'patient']

    def get_doctor_name(self, obj):
        try:
            return obj.doctor.user.full_name
        except Exception:
            return None

    def get_doctor_spec(self, obj):
        try:
            return obj.doctor.specialization
        except Exception:
            return None

    def get_patient_name(self, obj):
        try:
            return obj.patient.user.full_name
        except Exception:
            return None

    def get_patient_code(self, obj):
        try:
            return obj.patient.patient_code
        except Exception:
            return None

    def get_last_message(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        if msg:
            return {'content': msg.content[:80], 'created_at': msg.created_at.isoformat()}
        return None

    def get_unread_count(self, obj):
        return 0  # placeholder — mark-read handled by WebSocket consumer

    def get_doctor_name(self, obj):
        try:
            return obj.doctor.user.full_name
        except Exception:
            return None

    def get_patient_name(self, obj):
        try:
            return obj.patient.user.full_name
        except Exception:
            return None
