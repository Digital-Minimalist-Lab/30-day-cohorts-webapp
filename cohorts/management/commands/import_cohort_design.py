"""
Import a cohort design from JSON.

Usage:
    python manage.py import_cohort_design <file.json> [options]

Examples:
    # Create a new cohort
    python manage.py import_cohort_design cohort_design.json

    # Create with a custom name
    python manage.py import_cohort_design cohort_design.json --name "My Custom Cohort"

    # Update an existing cohort
    python manage.py import_cohort_design cohort_design.json --cohort-id 42

    # Validate only (don't create/update anything)
    python manage.py import_cohort_design cohort_design.json --validate-only
"""
import json
from django.core.management.base import BaseCommand, CommandError

from cohorts.models import Cohort
from cohorts.services.cohort_import import (
    validate_cohort_design,
    import_cohort_from_dict,
)


class Command(BaseCommand):
    help = 'Import a cohort design from a JSON file (create new or update existing)'

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to the JSON file containing the cohort design'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Override the cohort name from the JSON'
        )
        parser.add_argument(
            '--cohort-id',
            type=int,
            help='ID of an existing cohort to update (if not provided, creates a new cohort)'
        )
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate the JSON, do not create/update anything'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        name_override = options.get('name')
        cohort_id = options.get('cohort_id')
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
        errors = validate_cohort_design(data)
        if errors:
            self.stdout.write(self.style.ERROR("Validation errors:"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
            raise CommandError("JSON validation failed")

        if validate_only:
            self.stdout.write(self.style.SUCCESS("JSON is valid!"))
            self._print_summary(data)
            return

        # Check if cohort exists when updating
        if cohort_id is not None:
            if not Cohort.objects.filter(pk=cohort_id).exists():
                raise CommandError(f"Cohort with ID {cohort_id} does not exist")
            action = "Updated"
        else:
            action = "Created"

        # Import/update the cohort (validation already done, skip it)
        try:
            cohort = import_cohort_from_dict(
                data,
                name_override=name_override,
                cohort_id=cohort_id,
                validate=False,  # Already validated above
            )
        except Cohort.DoesNotExist:
            raise CommandError(f"Cohort with ID {cohort_id} does not exist")
        except ValueError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully {action.lower()} cohort:"))
        self.stdout.write(f"  Name: {cohort.name}")
        self.stdout.write(f"  ID: {cohort.pk}")
        self.stdout.write(f"  Start: {cohort.start_date}")
        self.stdout.write(f"  End: {cohort.end_date}")
        self.stdout.write(f"  Surveys scheduled: {cohort.task_schedulers.count()}")

        self.stdout.write(self.style.SUCCESS(f"\nCohort '{cohort.name}' is ready!"))

    def _print_summary(self, data):
        """Print a summary of what the JSON contains."""
        surveys = data.get("surveys", [])
        schedules = data.get("schedules", [])

        self.stdout.write(f"\nCohort Design:")
        self.stdout.write(f"  Name: {data.get('name', '(not specified)')}")
        dates = data.get("dates", {})
        self.stdout.write(f"  Start: {dates.get('cohort_start', '?')}")
        self.stdout.write(f"  End: {dates.get('cohort_end', '?')}")
        self.stdout.write(f"  Paid: {data.get('is_paid', False)}")

        self.stdout.write(f"\nSurveys ({len(surveys)}):")
        for survey in surveys:
            sections = survey.get("sections", [])
            question_count = sum(len(s.get("questions", [])) for s in sections)
            self.stdout.write(f"  - {survey.get('name', survey.get('id', '?'))}")
            self.stdout.write(f"    Questions: {question_count}")

        self.stdout.write(f"\nSchedules ({len(schedules)}):")
        for schedule in schedules:
            self.stdout.write(f"  - {schedule.get('slug')}: {schedule.get('frequency', '?')}")

