"""
apps/iot/migrations/0007_physicalcompartment_scheduled_time.py
Adds customizable scheduled_time (HH:MM) to PhysicalCompartment.
Existing rows get their default from the time_slot field.
"""
from django.db import migrations, models


def set_default_times(apps, schema_editor):
    """Populate scheduled_time for existing rows based on their time_slot."""
    PhysicalCompartment = apps.get_model('iot', 'PhysicalCompartment')
    slot_defaults = {
        'morning_before': '08:00',
        'morning_after':  '09:00',
        'night_before':   '20:00',
        'night_after':    '21:00',
    }
    for comp in PhysicalCompartment.objects.all():
        comp.scheduled_time = slot_defaults.get(comp.time_slot, '08:00')
        comp.save(update_fields=['scheduled_time'])


class Migration(migrations.Migration):

    dependencies = [
        ('iot', '0006_alter_devicecommand_command_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='physicalcompartment',
            name='scheduled_time',
            field=models.CharField(
                default='08:00',
                max_length=5,
                help_text='Custom alarm time in HH:MM format (24h). Caregiver can change this.',
            ),
        ),
        migrations.RunPython(set_default_times, migrations.RunPython.noop),
    ]
