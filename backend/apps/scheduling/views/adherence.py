"""
apps/scheduling/views/adherence.py — Adherence summary, timeline, and history endpoints.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from shared.response import APIResponse
from shared.permissions import IsPatient
from shared.pagination import StandardResultsPagination
from ..models import DoseLog, AdherenceSummary
from ..serializers import DoseLogSerializer, AdherenceSummarySerializer
from ..services import AdherenceReportService


def get_patient_or_404(user):
    try:
        return user.patient_profile
    except Exception:
        from django.http import Http404
        raise Http404


class AdherenceSummaryView(APIView):
    """GET /api/v1/adherence/summary/?days=30"""
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        patient = get_patient_or_404(request.user)

        # Subscription gate: limit history_days for free/freemium users
        from apps.subscriptions.gates import SubscriptionGate
        max_days = SubscriptionGate.get_limit(request.user, 'history_days')
        days     = min(int(request.query_params.get('days', 30)), max_days)

        summary = AdherenceReportService.get_summary(patient, days=days)
        return APIResponse.success(summary)


class AdherenceTimelineView(APIView):
    """GET /api/v1/adherence/timeline/?days=30 — per-day chart data."""
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        patient = get_patient_or_404(request.user)
        from apps.subscriptions.gates import SubscriptionGate
        max_days = SubscriptionGate.get_limit(request.user, 'history_days')
        days     = min(int(request.query_params.get('days', 30)), max_days)
        timeline = AdherenceReportService.get_timeline(patient, days=days)
        return APIResponse.success(timeline)


class AdherenceMedicationBreakdownView(APIView):
    """GET /api/v1/adherence/medications/?days=30 — per-medication breakdown."""
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        patient = get_patient_or_404(request.user)
        from apps.subscriptions.gates import SubscriptionGate
        max_days = SubscriptionGate.get_limit(request.user, 'history_days')
        days     = min(int(request.query_params.get('days', 30)), max_days)
        breakdown = AdherenceReportService.get_medication_breakdown(patient, days=days)
        return APIResponse.success(breakdown)


class DoseHistoryView(APIView):
    """GET /api/v1/adherence/history/?prescription_id=&status=&days="""
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        from django.utils import timezone
        import datetime
        patient = get_patient_or_404(request.user)
        from apps.subscriptions.gates import SubscriptionGate
        max_days = SubscriptionGate.get_limit(request.user, 'history_days')
        days     = min(int(request.query_params.get('days', 7)), max_days)
        since    = timezone.now() - datetime.timedelta(days=days)

        qs = DoseLog.objects.filter(
            prescription__patient=patient,
            taken_at__gte=since,
        ).select_related('prescription__medication', 'logged_by')

        # Optional filters
        rx_id = request.query_params.get('prescription_id')
        if rx_id:
            qs = qs.filter(prescription_id=rx_id)

        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status.upper())

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs.order_by('-taken_at'), request)
        return paginator.get_paginated_response(DoseLogSerializer(page, many=True).data)


class DoseLogDetailView(APIView):
    """GET/PATCH /api/v1/adherence/history/{id}/ — update notes / mood / pain score."""
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request, log_id):
        patient = get_patient_or_404(request.user)
        log = get_object_or_404(DoseLog, id=log_id, prescription__patient=patient)
        return APIResponse.success(DoseLogSerializer(log).data)

    def patch(self, request, log_id):
        patient = get_patient_or_404(request.user)
        log     = get_object_or_404(DoseLog, id=log_id, prescription__patient=patient)
        updatable = ['notes', 'side_effects', 'mood_score', 'pain_score', 'with_food']
        for field in updatable:
            if field in request.data:
                setattr(log, field, request.data[field])
        log.save(update_fields=updatable + ['updated_at'])
        return APIResponse.success(DoseLogSerializer(log).data, message='Dose log updated.')


class AdherenceReportExportView(APIView):
    """GET /api/v1/adherence/export/?days=90&format=csv — Premium only."""
    permission_classes = [IsAuthenticated, IsPatient]

    def get(self, request):
        from apps.subscriptions.gates import SubscriptionGate
        try:
            SubscriptionGate.check_feature(request.user, 'report_export')
        except Exception as e:
            return APIResponse.error(str(e), code='SUBSCRIPTION_LIMIT', status=402)

        patient = get_patient_or_404(request.user)
        days    = min(int(request.query_params.get('days', 30)), 365)
        fmt     = request.query_params.get('format', 'json')

        from django.utils import timezone
        import datetime
        since = timezone.now() - datetime.timedelta(days=days)

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

            # Fetch stats summary
            summary = AdherenceReportService.get_summary(patient, days=days)
            breakdown = AdherenceReportService.get_medication_breakdown(patient, days=days)

            # Format logs for template
            log_list = []
            for log in logs[:200]: # limit to top 200 logs for beautiful presentation
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
                        @bottom-right {{
                            content: "Page " counter(page) " of " counter(pages);
                            font-family: Arial, sans-serif;
                            font-size: 8pt;
                            color: #64748b;
                        }}
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
                    }}
                    .header-logo {{
                        font-size: 22pt;
                        font-weight: bold;
                        color: #4f46e5;
                    }}
                    .header-title {{
                        text-align: right;
                        font-size: 13pt;
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
                        background-color: #f8fafc;
                        border: 1px solid #e2e8f0;
                        margin-bottom: 20px;
                    }}
                    .info-td {{
                        padding: 10px;
                        font-size: 9pt;
                        color: #334155;
                        width: 50%;
                    }}
                    .section-title {{
                        font-size: 12pt;
                        font-weight: bold;
                        color: #0f172a;
                        border-bottom: 2px solid #e2e8f0;
                        padding-bottom: 4px;
                        margin-bottom: 12px;
                        margin-top: 20px;
                    }}
                    .kpi-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 20px;
                    }}
                    .kpi-card {{
                        background-color: #f1f5f9;
                        border: 1px solid #cbd5e1;
                        padding: 12px;
                        text-align: center;
                    }}
                    .kpi-value {{
                        font-size: 16pt;
                        font-weight: bold;
                        color: #4f46e5;
                    }}
                    .kpi-label {{
                        font-size: 7.5pt;
                        font-weight: bold;
                        color: #475569;
                        text-transform: uppercase;
                    }}
                    .data-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 16px;
                    }}
                    .data-table th {{
                        background-color: #4f46e5;
                        color: #ffffff;
                        font-size: 8.5pt;
                        font-weight: bold;
                        text-align: left;
                        padding: 6px 8px;
                    }}
                    .data-table td {{
                        font-size: 8pt;
                        border-bottom: 1px solid #e2e8f0;
                        padding: 6px 8px;
                    }}
                    .status-badge {{
                        font-weight: bold;
                        font-size: 7.5pt;
                        padding: 2px 6px;
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
                        <td class="kpi-card" style="width: 25%;">
                            <div class="kpi-value">{summary['adherence_pct']}%</div>
                            <div class="kpi-label">Adherence Score</div>
                        </td>
                        <td class="kpi-card" style="width: 25%;">
                            <div class="kpi-value">{summary['total_scheduled']}</div>
                            <div class="kpi-label">Total Doses</div>
                        </td>
                        <td class="kpi-card" style="width: 25%;">
                            <div class="kpi-value">{summary['taken']}</div>
                            <div class="kpi-label">Taken Doses</div>
                        </td>
                        <td class="kpi-card" style="width: 25%;">
                            <div class="kpi-value">{summary['missed']}</div>
                            <div class="kpi-label">Missed Doses</div>
                        </td>
                    </tr>
                </table>

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
                            <td colspan="5" style="text-align: center; color: #64748b; padding: 12px;">No active clinical schedules for this period.</td>
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
                            <td colspan="6" style="text-align: center; color: #64748b; padding: 12px;">No history logs found for this period.</td>
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
                    for link in caregivers:
                        if link.caregiver.user.email:
                            recipient_emails.append(link.caregiver.user.email)
                    
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
                        msg.send(fail_silently=True)
                except Exception as e:
                    logger.error(f"Failed to send adherence report email for patient {patient.id}: {e}")

                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="adherence_report_{days}d.pdf"'
                return response

            return APIResponse.error('Failed to generate PDF document.')

        return APIResponse.success(DoseLogSerializer(logs[:500], many=True).data)
