import os
import django
from django.utils import timezone

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.clinical.models import Prescription
from apps.iot.models import SubCompartment

def clean_database():
    print("Starting database clean up...")

    # 1. Handle prescription duplicate in Slot 1
    try:
        rx_to_delete = Prescription.objects.get(id="97a6ac7b-537f-403b-b47f-e7a5ac6969c6")
        rx_to_delete.is_active = False
        rx_to_delete.deleted_at = timezone.now()
        rx_to_delete.save()
        print("[SUCCESS] Soft-deleted older duplicate Prescription 97a6ac7b-537f-403b-b47f-e7a5ac6969c6")
    except Prescription.DoesNotExist:
        print("[INFO] Duplicate Prescription 97a6ac7b-537f-403b-b47f-e7a5ac6969c6 already cleaned or does not exist.")

    # 2. Handle sub-compartment duplicate in Compartment 1 (kjhsdfkjlghsdlkfhsd)
    try:
        sub1 = SubCompartment.objects.get(id="3c5d8e30-9bc7-456e-ac5a-de815af3e1a4")
        sub1.is_active = False
        sub1.save()
        print("[SUCCESS] Deactivated older SubCompartment 3c5d8e30-9bc7-456e-ac5a-de815af3e1a4 (Compartment 1)")
    except SubCompartment.DoesNotExist:
        print("[INFO] SubCompartment 3c5d8e30-9bc7-456e-ac5a-de815af3e1a4 does not exist.")

    # 3. Handle sub-compartment duplicate in Compartment 2 (dcasdasdasdsdad)
    try:
        sub2 = SubCompartment.objects.get(id="42fbad5c-b17e-4d2c-afe0-5189bed56ee2")
        sub2.is_active = False
        sub2.save()
        print("[SUCCESS] Deactivated older SubCompartment 42fbad5c-b17e-4d2c-afe0-5189bed56ee2 (Compartment 2)")
    except SubCompartment.DoesNotExist:
        print("[INFO] SubCompartment 42fbad5c-b17e-4d2c-afe0-5189bed56ee2 does not exist.")

    print("\nDatabase cleanup process completed.")

if __name__ == '__main__':
    clean_database()
