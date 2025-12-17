"""
Export a cohort design to JSON.

Usage:
    python manage.py export_cohort_design <cohort_id> [--output <file.json>]
    python manage.py export_cohort_design --name "Cohort Name" [--output <file.json>]
    
Examples:
    # Export cohort with ID 1 to stdout
    python manage.py export_cohort_design 1
    
    # Export cohort with ID 1 to a file
    python manage.py export_cohort_design 1 --output cohort_design.json
    
    # Export cohort by name
    python manage.py export_cohort_design --name "January 2025 Cohort" --output jan2025.json
"""
from django.core.management.base import BaseCommand, CommandError
from cohorts.models import Cohort


class Command(BaseCommand):
    help = 'Export a cohort design (surveys + schedules) to JSON'

    def add_arguments(self, parser):
        parser.add_argument(
            'cohort_id',
            nargs='?',
            type=int,
            help='ID of the cohort to export'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Name of the cohort to export (alternative to ID)'
        )
        parser.add_argument(
            '--output', '-o',
            type=str,
            help='Output file path (default: stdout)'
        )
        parser.add_argument(
            '--indent',
            type=int,
            default=2,
            help='JSON indentation level (default: 2)'
        )

    def handle(self, *args, **options):
        cohort_id = options.get('cohort_id')
        cohort_name = options.get('name')
        output_file = options.get('output')
        indent = options.get('indent')
        
        # Get the cohort
        if cohort_id:
            try:
                cohort = Cohort.objects.get(pk=cohort_id)
            except Cohort.DoesNotExist:
                raise CommandError(f"Cohort with ID {cohort_id} does not exist")
        elif cohort_name:
            try:
                cohort = Cohort.objects.get(name=cohort_name)
            except Cohort.DoesNotExist:
                raise CommandError(f"Cohort with name '{cohort_name}' does not exist")
            except Cohort.MultipleObjectsReturned:
                raise CommandError(f"Multiple cohorts found with name '{cohort_name}'. Use --cohort_id instead.")
        else:
            # List available cohorts
            cohorts = Cohort.objects.all()
            if not cohorts.exists():
                raise CommandError("No cohorts found. Create a cohort first.")
            
            self.stdout.write("\nAvailable cohorts:")
            for c in cohorts:
                scheduler_count = c.task_schedulers.count()
                self.stdout.write(f"  ID {c.pk}: {c.name} ({scheduler_count} surveys scheduled)")
            self.stdout.write("\nUse: python manage.py export_cohort_design <ID> [--output <file>]")
            return
        
        # Export to JSON
        json_str = cohort.to_json(indent=indent)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(json_str)
            self.stdout.write(
                self.style.SUCCESS(f"Exported cohort '{cohort.name}' to {output_file}")
            )
        else:
            self.stdout.write(json_str)

