"""
Import a cohort design from JSON.

Usage:
    python manage.py import_cohort_design <file.json> --start-date YYYY-MM-DD [options]
    
Examples:
    # Import a cohort starting January 1, 2025
    python manage.py import_cohort_design cohort_design.json --start-date 2025-01-01
    
    # Import with a custom name
    python manage.py import_cohort_design cohort_design.json --start-date 2025-01-01 --name "My Custom Cohort"
    
    # Import and update existing surveys (instead of reusing them)
    python manage.py import_cohort_design cohort_design.json --start-date 2025-01-01 --update-surveys
    
    # Validate only (don't create anything)
    python manage.py import_cohort_design cohort_design.json --validate-only
"""
import json
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from cohorts.models import Cohort


class Command(BaseCommand):
    help = 'Import a cohort design from a JSON file'

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to the JSON file containing the cohort design'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for the cohort (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Override the cohort name from the JSON'
        )
        parser.add_argument(
            '--update-surveys',
            action='store_true',
            help='Update existing surveys with same slug (default: reuse existing)'
        )
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate the JSON, do not create anything'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        start_date_str = options.get('start_date')
        name_override = options.get('name')
        update_surveys = options.get('update_surveys', False)
        validate_only = options.get('validate_only', False)
        
        # Load the JSON file
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {json_file}")
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON in {json_file}: {e}")
        
        # Validate the JSON
        errors = Cohort.validate_design_dict(data)
        if errors:
            self.stdout.write(self.style.ERROR("Validation errors:"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
            raise CommandError("JSON validation failed")
        
        if validate_only:
            self.stdout.write(self.style.SUCCESS("JSON is valid!"))
            self._print_summary(data)
            return
        
        # Parse start date
        if not start_date_str:
            raise CommandError("--start-date is required (format: YYYY-MM-DD)")
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f"Invalid date format: {start_date_str}. Use YYYY-MM-DD.")
        
        # Import the cohort (validation already done, skip it)
        try:
            cohort = Cohort.from_design_dict(
                data,
                start_date=start_date,
                name_override=name_override,
                update_existing_surveys=update_surveys,
                validate=False,  # Already validated above
            )
        except ValueError as e:
            raise CommandError(str(e))
        
        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully created cohort:"))
        self.stdout.write(f"  Name: {cohort.name}")
        self.stdout.write(f"  ID: {cohort.pk}")
        self.stdout.write(f"  Start: {cohort.start_date}")
        self.stdout.write(f"  End: {cohort.end_date}")
        self.stdout.write(f"  Surveys scheduled: {cohort.task_schedulers.count()}")
        
        self.stdout.write(self.style.SUCCESS(f"\nCohort '{cohort.name}' is ready!"))
    
    def _print_summary(self, data):
        """Print a summary of what the JSON contains."""
        template = data.get("cohort_template", {})
        surveys = data.get("surveys", [])
        
        self.stdout.write(f"\nCohort Template:")
        self.stdout.write(f"  Name: {template.get('name', '(not specified)')}")
        self.stdout.write(f"  Duration: {template.get('duration_days', '?')} days")
        self.stdout.write(f"  Paid: {template.get('is_paid', False)}")
        
        self.stdout.write(f"\nSurveys ({len(surveys)}):")
        for survey in surveys:
            questions = survey.get("questions", [])
            schedule = survey.get("schedule", {})
            self.stdout.write(f"  - {survey.get('name', survey.get('slug', '?'))}")
            self.stdout.write(f"    Questions: {len(questions)}")
            self.stdout.write(f"    Schedule: {schedule.get('frequency', '?')}")

