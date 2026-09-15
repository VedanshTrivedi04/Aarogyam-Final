"""
Manual end-to-end test trigger for the Agentic Pharmacy Agent.

Usage:
    python manage.py agent_test_refill --prescription-id <uuid> --dry-run
    python manage.py agent_test_refill --prescription-id <uuid>
"""

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Manually run the Pharmacy Agent's reason->plan->act pipeline for one prescription"

    def add_arguments(self, parser):
        parser.add_argument("--prescription-id", required=True, help="Prescription UUID")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Log the intended tool call instead of actually executing it",
        )

    def handle(self, *args, **options):
        prescription_id = options["prescription_id"]
        dry_run = options["dry_run"]

        try:
            from apps.clinical.models import Prescription
            prescription = Prescription.objects.filter(id=prescription_id).first()
            if not prescription:
                raise CommandError(f"No Prescription with id={prescription_id}")
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f"Could not look up prescription: {e}")

        patient_id = str(prescription.patient_id)

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Agentic Pharmacy Agent - Test Refill ==="))
        self.stdout.write(f"  Prescription : {prescription_id} ({prescription.medication.name})")
        self.stdout.write(f"  Patient      : {patient_id}")
        self.stdout.write(f"  Dry run      : {'YES (no real actions taken)' if dry_run else 'NO (real actions will execute)'}")

        from apps.agent_runtime.services.pharmacy_pipeline import run_pharmacy_refill

        result = run_pharmacy_refill(prescription_id=prescription_id, patient_id=patient_id, dry_run=dry_run)

        self.stdout.write("\nResult:")
        self.stdout.write(json.dumps(result, indent=2, default=str))

        if result.get("error"):
            self.stdout.write(self.style.ERROR(f"\nPipeline error: {result['error']}"))
            return

        if not result.get("action_taken"):
            self.stdout.write(self.style.WARNING("\nNo action was taken (LLM decided stock is healthy, or the LLM call failed)."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"\nTool '{result['tool_name']}' -> status {result['action_status']} "
            f"(AgentAction id={result['action_id']})"
        ))
