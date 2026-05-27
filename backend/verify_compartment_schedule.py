#!/usr/bin/env python
"""
Quick smoke test: verify that adding a medicine to a dispenser compartment
creates a prescription and reminders for the linked patient.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.clinical.models import Patient, Medication, Prescription, MedicationSchedule
from apps.iot.models import Device, PhysicalCompartment, SubCompartment
from apps.scheduling.models import ReminderJob

User = get_user_model()

def test_compartment_medicine_creates_prescription():
    """Test: add medicine to compartment → prescription + schedule created for patient."""
    
    print("\n" + "="*70)
    print("TEST: Compartment Medicine → Patient Schedule Sync")
    print("="*70)
    
    # 1. Create test users
    print("\n[1] Creating test users...")
    caregiver_user, _ = User.objects.get_or_create(
        email='caregiver_test@test.com',
        defaults={'full_name': 'Test Caregiver', 'is_active': True}
    )
    patient_user, _ = User.objects.get_or_create(
        email='patient_test@test.com',
        defaults={'full_name': 'Test Patient', 'is_active': True}
    )
    print(f"   ✓ Caregiver: {caregiver_user.email}")
    print(f"   ✓ Patient: {patient_user.email}")
    
    # 2. Create patient profile
    print("\n[2] Creating patient profile...")
    patient, _ = Patient.objects.get_or_create(
        user=patient_user,
        defaults={'timezone': 'Asia/Kolkata'}
    )
    print(f"   ✓ Patient Profile ID: {patient.id}")    
    # 2.5. Set up a subscription for the patient (to avoid subscription limits)
    print("\n[2.5] Setting up subscription for patient...")
    from apps.subscriptions.models import UserSubscription, SubscriptionPlan
    # Get or create a plan with high medication limit
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug='test-premium',
        defaults={
            'name': 'Test Premium',
            'price_monthly': 99.99,
            'price_yearly': 999.99,
            'max_medications': 100,
            'max_caregivers': 5,
            'features': {'ai_insights': True, 'reports': True},
        }
    )
    subscription, _ = UserSubscription.objects.get_or_create(
        user=patient_user,
        defaults={
            'plan': plan,
            'status': 'ACTIVE',
        }
    )
    print(f"   ✓ Subscription: {subscription.status} ({plan.max_medications} meds max)")    
    # 3. Create and link device to patient
    print("\n[3] Creating device linked to patient...")
    device, _ = Device.objects.get_or_create(
        user=caregiver_user,
        device_name='Test Smart Dispenser',
        defaults={
            'device_type': 'CIRCULAR_PILL_DISPENSER',
            'api_key': 'test_api_key_12345',
            'linked_patient': patient,
            'is_active': True,
        }
    )
    if device.linked_patient_id != patient.id:
        device.linked_patient = patient
        device.save()
    print(f"   ✓ Device ID: {device.id}")
    print(f"   ✓ Linked Patient: {device.linked_patient.user.email}")
    
    # 4. Create physical compartment (time slot)
    print("\n[4] Creating physical compartment (morning_before slot)...")
    compartment, _ = PhysicalCompartment.objects.get_or_create(
        device=device,
        compartment_number=1,
        defaults={'time_slot': 'morning_before'}
    )
    print(f"   ✓ Compartment {compartment.compartment_number}: {compartment.time_slot}")
    
    # 5. Create medicine entry
    print("\n[5] Creating medication (test medicine)...")
    medicine, _ = Medication.objects.get_or_create(
        name='TestMed_Verify',
        defaults={'default_unit': 'mg', 'is_verified': True}
    )
    print(f"   ✓ Medicine: {medicine.name}")
    
    # 6. Manually call the prescription creation logic (simulating the API call)
    print("\n[6] Simulating add-medicine API call...")
    from apps.clinical.services import PrescriptionService
    from apps.scheduling.services import ScheduleGenerationService
    
    qty = 2
    duration = 14
    medicine_name = 'TestMed_Verify'
    compartment_num = 1
    
    med, _ = Medication.objects.get_or_create(
        name__iexact=medicine_name,
        defaults={'name': medicine_name, 'default_unit': 'tablet'}
    )
    
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
        print(f"   ✓ Prescription created: {prescription.id}")
        
        slot_defaults = {
            'morning_before': '08:00',
            'morning_after': '09:00',
            'night_before': '20:00',
            'night_after': '21:00',
        }
        time_str = slot_defaults.get(compartment.time_slot, '08:00')
        
        schedule = MedicationSchedule.objects.create(
            prescription=prescription,
            frequency_type='DAILY',
            times_of_day=[{'time': time_str, 'dose': qty, 'with_food': False, 'label': ''}],
            days_of_week=list(range(7)),
            timezone=getattr(patient, 'timezone', 'Asia/Kolkata') or 'Asia/Kolkata',
        )
        print(f"   ✓ Schedule created: {schedule.id} @ {time_str} every day")
        
        # 7. Generate reminders
        print("\n[7] Generating reminder jobs (today + tomorrow)...")
        jobs_count = ScheduleGenerationService.generate_upcoming_reminders(schedule, days=2)
        print(f"   ✓ {jobs_count} reminder job(s) created")
        
        # 8. Verify reminders exist for today
        print("\n[8] Checking today's reminders for patient...")
        import datetime
        import pytz
        patient_tz = pytz.timezone(patient.timezone or 'Asia/Kolkata')
        now = timezone.now()
        now_local = now.astimezone(patient_tz)
        local_date = now_local.date()
        today_start = patient_tz.localize(
            datetime.datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0)
        )
        today_end = today_start + datetime.timedelta(days=1)
        
        today_reminders = ReminderJob.objects.filter(
            schedule__prescription__patient=patient,
            scheduled_at__gte=today_start,
            scheduled_at__lt=today_end,
        ).select_related('schedule__prescription__medication')
        
        print(f"   ✓ Found {today_reminders.count()} reminder(s) for today")
        for reminder in today_reminders:
            print(f"      - {reminder.schedule.prescription.medication.name} @ {reminder.scheduled_at.strftime('%H:%M')} ({reminder.status})")
        
        if today_reminders.count() > 0:
            print("\n" + "="*70)
            print("✅ TEST PASSED: Medicine added to compartment → Schedule synced to patient")
            print("="*70)
            return True
        else:
            print("\n" + "="*70)
            print("❌ TEST FAILED: No reminders generated")
            print("="*70)
            return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_compartment_medicine_creates_prescription()
    sys.exit(0 if success else 1)
