from django.core.management.base import BaseCommand
from surveys.seed import seed_surveys


class Command(BaseCommand):
    help = 'Seeds the database with a default set of surveys and questions.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Seeding/updating default survey data...'))

        # The `update=True` flag will use `update_or_create` to allow running this command multiple times.
        for survey, created in seed_surveys(update=True):
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created Survey: "{survey.name}"'))
            else:
                self.stdout.write(self.style.NOTICE(f'  Survey "{survey.name}" already exists, updating.'))

        self.stdout.write(self.style.SUCCESS('Successfully seeded survey data.'))
