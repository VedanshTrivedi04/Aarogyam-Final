from django.urls import path
from .views import (
    # ── Existing views (unchanged) ───────────────────────────────
    DeviceListView, ValidateDeviceCodeView, DeviceLinkView, DeviceProvisionView,
    DeviceDetailView, DeviceLinkPatientView, DeviceUnlinkView, DeviceStatusView,
    DeviceEventsView, DeviceCompartmentMappingView, DeviceCommandCreateView,
    FillModeStartView, FillModeNextView, FillModeEndView,
    CompartmentInventoryView, MealLogView,
    DeviceEventIngestView, DeviceHeartbeatView, DeviceCommandPollView,
    # ── New dispenser views ──────────────────────────────────────
    DispenserCompartmentSetupView, DispenserCompartmentListView,
    DispenserAddMedicineView, DispenserMedicineListView,
    DispenserFillCompleteView, DispenserCurrentScheduleView,
    DispenserUpdateSlotTimeView,
    FillWeightMeasureView, FillWeightIngestView,
    GateEventView, WeightReadingView,
    DoseHistoryView, MissedDoseView, CaregiverUnlockView, DoseAlertsView,
    SyncTimeView,
)

urlpatterns = [
    # ── Firmware (X-Device-Key) ──────────────────────────────────
    path('events/',    DeviceEventIngestView.as_view(),  name='iot-event-ingest'),
    path('heartbeat/', DeviceHeartbeatView.as_view(),    name='iot-heartbeat'),
    path('devices/<uuid:device_id>/commands/', DeviceCommandPollView.as_view(), name='iot-command-poll'),

    # ── New firmware endpoints (X-Device-Key) ───────────────────
    path('events/gate-event/',    GateEventView.as_view(),    name='iot-gate-event'),
    path('events/weight-reading/', WeightReadingView.as_view(), name='iot-weight-reading'),
    path('events/fill-weight/',   FillWeightIngestView.as_view(), name='iot-fill-weight'),
    path('sync/time/',            SyncTimeView.as_view(),      name='iot-sync-time'),
    path('devices/<uuid:device_id>/dispenser/schedule/current/',
         DispenserCurrentScheduleView.as_view(), name='iot-dispenser-schedule'),

    # ── Meal Log ─────────────────────────────────────────────────
    path('meal-log/', MealLogView.as_view(), name='iot-meal-log'),

    # ── Dose management (JWT) ────────────────────────────────────
    path('dose/history/',           DoseHistoryView.as_view(),    name='iot-dose-history'),
    path('dose/missed/',            MissedDoseView.as_view(),     name='iot-dose-missed'),
    path('dose/caregiver-unlock/',  CaregiverUnlockView.as_view(), name='iot-caregiver-unlock'),
    path('dose/alerts/',            DoseAlertsView.as_view(),     name='iot-dose-alerts'),

    # ── Dispenser setup + medicine management (JWT) ──────────────
    path('devices/<uuid:pk>/dispenser/setup/',
         DispenserCompartmentSetupView.as_view(), name='iot-dispenser-setup'),
    path('devices/<uuid:pk>/dispenser/compartments/',
         DispenserCompartmentListView.as_view(), name='iot-dispenser-compartments'),
    path('devices/<uuid:pk>/dispenser/compartments/<int:compartment_num>/time/',
         DispenserUpdateSlotTimeView.as_view(), name='iot-dispenser-update-time'),
    path('devices/<uuid:pk>/dispenser/compartments/<int:compartment_num>/medicine/add/',
         DispenserAddMedicineView.as_view(), name='iot-dispenser-add-medicine'),
    path('devices/<uuid:pk>/dispenser/compartments/<int:compartment_num>/medicines/',
         DispenserMedicineListView.as_view(), name='iot-dispenser-medicines'),
    path('devices/<uuid:pk>/dispenser/compartments/<int:compartment_num>/medicines/<uuid:medicine_id>/',
         DispenserMedicineListView.as_view(), name='iot-dispenser-medicine-delete'),
    path('devices/<uuid:pk>/dispenser/compartments/<int:compartment_num>/medicines/<uuid:medicine_id>/measure-weight/',
         FillWeightMeasureView.as_view(), name='iot-fill-measure-weight'),
    path('devices/<uuid:pk>/dispenser/fill/complete/',
         DispenserFillCompleteView.as_view(), name='iot-dispenser-fill-complete'),

    # ── JWT User Endpoints (unchanged) ──────────────────────────
    path('devices/',                              DeviceListView.as_view(),           name='iot-device-list'),
    path('devices/validate-code/',                ValidateDeviceCodeView.as_view(),   name='iot-validate-code'),
    path('devices/link/',                         DeviceLinkView.as_view(),           name='iot-device-link'),
    path('devices/provision/',                    DeviceProvisionView.as_view(),      name='iot-device-provision'),
    path('devices/<uuid:pk>/',                    DeviceDetailView.as_view(),         name='iot-device-detail'),
    path('devices/<uuid:pk>/link-patient/',       DeviceLinkPatientView.as_view(),    name='iot-device-link-patient'),
    path('devices/<uuid:pk>/unlink/',             DeviceUnlinkView.as_view(),         name='iot-device-unlink'),
    path('devices/<uuid:pk>/status/',             DeviceStatusView.as_view(),         name='iot-device-status'),
    path('devices/<uuid:pk>/events/',             DeviceEventsView.as_view(),         name='iot-device-events'),
    path('devices/<uuid:pk>/commands/queue/',     DeviceCommandCreateView.as_view(),  name='iot-command-queue'),
    path('devices/<uuid:pk>/inventory/',          CompartmentInventoryView.as_view(), name='iot-inventory'),
    # Fill Mode (existing)
    path('devices/<uuid:pk>/fill/start/',         FillModeStartView.as_view(),        name='iot-fill-start'),
    path('devices/<uuid:pk>/fill/next/',          FillModeNextView.as_view(),         name='iot-fill-next'),
    path('devices/<uuid:pk>/fill/end/',           FillModeEndView.as_view(),          name='iot-fill-end'),
    # Compartments (existing)
    path('devices/<uuid:device_id>/compartments/', DeviceCompartmentMappingView.as_view(), name='iot-compartments'),
]
