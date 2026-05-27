"""
apps/clinical/urls/caregivers.py
"""
from django.urls import path
from ..views.caregivers import (
    CaregiverPatientListView, CaregiverPatientDetailView,
    CaregiverPatientAdherenceSummaryView, CaregiverPatientAdherenceTimelineView,
    CaregiverPatientAdherenceMedicationsView, CaregiverPatientAdherenceExportView,
    CaregiverPatientAlertsView,
    CaregiverPatientAddView, CaregiverPatientPrescriptionsView, CaregiverPatientDevicesView,
    CaregiverCompartmentRescheduleView,
)

urlpatterns = [
    path('patients/',                              CaregiverPatientListView.as_view(),     name='caregiver-patients'),
    path('patients/add/',                          CaregiverPatientAddView.as_view(),      name='caregiver-patient-add'),
    path('patients/<uuid:patient_id>/',            CaregiverPatientDetailView.as_view(),   name='caregiver-patient-detail'),
    path('patients/<uuid:patient_id>/adherence/summary/', CaregiverPatientAdherenceSummaryView.as_view(), name='caregiver-patient-adherence-summary'),
    path('patients/<uuid:patient_id>/adherence/timeline/', CaregiverPatientAdherenceTimelineView.as_view(), name='caregiver-patient-adherence-timeline'),
    path('patients/<uuid:patient_id>/adherence/medications/', CaregiverPatientAdherenceMedicationsView.as_view(), name='caregiver-patient-adherence-medications'),
    path('patients/<uuid:patient_id>/adherence/export/', CaregiverPatientAdherenceExportView.as_view(), name='caregiver-patient-adherence-export'),
    path('patients/<uuid:patient_id>/alerts/',     CaregiverPatientAlertsView.as_view(),   name='caregiver-patient-alerts'),
    path('patients/<uuid:patient_id>/prescriptions/', CaregiverPatientPrescriptionsView.as_view(), name='caregiver-patient-prescriptions'),
    path('patients/<uuid:patient_id>/prescriptions/<uuid:prescription_id>/', CaregiverPatientPrescriptionsView.as_view(), name='caregiver-patient-prescription-detail'),
    path('patients/<uuid:patient_id>/devices/',    CaregiverPatientDevicesView.as_view(),  name='caregiver-patient-devices'),
    path('patients/<uuid:patient_id>/devices/<uuid:device_id>/compartments/<int:compartment_number>/reschedule/',
         CaregiverCompartmentRescheduleView.as_view(), name='caregiver-compartment-reschedule'),
]
