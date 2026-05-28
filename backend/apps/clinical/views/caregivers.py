"""
apps/clinical/views/caregivers.py — Caregiver linking, invites, patient-facing caregiver views.
"""
import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger('medadhere')
from django.shortcuts import get_object_or_404
from django.utils import timezone

from shared.response import APIResponse
from shared.permissions import IsPatient, IsCaregiver
from ..models import Patient, Caregiver, PatientCaregiverLink, PermissionLevel
from ..serializers import (
    CaregiverLinkSerializer, CaregiverInviteSerializer,
    CaregiverPermissionUpdateSerializer, PatientSummarySerializer,
    PatientSerializer, PrescriptionSerializer,
)
from ..services import CaregiverInviteService


def get_patient_or_404(user):
    try:
        return user.patient_profile
    except Exception:
        from django.http import Http404
        raise Http404


# ─── Patient → Caregiver Management ──────────────────────────────────────────

class PatientCaregiverListView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        """GET /api/v1/patients/me/caregivers/"""
        patient = get_patient_or_404(request.user)
        links   = PatientCaregiverLink.objects.filter(
            patient=patient, deleted_at__isnull=True
        ).select_related('caregiver__user').order_by('-created_at')
        return APIResponse.success(CaregiverLinkSerializer(links, many=True).data)


class PatientCaregiverInviteView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def post(self, request):
        """POST /api/v1/patients/me/caregivers/invite/"""
        patient = get_patient_or_404(request.user)
        s = CaregiverInviteSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)

        try:
            link = CaregiverInviteService.send_invite(
                patient=patient,
                caregiver_email=s.validated_data['caregiver_email'],
                permission_level=s.validated_data['permission_level'],
                can_receive_alerts=s.validated_data.get('can_receive_alerts', True),
            )
            return APIResponse.created({
                'invite_token': link.invite_token,
                'expires_at':   link.invite_expires_at.isoformat(),
                'caregiver_email': s.validated_data['caregiver_email'],
            }, message='Invite sent. Caregiver must accept within 7 days.')
        except Exception as e:
            return APIResponse.error(str(e), code='INVITE_FAILED')


class PatientCaregiverUnlinkView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def delete(self, request, link_id):
        """DELETE /api/v1/patients/me/caregivers/{id}/"""
        patient = get_patient_or_404(request.user)
        link = get_object_or_404(PatientCaregiverLink, id=link_id, patient=patient)
        link.is_active = False
        link.save(update_fields=['is_active', 'updated_at'])
        return APIResponse.no_content('Caregiver unlinked.')


class PatientCaregiverPermissionsView(APIView):
    permission_classes = [IsAuthenticated, IsPatient]

    def patch(self, request, link_id):
        """PATCH /api/v1/patients/me/caregivers/{id}/permissions/"""
        patient = get_patient_or_404(request.user)
        link = get_object_or_404(PatientCaregiverLink, id=link_id, patient=patient, is_active=True)
        s = CaregiverPermissionUpdateSerializer(data=request.data)
        if not s.is_valid():
            return APIResponse.error('Validation failed.', errors=s.errors)

        link.permission_level = s.validated_data['permission_level']
        if 'can_receive_alerts' in s.validated_data:
            link.can_receive_alerts = s.validated_data['can_receive_alerts']
        link.save(update_fields=['permission_level', 'can_receive_alerts', 'updated_at'])
        return APIResponse.success(CaregiverLinkSerializer(link).data, message='Permissions updated.')


# ─── Invite Accept (public token endpoint) ────────────────────────────────────

class CaregiverInviteAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        """POST /api/v1/caregiver-links/{token}/accept/"""
        try:
            link = CaregiverInviteService.accept_invite(token, request.user)
            return APIResponse.success(
                CaregiverLinkSerializer(link).data,
                message='Invite accepted. You are now linked as a caregiver.'
            )
        except Exception as e:
            return APIResponse.error(str(e), code='INVITE_ACCEPT_FAILED')


# ─── Caregiver → Patient Views ────────────────────────────────────────────────

def get_caregiver_or_404(user):
    try:
        return user.caregiver_profile
    except Exception:
        from django.http import Http404
        raise Http404


class CaregiverPatientListView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request):
        """GET /api/v1/caregivers/patients/ — list all linked patients."""
        caregiver = get_caregiver_or_404(request.user)
        links = PatientCaregiverLink.objects.filter(
            caregiver=caregiver, is_active=True
        ).select_related('patient__user')
        patients = [link.patient for link in links]
        return APIResponse.success(
            PatientSummarySerializer(patients, many=True, context={'request': request}).data
        )


