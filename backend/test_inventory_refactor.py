import os
import django

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.iot.models import Device, PhysicalCompartment, SubCompartment, DeviceCompartmentMapping

def test_inventory_logic():
    device_id = 'e214a30b-c919-4d23-b3f1-80557b756cdd'
    device = Device.objects.get(id=device_id)
    print("Device Name:", device.device_name)
    
    # Simulate new inventory serialization
    inventory = []
    
    # We want to represent compartments 1 to 4
    for slot_num in range(1, 5):
        comp = device.physical_compartments.filter(compartment_number=slot_num, is_active=True).first()
        
        # Default mapping details
        slot_map = {1: 'morning_before', 2: 'morning_after', 3: 'night_before', 4: 'night_after'}
        time_slot = slot_map.get(slot_num, 'morning_before')
        
        # Fallback time slot values for meal dependency
        meal_dep_map = {
            'morning_before': 'BEFORE_BREAKFAST',
            'morning_after': 'AFTER_BREAKFAST',
            'night_before': 'BEFORE_DINNER',
            'night_after': 'AFTER_DINNER'
        }
        
        if comp:
            active_subs = comp.sub_compartments.filter(is_active=True)
            medication_name = ", ".join(sub.medicine_name for sub in active_subs) if active_subs.exists() else ""
            
            # Fetch scheduled times from old mapping or fallback
            mapping = DeviceCompartmentMapping.objects.filter(device=device, compartment_number=slot_num).first()
            if mapping:
                scheduled_times = mapping.scheduled_times
                priority = mapping.priority
                meal_dep = mapping.meal_dependency
            else:
                slot_times = {
                    'morning_before': ['08:00'],
                    'morning_after': ['09:00'],
                    'night_before': ['20:00'],
                    'night_after': ['21:00'],
                }
                scheduled_times = slot_times.get(comp.time_slot, [])
                priority = 'NORMAL'
                meal_dep = meal_dep_map.get(comp.time_slot, 'NONE')
                
            total_pills = sum(sub.total_pills for sub in active_subs)
            pills_remaining = total_pills
            
            # Estimate pills remaining from current balance weight
            if comp.expected_weight_grams > 0:
                ratio = comp.current_balance_weight_grams / comp.expected_weight_grams
                ratio = max(0.0, min(1.0, ratio))
                pills_remaining = int(round(total_pills * ratio))
                
            doses_per_day = len(scheduled_times) if scheduled_times else 1
            days_remaining = pills_remaining // doses_per_day
            needs_refill = pills_remaining <= 3 or days_remaining <= 3 if active_subs.exists() else False
            is_filled = comp.expected_weight_grams > 0 or active_subs.exists()
            last_filled_at = comp.last_filled_at
        else:
            # Empty compartment representation
            medication_name = ""
            priority = 'NORMAL'
            meal_dep = meal_dep_map.get(time_slot, 'NONE')
            total_pills = 0
            pills_remaining = 0
            days_remaining = 0
            needs_refill = False
            is_filled = False
            last_filled_at = None
            slot_times = {
                'morning_before': ['08:00'],
                'morning_after': ['09:00'],
                'night_before': ['20:00'],
                'night_after': ['21:00'],
            }
            scheduled_times = slot_times.get(time_slot, [])
            
        inventory.append({
            'compartment': slot_num,
            'medication_name': medication_name,
            'priority': priority,
            'meal_dependency': meal_dep,
            'total_pills': total_pills,
            'pills_remaining': pills_remaining,
            'days_remaining': days_remaining,
            'needs_refill': needs_refill,
            'is_filled': is_filled,
            'last_filled_at': last_filled_at,
            'scheduled_times': scheduled_times,
        })
        
    print("\n--- Serialized Inventory ---")
    for item in inventory:
        print(item)

if __name__ == '__main__':
    test_inventory_logic()
