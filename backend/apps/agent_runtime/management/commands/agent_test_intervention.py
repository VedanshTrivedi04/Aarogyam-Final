"""
Manual end-to-end test trigger for the Agentic AI Agent.

Usage:
    python manage.py agent_test_intervention --patient-id <uuid> --dry-run
    python manage.py agent_test_intervention --patient-id <uuid>
"""

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Manually run the AI Agent's reason->plan->act pipeline for one patient"

    def add_arguments(self, parser):
        parser.add_argument("--patient-id", required=True, help="Patient UUID")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Log the intended tool call instead of actually executing it",
        )

    def handle(self, *args, **options):
        patient_id = options["patient_id"]
        dry_run = options["dry_run"]

        try:
            from apps.clinical.models import Patient
            if not Patient.objects.filter(id=patient_id).exists():
                raise CommandError(f"No Patient with id={patient_id}")
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f"Could not look up patient: {e}")

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Agentic AI Agent — Test Intervention ==="))
        self.stdout.write(f"  Patient   : {patient_id}")
        self.stdout.write(f"  Dry run   : {'YES (no real actions taken)' if dry_run else 'NO (real actions will execute)'}")

        from apps.agent_runtime.services.pipeline import run_adherence_intervention

        result = run_adherence_intervention(patient_id=patient_id, dry_run=dry_run)

        self.stdout.write("\nResult:")
        self.stdout.write(json.dumps(result, indent=2, default=str))

        if result.get("error"):
            self.stdout.write(self.style.ERROR(f"\nPipeline error: {result['error']}"))
            return

        if not result.get("action_taken"):
            self.stdout.write(self.style.WARNING("\nNo action was taken (LLM decided no intervention was warranted, or LLM call failed)."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Tool '{result['tool_name']}' -> status {result['action_status']} "
            f"(AgentAction id={result['action_id']})"
        ))