class CaregiverPatientAddView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def post(self, request):
        """POST /api/v1/caregivers/patients/add/"""
        caregiver = get_caregiver_or_404(request.user)
        email = request.data.get('email')
        patient_code = request.data.get('patient_code')
        phone_number = request.data.get('phone_number')
        is_create = request.data.get('create_new', False)

        if not email and not patient_code and not phone_number:
            return APIResponse.error("Please provide email, patient code, or phone number to link.", status=400)

        from apps.clinical.models import Patient
        from apps.identity.models import User
        
        patient = None
        
        if is_create:
            password = request.data.get('password')
            full_name = request.data.get('full_name')

            if not password or not full_name:
                return APIResponse.error("Password and full name are required to create a new patient.", status=400)
            if not email and not phone_number:
                return APIResponse.error("Either email or phone number is required to create a new patient.", status=400)

            from django.db import transaction
            try:
                with transaction.atomic():
                    if email and User.objects.filter(email__iexact=email.strip()).exists():
                        return APIResponse.error("A user with this email already exists.", status=400)
                    if phone_number and User.objects.filter(phone_number=phone_number.strip()).exists():
                        return APIResponse.error("A user with this phone number already exists.", status=400)

                    import uuid
                    # User model requires an email, so we generate a placeholder if only phone is provided
                    final_email = email.strip() if email else f"{uuid.uuid4().hex[:8]}@temp.com"
                    
                    user = User.objects.create_user(
                        email=final_email,
                        password=password,
                        full_name=full_name.strip(),
                        phone_number=phone_number.strip() if phone_number else None,
                        role='PATIENT'
                    )
                    patient, _ = Patient.objects.get_or_create(user=user)
                    
                    # Optionally, you could trigger an email or SMS here with the credentials
                    # NotificationService.send_credentials(user, password)
            except Exception as e:
                return APIResponse.error(f"Failed to create patient: {str(e)}", status=400)
        else:
            if patient_code:
                patient = Patient.objects.filter(patient_code=patient_code.strip().upper(), deleted_at__isnull=True).first()
            
            if not patient and email:
                user = User.objects.filter(email__iexact=email.strip(), deleted_at__isnull=True).first()
                if user:
                    patient = Patient.objects.filter(user=user, deleted_at__isnull=True).first()
                    
            if not patient and phone_number:
                user = User.objects.filter(phone_number=phone_number.strip(), deleted_at__isnull=True).first()
                if user:
                    patient = Patient.objects.filter(user=user, deleted_at__isnull=True).first()

        if not patient:
            return APIResponse.error("Patient not found. Please verify the details provided.", status=404)

        # Check if already linked
        link, created = PatientCaregiverLink.objects.get_or_create(
            patient=patient,
            caregiver=caregiver,
            defaults={
                'permission_level': PermissionLevel.FULL_ACCESS,
                'can_receive_alerts': True,
                'is_active': True,
                'accepted_at': timezone.now()
            }
        )

        if not created:
            if link.is_active:
                return APIResponse.error("This patient is already linked to your account.", status=400)
            else:
                link.is_active = True
                link.permission_level = PermissionLevel.FULL_ACCESS
                link.accepted_at = timezone.now()
                link.save()

        from apps.clinical.serializers import PatientSerializer
        return APIResponse.success(
            {
                "message": "Patient created and linked successfully!" if is_create else "Patient linked successfully!",
                "patient": PatientSerializer(patient).data
            },
            status=201
        )


class CaregiverPatientDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request, patient_id):
        """GET /api/v1/caregivers/patients/{id}/ — patient detail (filtered by permission)."""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        s = PatientSerializer(link.patient)
        return APIResponse.success(s.data)

    def patch(self, request, patient_id):
        """PATCH /api/v1/caregivers/patients/{id}/ — update patient detail."""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        if link.permission_level != PermissionLevel.FULL_ACCESS:
            return APIResponse.error("You do not have permission to edit this patient.", status=403)
        
        from apps.clinical.serializers import PatientUpdateSerializer
        serializer = PatientUpdateSerializer(link.patient, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return APIResponse.success(PatientSerializer(link.patient).data)
        return APIResponse.error(serializer.errors, status=400)


class CaregiverPatientAdherenceSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request, patient_id):
        """GET /api/v1/caregivers/patients/{id}/adherence/summary/"""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        from apps.scheduling.services import AdherenceReportService
        days = int(request.query_params.get('days', 30))
        report = AdherenceReportService.get_summary(link.patient, days=days)
        return APIResponse.success(report)


class CaregiverPatientAdherenceTimelineView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request, patient_id):
        """GET /api/v1/caregivers/patients/{id}/adherence/timeline/"""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        from apps.scheduling.services import AdherenceReportService
        days = int(request.query_params.get('days', 30))
        timeline = AdherenceReportService.get_timeline(link.patient, days=days)
        return APIResponse.success(timeline)


class CaregiverPatientAdherenceMedicationsView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request, patient_id):
        """GET /api/v1/caregivers/patients/{id}/adherence/medications/"""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        from apps.scheduling.services import AdherenceReportService
        days = int(request.query_params.get('days', 30))
        breakdown = AdherenceReportService.get_medication_breakdown(link.patient, days=days)
        return APIResponse.success(breakdown)


