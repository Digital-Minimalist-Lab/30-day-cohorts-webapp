from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Cohort, TaskScheduler
from surveys.models import Survey
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Cohort)
def create_default_task_schedulers(sender, instance: Cohort, created: bool, **kwargs):
    """
    When a new Cohort is created, create the default set of TaskSchedulers for it.
    """
    if not created:
        return

    # Define the default schedules for a new cohort.
    # This assumes Surveys with these slugs have been created (e.g., in a data migration).
    default_schedules_config = [
        {
            'slug': 'entry-survey',
            'frequency': TaskScheduler.Frequency.ONCE,
            'offset_days': 0,
            'offset_from': TaskScheduler.OffsetFrom.START,
            'is_cumulative': False,
        },
        {
            'slug': 'exit-survey',
            'frequency': TaskScheduler.Frequency.ONCE,
            'offset_days': 0,
            'offset_from': TaskScheduler.OffsetFrom.END,
            'is_cumulative': False,
        },
        {
            'slug': 'daily-check-in',
            'frequency': TaskScheduler.Frequency.DAILY,
            'is_cumulative': False,
        },
        {
            'slug': 'weekly-reflection',
            'frequency': TaskScheduler.Frequency.WEEKLY,
            'day_of_week': 6,  # Sunday
            'is_cumulative': True,
        },
    ]

    for config in default_schedules_config:
        slug = config.pop('slug')
        try:
            # Find the survey with the specified slug to use as the default.
            survey_to_schedule = Survey.objects.filter(slug=slug).first()
            if survey_to_schedule:
                TaskScheduler.objects.get_or_create(
                    cohort=instance, survey=survey_to_schedule,
                    defaults=config
                )
                logger.info(f"Created schedule for new cohort '{instance.name}' using survey '{slug}'.")
        except Exception as e:
            logger.error(f"Could not create schedule for cohort '{instance.name}' for survey '{slug}'. Error: {e}")
