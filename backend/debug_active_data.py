import os
import django
import sys

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.clinical.models import Prescription, Patient
from apps.iot.models import Device, DeviceCompartmentMapping, PhysicalCompartment, SubCompartment

def inspect_all():
    print("=== PATIENTS ===")
    for p in Patient.objects.all():
        print(f"Patient ID: {p.id}, Code: {p.patient_code}, Name: {p.user.full_name}")
        
        print("  --- Active Prescriptions ---")
        prescriptions = Prescription.objects.filter(patient=p, deleted_at__isnull=True)
        for rx in prescriptions:
            print(f"    Rx ID: {rx.id}, Medication: {rx.medication.name}, Compartment: {rx.compartment_number}, Created: {rx.created_at}")
            
        print("  --- Linked Devices ---")
        devices = Device.objects.filter(linked_patient=p, is_active=True)
        for dev in devices:
            print(f"    Device ID: {dev.id}, Name: {dev.device_name}")
            
            print("    --- DeviceCompartmentMappings ---")
            mappings = DeviceCompartmentMapping.objects.filter(device=dev)
            for m in mappings:
                print(f"      Mapping ID: {m.id}, Comp: {m.compartment_number}, Medication: {m.medication_name}, Rx: {m.prescription_id}")
                
            print("    --- PhysicalCompartments & SubCompartments ---")
            phys_comps = PhysicalCompartment.objects.filter(device=dev)
            for pc in phys_comps:
                print(f"      Physical Compartment: {pc.compartment_number}, Expected weight: {pc.expected_weight_grams}g")
                sub_comps = SubCompartment.objects.filter(compartment=pc, is_active=True)
                for sc in sub_comps:
                    print(f"        SubCompartment ID: {sc.id}, Medicine: {sc.medicine_name}, Qty: {sc.quantity_per_dose}, Created: {sc.created_at}")

if __name__ == '__main__':
    inspect_all()