class CaregiverPatientAdherenceExportView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request, patient_id):
        """GET /api/v1/caregivers/patients/{id}/adherence/export/"""
        print(f"DEBUG: Entering CaregiverPatientAdherenceExportView for patient_id: {patient_id}")
        try:
            caregiver = get_caregiver_or_404(request.user)
            print(f"DEBUG: Found caregiver: {caregiver.id}")
        except Exception as e:
            print(f"DEBUG: Failed to get caregiver: {e}")
            raise
            
        try:
            link = get_object_or_404(
                PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
            )
            print(f"DEBUG: Found link: {link.id}")
        except Exception as e:
            print(f"DEBUG: Failed to find active link for patient {patient_id} and caregiver {caregiver.id}: {e}")
            raise
        # Delegate to the patient-level view logic or duplicate it here.
        # Since AdherenceReportExportView is complex, it's better to just reuse its logic.
        from apps.scheduling.views.adherence import AdherenceReportExportView
        
        # We need to temporarily set request.user to the patient's user to pass the permission checks
        # inside AdherenceReportExportView if it uses request.user, but wait, AdherenceReportExportView 
        # fetches patient via get_patient_or_404(request.user).
        # Let's just reimplement the export logic for caregiver without checking SubscriptionGate or 
        # extracting patient from request.user, instead using `link.patient`.
        
        patient = link.patient
        days = min(int(request.query_params.get('days', 30)), 365)
        fmt = request.query_params.get('export_format', request.query_params.get('format', 'json'))

        from django.utils import timezone
        import datetime
        since = timezone.now() - datetime.timedelta(days=days)

        from apps.scheduling.models import DoseLog
        logs = DoseLog.objects.filter(
            prescription__patient=patient,
            taken_at__gte=since,
        ).select_related('prescription__medication').order_by('-taken_at')

        if fmt == 'csv':
            import csv
            from django.http import StreamingHttpResponse

            def generate():
                headers = ['date', 'medication', 'status', 'dose_value', 'dose_unit', 'with_food', 'notes']
                yield ','.join(headers) + '\n'
                for log in logs.iterator():
                    row = [
                        str(log.taken_at.date()),
                        log.prescription.medication.name,
                        log.status,
                        str(log.dose_value),
                        log.dose_unit,
                        'Yes' if log.with_food else 'No',
                        (log.notes or '').replace(',', ' '),
                    ]
                    yield ','.join(row) + '\n'

            response = StreamingHttpResponse(generate(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="adherence_report_{days}d.csv"'
            return response

        elif fmt == 'pdf':
            from io import BytesIO
            from xhtml2pdf import pisa
            from django.http import HttpResponse
            from apps.scheduling.services import AdherenceReportService
            from apps.scheduling.serializers import DoseLogSerializer
            import urllib.parse
            import json

            summary = AdherenceReportService.get_summary(patient, days=days)
            breakdown = AdherenceReportService.get_medication_breakdown(patient, days=days)
            timeline = AdherenceReportService.get_timeline(patient, days=days)

            # Generate QuickChart URL for the timeline (last 14 days for readability)
            chart_data = timeline[-14:] if len(timeline) > 14 else timeline
            labels = [d['date'][-5:] for d in chart_data] # Just MM-DD
            taken_data = [d.get('taken', 0) for d in chart_data]
            missed_data = [d.get('missed', 0) for d in chart_data]

            chart_config = {
                "type": "bar",
                "data": {
                    "labels": labels,
                    "datasets": [
                        {"label": "Taken", "data": taken_data, "backgroundColor": "#0B6E7A"},
                        {"label": "Missed", "data": missed_data, "backgroundColor": "#FF6B6B"}
                    ]
                },
                "options": {
                    "title": {"display": False},
                    "legend": {"position": "bottom"},
                    "scales": {
                        "xAxes": [{"stacked": True, "gridLines": {"display": False}}],
                        "yAxes": [{"stacked": True, "ticks": {"beginAtZero": True, "stepSize": 1}}]
                    }
                }
            }
            encoded_config = urllib.parse.quote(json.dumps(chart_config))
            chart_url = f"https://quickchart.io/chart?c={encoded_config}&w=600&h=250&bkg=white&v=2.9.4"

            log_list = []
            for log in logs[:200]:
                status_class = "status-taken"
                if log.status == 'MISSED':
                    status_class = "status-missed"
                elif log.status == 'SKIPPED':
                    status_class = "status-skipped"

                log_list.append({
                    'date': log.taken_at.strftime('%Y-%m-%d %I:%M %p') if log.taken_at else 'N/A',
                    'medication': log.prescription.medication.name,
                    'status': log.status,
                    'status_class': status_class,
                    'dose': f"{log.dose_value} {log.dose_unit or ''}",
                    'with_food': 'Yes' if log.with_food else 'No',
                    'notes': log.notes or '-',
                })

            breakdown_list = []
            for item in breakdown:
                breakdown_list.append({
                    'medication': item['medication'],
                    'total': item['total'],
                    'taken': item['taken'],
                    'missed': item['missed'],
                    'adherence_pct': f"{item['adherence_pct']}%",
                })

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    @page {{
                        size: letter;
                        margin: 0.5in;
                    }}
                    body {{
                        font-family: Arial, sans-serif;
                        color: #1e293b;
                        font-size: 10pt;
                        line-height: 1.5;
                    }}
                    .header-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 20px;
                        border-bottom: 3px solid #0B6E7A;
                        padding-bottom: 10px;
                    }}
                    .header-logo {{
                        font-size: 24pt;
                        font-weight: bold;
                        color: #0B6E7A;
                    }}
                    .header-title {{
                        text-align: right;
                        font-size: 14pt;
                        font-weight: bold;
                        color: #0f172a;
                    }}
                    .header-sub {{
                        text-align: right;
                        font-size: 9pt;
                        color: #64748b;
                    }}
                    .info-table {{
                        width: 100%;
                        border-collapse: collapse;
                        background-color: #F8FAFC;
                        border: 1px solid #E2E8F0;
                        border-radius: 8px;
                        margin-bottom: 20px;
                    }}
                    .info-td {{
                        padding: 12px;
                        font-size: 10pt;
                        color: #334155;
                        width: 50%;
                    }}
                    .section-title {{
                        font-size: 13pt;
                        font-weight: bold;
                        color: #0f172a;
                        border-bottom: 2px solid #E2E8F0;
                        padding-bottom: 6px;
                        margin-bottom: 15px;
                        margin-top: 25px;
                    }}
                    .kpi-table {{
                        width: 100%;
                        border-collapse: separate;
                        border-spacing: 10px 0;
                        margin-bottom: 25px;
                    }}
                    .kpi-card {{
                        background-color: #F1F5F9;
                        border: 1px solid #CBD5E1;
                        border-radius: 8px;
                        padding: 15px;
                        text-align: center;
                        width: 25%;
                    }}
                    .kpi-value {{
                        font-size: 18pt;
                        font-weight: bold;
                        color: #0B6E7A;
                        margin-bottom: 5px;
                    }}
                    .kpi-label {{
                        font-size: 8pt;
                        font-weight: bold;
                        color: #475569;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                    }}
                    .chart-container {{
                        text-align: center;
                        margin-bottom: 30px;
                        padding: 15px;
                        background-color: white;
                        border: 1px solid #E2E8F0;
                        border-radius: 8px;
                    }}
                    .data-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 20px;
                    }}
                    .data-table th {{
                        background-color: #0B6E7A;
                        color: #ffffff;
                        font-size: 9pt;
                        font-weight: bold;
                        text-align: left;
                        padding: 8px 10px;
                    }}
                    .data-table td {{
                        font-size: 8.5pt;
                        border-bottom: 1px solid #E2E8F0;
                        padding: 8px 10px;
                    }}
                    .data-table tr:nth-child(even) {{
                        background-color: #F8FAFC;
                    }}
                    .status-badge {{
                        font-weight: bold;
                        font-size: 7.5pt;
                        padding: 3px 8px;
                        border-radius: 4px;
                    }}
                    .status-taken {{
                        color: #15803d;
                        background-color: #dcfce7;
                    }}
                    .status-missed {{
                        color: #b91c1c;
                        background-color: #fee2e2;
                    }}
                    .status-skipped {{
                        color: #b45309;
                        background-color: #fef3c7;
                    }}
                </style>
            </head>
            <body>
                <table class="header-table">
                    <tr>
                        <td class="header-logo">Aarogyam</td>
                        <td class="header-title">MEDICATION ADHERENCE REPORT<br/><span class="header-sub">Generated on {timezone.now().strftime('%Y-%m-%d')}</span></td>
                    </tr>
                </table>

                <table class="info-table">
                    <tr>
                        <td class="info-td"><strong>Patient:</strong> {patient.user.full_name or patient.user.username}</td>
                        <td class="info-td" style="text-align: right;"><strong>Reporting Period:</strong> {days} Days ({since.strftime('%Y-%m-%d')} to {timezone.now().strftime('%Y-%m-%d')})</td>
                    </tr>
                </table>

                <div class="section-title">Metrics Dashboard</div>
                <table class="kpi-table">
                    <tr>
                        <td class="kpi-card">
                            <div class="kpi-value">{summary.get('adherence_pct', 0)}%</div>
                            <div class="kpi-label">Adherence Score</div>
                        </td>
                        <td class="kpi-card">
                            <div class="kpi-value">{summary.get('total_scheduled', 0)}</div>
                            <div class="kpi-label">Total Doses</div>
                        </td>
                        <td class="kpi-card">
                            <div class="kpi-value">{summary.get('taken', 0)}</div>
                            <div class="kpi-label">Taken Doses</div>
                        </td>
                        <td class="kpi-card">
                            <div class="kpi-value">{summary.get('missed', 0)}</div>
                            <div class="kpi-label">Missed Doses</div>
                        </td>
                    </tr>
                </table>

                <div class="section-title">Adherence Timeline (Last {len(chart_data)} Days)</div>
                <div class="chart-container">
                    <img src="{chart_url}" width="600" height="250" />
                </div>

                <div class="section-title">Medication Breakdown</div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="width: 35%;">Medication</th>
                            <th style="width: 15%;">Total Scheduled</th>
                            <th style="width: 15%;">Taken</th>
                            <th style="width: 15%;">Missed</th>
                            <th style="width: 20%;">Adherence Rate</th>
                        </tr>
                    </thead>
                    <tbody>
            """

            for item in breakdown_list:
                html_content += f"""
                        <tr>
                            <td><strong>{item['medication']}</strong></td>
                            <td>{item['total']}</td>
                            <td>{item['taken']}</td>
                            <td>{item['missed']}</td>
                            <td>{item['adherence_pct']}</td>
                        </tr>
                """

            if not breakdown_list:
                html_content += """
                        <tr>
                            <td colspan="5" style="text-align: center; color: #64748b; padding: 15px;">No active clinical schedules for this period.</td>
                        </tr>
                """

            html_content += """
                    </tbody>
                </table>

                <div class="section-title">Detailed Logs (Top 200)</div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="width: 25%;">Date / Time</th>
                            <th style="width: 25%;">Medication</th>
                            <th style="width: 12%;">Dose</th>
                            <th style="width: 10%;">Food Req.</th>
                            <th style="width: 13%;">Status</th>
                            <th style="width: 15%;">Notes</th>
                        </tr>
                    </thead>
                    <tbody>
            """

            for log in log_list:
                html_content += f"""
                        <tr>
                            <td>{log['date']}</td>
                            <td><strong>{log['medication']}</strong></td>
                            <td>{log['dose']}</td>
                            <td>{log['with_food']}</td>
                            <td><span class="status-badge {log['status_class']}">{log['status']}</span></td>
                            <td>{log['notes']}</td>
                        </tr>
                """

            if not log_list:
                html_content += """
                        <tr>
                            <td colspan="6" style="text-align: center; color: #64748b; padding: 15px;">No history logs found for this period.</td>
                        </tr>
                """

            html_content += """
                    </tbody>
                </table>
            </body>
            </html>
            """

            result = BytesIO()
            pisa_status = pisa.pisaDocument(BytesIO(html_content.encode("UTF-8")), result)
            if not pisa_status.err:
                pdf_bytes = result.getvalue()

                # Send email with PDF attachment
                from django.core.mail import EmailMultiAlternatives
                from django.template.loader import render_to_string
                from django.conf import settings
                import logging
                logger = logging.getLogger('medadhere')

                try:
                    # Collect emails: Patient + Caregivers
                    recipient_emails = [patient.user.email] if patient.user.email else []
                    caregivers = patient.caregiver_links.select_related('caregiver__user').all()
                    for c_link in caregivers:
                        if c_link.caregiver.user.email:
                            recipient_emails.append(c_link.caregiver.user.email)
                    
                    recipient_emails = list(set(recipient_emails))
                    
                    if recipient_emails:
                        date_range = f"{since.strftime('%B %d, %Y')} to {timezone.now().strftime('%B %d, %Y')}"
                        email_html = render_to_string('emails/adherence_report_email.html', {
                            'patient_name': patient.user.full_name or patient.user.username,
                            'days': days,
                            'date_range': date_range
                        })
                        
                        msg = EmailMultiAlternatives(
                            subject=f"Medication Adherence Report - {patient.user.full_name or patient.user.username}",
                            body=f"Please find attached the adherence report for the last {days} days.",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            to=recipient_emails,
                        )
                        msg.attach_alternative(email_html, 'text/html')
                        msg.attach(f'adherence_report_{days}d.pdf', pdf_bytes, 'application/pdf')
                        msg.send(fail_silently=False)
                except Exception as e:
                    logger.error(f"Failed to send adherence report email for patient {patient.id}: {e}")

                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="adherence_report_{days}d.pdf"'
                return response

            logger.error(f"PDF generation failed: {pisa_status.err}")
            return APIResponse.error('Failed to generate PDF document.')

        from apps.scheduling.serializers import DoseLogSerializer
        return APIResponse.success(DoseLogSerializer(logs[:500], many=True).data)


class CaregiverPatientAlertsView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request, patient_id):
        """GET /api/v1/caregivers/patients/{id}/alerts/"""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        from apps.scheduling.models import ReminderJob
        missed = ReminderJob.objects.filter(
            schedule__prescription__patient=link.patient,
            status='MISSED',
        ).order_by('-scheduled_at')[:20]

        from apps.scheduling.serializers import ReminderJobSerializer
        return APIResponse.success(ReminderJobSerializer(missed, many=True).data)

class CaregiverPatientPrescriptionsView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request, patient_id):
        """GET /api/v1/caregivers/patients/{id}/prescriptions/"""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        from apps.clinical.models import Prescription
        from apps.clinical.serializers import PrescriptionSerializer
        qs = Prescription.objects.filter(
            patient=link.patient, deleted_at__isnull=True
        ).select_related('medication').prefetch_related('schedules')
        return APIResponse.success(PrescriptionSerializer(qs, many=True).data)

    def post(self, request, patient_id):
        """POST /api/v1/caregivers/patients/{id}/prescriptions/"""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        if link.permission_level != PermissionLevel.FULL_ACCESS:
            return APIResponse.error("You do not have permission to add prescriptions for this patient.", status=403)

        data = request.data

        # ── Resolve medicine name → Medication row (get or create) ──
        medicine_name = (data.get('medicine_name') or '').strip()
        if not medicine_name:
            return APIResponse.error('medicine_name is required.', code='VALIDATION_ERROR')

        from apps.clinical.models import Medication, MedicationForm, Prescription, MedicationSchedule
        from apps.clinical.services import PrescriptionService, DrugInteractionChecker
        import datetime

        medicine_form = data.get('medicine_form', 'TABLET').upper()
        if medicine_form not in [c[0] for c in MedicationForm.choices]:
            medicine_form = 'TABLET'

        existing = Medication.objects.filter(name__iexact=medicine_name).first()
        if existing:
            medication = existing
        else:
            medication = Medication.objects.create(name=medicine_name, form=medicine_form)

        # ── Dates ──
        start_date   = timezone.now().date()
        duration_days = data.get('duration_days')
        is_indefinite = duration_days is None or duration_days == 0
        end_date = (
            start_date + datetime.timedelta(days=int(duration_days))
            if not is_indefinite else None
        )

        # ── Quantities ──
        total_pills = data.get('total_pills') or data.get('total_quantity')
        try:
            total_qty = float(total_pills) if total_pills is not None else None
        except (ValueError, TypeError):
            total_qty = None

        dosage_value = data.get('dosage_value', 1)
        try:
            dosage_value = float(dosage_value)
        except (ValueError, TypeError):
            dosage_value = 1.0

        # ── Drug interaction check ──
        interactions = DrugInteractionChecker.check(link.patient, medication.id)
        severe = [i for i in interactions if i['severity'] in ('SEVERE', 'CONTRAINDICATED')]

        # ── Create Prescription ──
        try:
            prescription_data = {
                'medication':          medication,
                'prescribed_by':       (data.get('prescribed_by') or '').strip() or caregiver.user.full_name,
                'dosage_value':        dosage_value,
                'dosage_unit':         data.get('dosage_unit', 'tablet(s)'),
                'instructions':        data.get('instructions') or '',
                'start_date':          start_date,
                'end_date':            end_date,
                'is_indefinite':       is_indefinite,
                'total_quantity':      total_qty,
                'remaining_quantity':  total_qty,
                'compartment_number':  data.get('compartment_number'),
                'current_pill_count':  total_qty,
            }
            prescription = PrescriptionService.create(link.patient, prescription_data)
        except Exception as e:
            return APIResponse.error(str(e), code='PRESCRIPTION_FAILED')

        # ── Create schedule from schedule_times ──
        schedule_times = data.get('schedule_times', [])
        if schedule_times:
            times_of_day = [
                {
                    'time':      t.get('time', '08:00'),
                    'dose':      dosage_value,
                    'with_food': t.get('with_food', False),
                    'label':     t.get('label', ''),
                }
                for t in schedule_times
            ]
            schedule = MedicationSchedule.objects.create(
                prescription=prescription,
                frequency_type='DAILY',
                times_of_day=times_of_day,
                days_of_week=list(range(7)),
                timezone=link.patient.timezone or 'Asia/Kolkata',
            )
            # Generate only today + tomorrow immediately so patient sees schedule right away.
            # The midnight Celery task (generate_next_day_reminders) handles all subsequent days.
            try:
                from apps.scheduling.services import ScheduleGenerationService
                ScheduleGenerationService.generate_upcoming_reminders(schedule, days=2)
            except Exception:
                pass

        # ── Sync to IoT device if patient has a linked device ──
        compartment_number = data.get('compartment_number')
        if compartment_number and schedule_times:
            try:
                from apps.iot.models import Device, DeviceCompartmentMapping, PhysicalCompartment, SubCompartment, DeviceCommand
                device = Device.objects.filter(
                    linked_patient=link.patient, is_active=True
                ).first()
                if device:
                    time_strings = [t.get('time', '08:00') for t in schedule_times]
                    # Update the old-architecture mapping (used by get_device_schedule)
                    DeviceCompartmentMapping.objects.update_or_create(
                        device=device,
                        compartment_number=int(compartment_number),
                        defaults={
                            'prescription':    prescription,
                            'scheduled_times': time_strings,
                            'medication_name': medication.name,
                            'total_pills':     int(total_qty) if total_qty else 0,
                            'pills_remaining': int(total_qty) if total_qty else 0,
                        }
                    )
                    # Update the new-architecture mapping (PhysicalCompartment + SubCompartment)
                    slot_map = {1: 'morning_before', 2: 'morning_after', 3: 'night_before', 4: 'night_after'}
                    time_slot = slot_map.get(int(compartment_number), 'morning_before')
                    phys, _ = PhysicalCompartment.objects.get_or_create(
                        device=device,
                        compartment_number=int(compartment_number),
                        defaults={'time_slot': time_slot}
                    )
                    # Deactivate existing sub-compartment for same medicine, then create fresh
                    SubCompartment.objects.filter(
                        compartment=phys, medicine_name__iexact=medication.name
                    ).update(is_active=False)
                    SubCompartment.objects.create(
                        compartment=phys,
                        medicine_name=medication.name,
                        quantity_per_dose=int(dosage_value),
                        duration_days=int(duration_days) if not is_indefinite and duration_days else 30,
                        total_pills=int(total_qty) if total_qty else 0,
                        instructions=data.get('instructions', ''),
                        is_active=True,
                    )
                    # Queue SYNC_SCHEDULE so device picks up the change on next poll
                    DeviceCommand.objects.create(
                        device=device,
                        command_type='SYNC_SCHEDULE',
                        payload={
                            'reason':       'prescription_added',
                            'compartment':  int(compartment_number),
                            'medicine':     medication.name,
                        },
                        expires_at=timezone.now() + datetime.timedelta(hours=24),
                    )
                    logger.info(
                        f'IoT sync: device={device.id} compartment={compartment_number} '
                        f'medicine={medication.name}'
                    )
            except Exception as e:
                logger.warning(f'IoT sync failed for new prescription: {e}')

        from apps.clinical.serializers import PrescriptionSerializer
        response_data = PrescriptionSerializer(prescription).data
        if interactions:
            response_data['drug_interaction_warnings'] = interactions
        if severe:
            response_data['severe_interaction_alert'] = True

        return APIResponse.created(response_data)

    def delete(self, request, patient_id, prescription_id):
        """DELETE /api/v1/caregivers/patients/{id}/prescriptions/{prescription_id}/"""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        if link.permission_level != PermissionLevel.FULL_ACCESS:
            return APIResponse.error("You do not have permission to delete prescriptions for this patient.", status=403)

        from apps.clinical.models import Prescription
        # Try to find the prescription (including already soft-deleted ones)
        # to ensure idempotency and clean up any orphaned IoT mappings.
        rx = Prescription.all_objects.filter(id=prescription_id, patient=link.patient).first()
        if not rx:
            return APIResponse.error("Prescription not found.", status=404)
        
        # Soft delete the prescription (also cancels pending reminders and triggers IoT cleanup)
        rx.soft_delete(user=request.user)
        
        return APIResponse.no_content('Medicine removed from patient schedule.')


class CaregiverPatientDevicesView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request, patient_id):
        """GET /api/v1/caregivers/patients/{id}/devices/"""
        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        from apps.iot.models import Device, DeviceCompartmentMapping
        from apps.iot.serializers import DeviceSerializer, CompartmentMappingSerializer

        devices_qs = Device.objects.filter(linked_patient=link.patient, deleted_at__isnull=True)
        devices_data = DeviceSerializer(devices_qs, many=True).data

        # Attach compartment mappings (serialized) for each device so caregiver view reflects IoT state
        # Map by device id (string) to index in devices_data for quick merge
        device_index = {d['id']: i for i, d in enumerate(devices_data)}

        mappings = DeviceCompartmentMapping.objects.filter(device__in=devices_qs).select_related('prescription__medication')
        # Group mappings by device id
        grouped = {}
        for m in mappings:
            key = str(m.device_id)
            grouped.setdefault(key, []).append(m)

        for dev_id, maps in grouped.items():
            ser = CompartmentMappingSerializer(maps, many=True).data
            idx = device_index.get(dev_id)
            if idx is not None:
                devices_data[idx]['compartments'] = ser

        return APIResponse.success(devices_data)


class CaregiverCompartmentRescheduleView(APIView):
    """
    PATCH /api/v1/caregivers/patients/<patient_id>/devices/<device_id>/compartments/<compartment_number>/reschedule/

    Body: { "times": ["08:00", "14:00", "20:00"] }

    Updates the compartment's scheduled times, syncs the MedicationSchedule,
    regenerates today+tomorrow ReminderJobs, and queues a SYNC_SCHEDULE device command.
    """
    permission_classes = [IsAuthenticated, IsCaregiver]

    def patch(self, request, patient_id, device_id, compartment_number):
        import datetime
        from django.db import transaction
        from apps.iot.models import Device, DeviceCompartmentMapping, DeviceCommand
        from apps.scheduling.models import ReminderJob
        from apps.scheduling.services import ScheduleGenerationService

        caregiver = get_caregiver_or_404(request.user)
        link = get_object_or_404(
            PatientCaregiverLink, patient__id=patient_id, caregiver=caregiver, is_active=True
        )
        patient = link.patient

        # Validate input
        new_times = request.data.get('times', [])
        if not new_times or not isinstance(new_times, list):
            return APIResponse.error('times field is required and must be a non-empty list.', status=400)

        # Validate each time is HH:MM format
        import re
        for t in new_times:
            if not re.match(r'^\d{2}:\d{2}$', str(t)):
                return APIResponse.error(f'Invalid time format: {t}. Use HH:MM (e.g. "08:00").', status=400)

        new_times = sorted(set(new_times))  # deduplicate + sort

        # Fetch device (must belong to this patient)
        device = get_object_or_404(Device, id=device_id, linked_patient=patient, deleted_at__isnull=True)

        # Fetch compartment mapping — if missing, try to create from an existing prescription
        from apps.clinical.models import Prescription

        mapping = DeviceCompartmentMapping.objects.filter(device=device, compartment_number=compartment_number).first()
        if not mapping:
            # Try to find an active prescription already assigned to this compartment for the patient
            prescription = Prescription.objects.filter(
                patient=patient,
                compartment_number=compartment_number,
                is_active=True,
            ).order_by('-created_at').first()
            if prescription:
                # Derive scheduled_times from the first active schedule if present
                times = []
                sched = prescription.schedules.filter(is_active=True).first()
                if sched and (sched.times_of_day or []) :
                    try:
                        times = [entry.get('time') for entry in (sched.times_of_day or []) if entry.get('time')]
                    except Exception:
                        times = []

                mapping = DeviceCompartmentMapping.objects.create(
                    device=device,
                    compartment_number=compartment_number,
                    prescription=prescription,
                    scheduled_times=times,
                    medication_name=(getattr(prescription, 'medication_name', '') or getattr(getattr(prescription, 'medication', None), 'name', '')),
                )
            else:
                return APIResponse.error('No DeviceCompartmentMapping found for this slot. Add a medicine to the slot before editing.', status=404)
        else:
            prescription = mapping.prescription

        with transaction.atomic():
            # 1. Update DeviceCompartmentMapping.scheduled_times
            mapping.scheduled_times = new_times
            mapping.save(update_fields=['scheduled_times'])

            # 2. Update all active MedicationSchedules for this prescription
            #    Preserve existing per-slot metadata (dose, with_food, label) where possible
            schedules = prescription.schedules.filter(is_active=True, deleted_at__isnull=True)
            for schedule in schedules:
                old_entries = {e['time']: e for e in (schedule.times_of_day or [])}
                new_times_of_day = []
                for t in new_times:
                    if t in old_entries:
                        entry = dict(old_entries[t])
                        entry['time'] = t
                    else:
                        # New time slot — use defaults
                        entry = {'time': t, 'dose': 1.0, 'with_food': False, 'label': ''}
                    new_times_of_day.append(entry)
                schedule.times_of_day = new_times_of_day
                schedule.save(update_fields=['times_of_day', 'updated_at'])

                # 3. Cancel all future PENDING jobs for this schedule — they'll be regenerated
                ReminderJob.objects.filter(
                    schedule=schedule,
                    status='PENDING',
                    scheduled_at__gte=timezone.now(),
                ).update(status='CANCELLED')

                # 4. Regenerate today + tomorrow with the new times (idempotent)
                try:
                    ScheduleGenerationService.generate_upcoming_reminders(schedule, days=2)
                except Exception as e:
                    logger.error(f'Reminder regeneration failed for schedule={schedule.id}: {e}')

            # 5. Queue SYNC_SCHEDULE command so the physical device picks up new times
            DeviceCommand.objects.create(
                device=device,
                command_type='SYNC_SCHEDULE',
                payload={
                    'reason': 'caregiver_reschedule',
                    'compartment': compartment_number,
                    'new_times': new_times,
                    'medicine': mapping.medication_name,
                },
                expires_at=timezone.now() + datetime.timedelta(hours=24),
            )

        logger.info(
            f'Compartment rescheduled: device={device.id} compartment={compartment_number} '
            f'times={new_times} by caregiver={caregiver.user.email}'
        )

        return APIResponse.success({
            'compartment_number': compartment_number,
            'medication_name': mapping.medication_name,
            'new_times': new_times,
            'device_command_queued': True,
        }, message='Compartment schedule updated successfully.')
