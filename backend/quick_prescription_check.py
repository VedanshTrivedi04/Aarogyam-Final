import os
import django
import sys

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.clinical.models import Prescription, Patient
from apps.iot.models import Device, DeviceCompartmentMapping, PhysicalCompartment, SubCompartment

def check_prescription():
    patient_id = "c5d8b018-809d-4462-901f-2d57852efa61"
    rx_id = "975fd0ec-ffa7-4e1a-a0f8-97d070b20c16"
    
    print("--- CHECKING PRESCRIPTION ---")
    rx = Prescription.all_objects.filter(id=rx_id).first()
    if rx:
        print(f"Prescription found: id={rx.id}, patient={rx.patient.id}, medication={rx.medication.name}, is_active={rx.is_active}, deleted_at={rx.deleted_at}")
    else:
        print(f"Prescription with id {rx_id} NOT found!")
        
    print("\n--- ALL PRESCRIPTIONS FOR PATIENT ---")
    rxs = Prescription.all_objects.filter(patient_id=patient_id)
    for r in rxs:
        print(f"rx_id={r.id}, med={r.medication.name}, is_active={r.is_active}, deleted_at={r.deleted_at}")
        
    print("\n--- RUNNING SOFT DELETE SIMULATION ---")
    if rx:
        try:
            # Let's run the soft delete logic step by step to see where it fails!
            print("Step 1: ReminderJob update")
            from apps.scheduling.models import ReminderJob
            reminders = ReminderJob.objects.filter(schedule__prescription=rx, status='PENDING')
            print("Found pending reminders:", reminders.count())
            
            print("Step 2: Get active device")
            device = Device.objects.filter(linked_patient=rx.patient, is_active=True).first()
            if device:
                print("Active device found:", device.device_name, "id=", device.id)
                compartments_to_update = set()
                if rx.compartment_number:
                    compartments_to_update.add(int(rx.compartment_number))
                mappings = DeviceCompartmentMapping.objects.filter(prescription=rx)
                print("Old mapping count:", mappings.count())
                for mapping in mappings:
                    compartments_to_update.add(int(mapping.compartment_number))
                    
                print("Compartments to update:", compartments_to_update)
                for comp_num in compartments_to_update:
                    comp = PhysicalCompartment.objects.filter(device=device, compartment_number=comp_num).first()
                    if comp:
                        print(f"PhysicalCompartment found: slot={comp_num}, time_slot={comp.time_slot}")
                        subs = SubCompartment.objects.filter(compartment=comp, medicine_name__iexact=rx.medication.name)
                        print("Subcompartments to deactivate count:", subs.count())
                        # Check if expected weight calculation has issues
                        from apps.iot.weight_service import calculate_compartment_expected_weight
                        active_subs = comp.sub_compartments.filter(is_active=True)
                        print("Active subcompartments count:", active_subs.count())
                        weight = calculate_compartment_expected_weight(active_subs)
                        print("Recalculated weight:", weight)
                    else:
                        print(f"PhysicalCompartment NOT found for slot {comp_num}")
            else:
                print("No active device found for patient.")
                
            print("Step 3: Calling rx.soft_delete()")
            rx.soft_delete()
            print("Soft delete call completed successfully!")
        except Exception as e:
            print("EXCEPTION CAUGHT:", str(e))
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    check_prescription()
