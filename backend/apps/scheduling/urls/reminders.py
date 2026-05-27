"""
apps/scheduling/urls/reminders.py
"""
from django.urls import path
from ..views.reminders import (
    TodayRemindersView, UpcomingRemindersView, ReminderDetailView,
    LogDoseView, SnoozeReminderView, ManualDoseView, TriggerDispatchView,
    DispenseNowView,
)

urlpatterns = [
    path('today/',                      TodayRemindersView.as_view(),    name='reminders-today'),
    path('upcoming/',                   UpcomingRemindersView.as_view(), name='reminders-upcoming'),
    path('trigger-dispatch/',           TriggerDispatchView.as_view(),   name='reminders-trigger-dispatch'),
    path('<uuid:reminder_id>/',         ReminderDetailView.as_view(),    name='reminder-detail'),
    path('<uuid:reminder_id>/log/',     LogDoseView.as_view(),           name='reminder-log'),
    path('<uuid:reminder_id>/dispense-now/', DispenseNowView.as_view(),  name='reminder-dispense-now'),
    path('<uuid:reminder_id>/snooze/',  SnoozeReminderView.as_view(),    name='reminder-snooze'),
]
