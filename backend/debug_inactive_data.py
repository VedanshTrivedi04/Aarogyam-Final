import os
import django
import sys

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.clinical.models import Prescription, Patient
from apps.iot.models import Device, DeviceCompartmentMapping, PhysicalCompartment, SubCompartment

def inspect_all():
    patient_id = "c5d8b018-809d-4462-901f-2d57852efa61"
    p = Patient.objects.get(id=patient_id)
    print(f"Patient Name: {p.user.full_name}")
    
    print("\n=== ALL PRESCRIPTIONS (with_deleted) ===")
    rxs = Prescription.all_objects.filter(patient=p)
    for rx in rxs:
        print(f"Rx ID: {rx.id}, Medication: {rx.medication.name}, Compartment: {rx.compartment_number}, is_active: {rx.is_active}, deleted_at: {rx.deleted_at}")
        
    print("\n=== ALL PHYSICAL COMPARTMENTS & SUB-COMPARTMENTS ===")
    dev = Device.objects.filter(linked_patient=p, is_active=True).first()
    if dev:
        print(f"Device: {dev.device_name}")
        phys_comps = PhysicalCompartment.objects.filter(device=dev)
        for pc in phys_comps:
            print(f"Compartment {pc.compartment_number}:")
            # Get all sub-compartments, both active and inactive
            sub_comps = SubCompartment.objects.filter(compartment=pc)
            for sc in sub_comps:
                print(f"  SubCompartment ID: {sc.id}, Medicine: {sc.medicine_name}, is_active: {sc.is_active}, created_at: {sc.created_at}")
    else:
        print("No active device found.")

if __name__ == '__main__':
    inspect_all()
