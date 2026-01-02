"""
Service for importing cohort designs from JSON.

This module handles the creation and updating of Cohort, Survey, Question, and
TaskScheduler objects from a cohort design dictionary (typically loaded from JSON).
"""
from __future__ import annotations

import logging

import jsonschema
from django.db import transaction

from cohorts.models import Cohort, TaskScheduler, UserSurveyResponse
from surveys.models import Survey, Question, SurveySubmission, SurveySection

logger = logging.getLogger(__name__)


# JSON Schema for validating cohort design structure
COHORT_DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "is_paid": {"type": "boolean"},
        "minimum_price_cents": {"type": "integer"},
        "max_seats": {"type": ["integer", "null"]},
        "dates": {
            "type": "object",
            "properties": {
                "enroll_start": {"type": "string"},
                "enroll_end": {"type": "string"},
                "cohort_start": {"type": "string"},
                "cohort_end": {"type": "string"},
            },
            "required": ["cohort_start", "cohort_end"]
        },
        "schedules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "survey_id": {"type": "string"},
                    "frequency": {"enum": ["ONCE", "DAILY", "WEEKLY"]},
                    "is_cumulative": {"type": "boolean"},
                    "task_title_template": {"type": "string"},
                    "task_description_template": {"type": "string"},
                    "day_of_week": {"type": "integer", "minimum": 0, "maximum": 6},
                    "offset_days": {"type": "integer"},
                    "offset_from": {"enum": ["ENROLL_START", "ENROLL_END", "COHORT_START", "COHORT_END"]}
                },
                "required": ["slug", "survey_id", "frequency"],
                "allOf": [
                    {
                        "if": {"properties": {"frequency": {"const": "WEEKLY"}}},
                        "then": {"required": ["day_of_week"]}
                    },
                    {
                        "if": {"properties": {"frequency": {"const": "ONCE"}}},
                        "then": {"required": ["offset_days", "offset_from"]}
                    }
                ]
            }
        },
        "surveys": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "title_template": {"type": "string"},
                    'estimated_time_minutes': {"type": "integer"},
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "questions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "key": {"type": "string"},
                                            "text": {"type": "string"},
                                            "type": {"enum": ["text", "textarea", "integer", "decimal", "radio", "info"]},
                                            "is_required": {"type": "boolean"},
                                            "choices": {"type": ["object", "null"]},
                                        },
                                        "required": ["key", "text", "type"]
                                    }
                                }
                            },
                            "required": ["title", "questions"]
                        }
                    },
                },
                "required": ["id", "name", "sections"]
            }
        }
    },
    "required": ["name", "dates", "surveys"]
}


def validate_cohort_design(data: dict) -> list[str]:
    """
    Validate a cohort design dict structure using JSON Schema.
    
    Args:
        data: The cohort design dictionary to validate.
        
    Returns:
        A list of error messages. Empty list if valid.
    """
    try:
        jsonschema.validate(instance=data, schema=COHORT_DESIGN_SCHEMA)
        return []
    except jsonschema.ValidationError as e:
        path = '/'.join(str(p) for p in e.path)
        return [f"{e.message} (at path: {path})"]


@transaction.atomic
def import_cohort_from_dict(
    data: dict,
    name_override: str | None = None,
    cohort_id: int | None = None,
    validate: bool = True,
) -> Cohort:
    """
    Create or update a cohort from a design dictionary.

    This creates/updates the Cohort, all referenced Surveys (with Questions),
    and all TaskSchedulers linking them together.

    Args:
        data: The cohort design dict (with dates, surveys, and schedules).
        name_override: Optional name to use instead of the one in data.
        cohort_id: If provided, update the existing cohort with this ID.
                   If None (default), create a new cohort.
        validate: If True (default), validate the dict structure before importing.

    Returns:
        The created or updated Cohort instance.

    Raises:
        ValueError: If validate=True and the dict structure is invalid.
        Cohort.DoesNotExist: If cohort_id is provided but no cohort exists with that ID.

    Behavior:
        When cohort_id is None (create mode):
            - Creates a new Cohort
            - Reuses existing Survey objects by slug (does not update them)
            - Creates new TaskSchedulers for the cohort

        When cohort_id is provided (update mode):
            - Updates the existing Cohort's fields
            - For Surveys: Updates existing surveys in the design, creates new ones,
              deletes surveys no longer in the design (only if not used by other cohorts)
            - For TaskSchedulers: Updates existing, creates new, deletes removed ones
            - For Questions: Deletes all old questions and recreates from the new design
    """
    if validate:
        errors = validate_cohort_design(data)
        if errors:
            raise ValueError(f"Invalid cohort design: {'; '.join(errors)}")

    if cohort_id is not None:
        return _update_existing_cohort(data, cohort_id, name_override)
    else:
        return _create_new_cohort(data, name_override)


def _create_new_cohort(data: dict, name_override: str | None = None) -> Cohort:
    """
    Create a new cohort from design data.

    Creates new Survey objects for this cohort (no sharing between cohorts).
    Survey slugs are generated as: {cohort_id}_{survey_internal_id}
    """
    dates = data["dates"]

    cohort = Cohort.objects.create(
        name=name_override or data.get("name", f"Cohort starting {dates['cohort_start']}"),
        enrollment_start_date=dates.get("enroll_start"),
        enrollment_end_date=dates.get("enroll_end"),
        start_date=dates["cohort_start"],
        end_date=dates["cohort_end"],
        is_paid=data.get("is_paid", False),
        minimum_price_cents=data.get("minimum_price_cents", 0),
        max_seats=data.get("max_seats"),
        is_active=True,
    )

    # Create surveys for this cohort (indexed by internal id)
    surveys = {}
    for survey_data in data.get("surveys", []):
        internal_id = survey_data["id"]
        survey = _create_survey_for_cohort(cohort, survey_data)
        surveys[internal_id] = survey

    # Create schedulers
    for schedule_data in data.get("schedules", []):
        _create_or_update_scheduler(cohort, surveys, schedule_data)

    # Set onboarding survey if specified
    cohort.onboarding_survey = surveys.get(data.get("onboarding_survey"))
    cohort.save()

    return cohort


def _update_existing_cohort(
    data: dict,
    cohort_id: int,
    name_override: str | None = None
) -> Cohort:
    """
    Update an existing cohort from design data.

    - Updates cohort fields
    - Updates/creates/deletes surveys as needed (matched by internal id)
    - Updates/creates/deletes schedulers as needed (matched by slug)
    """
    cohort = Cohort.objects.get(pk=cohort_id)
    dates = data["dates"]

    # Update cohort fields
    cohort.name = name_override or data.get("name", cohort.name)
    cohort.enrollment_start_date = dates.get("enroll_start")
    cohort.enrollment_end_date = dates.get("enroll_end")
    cohort.start_date = dates["cohort_start"]
    cohort.end_date = dates["cohort_end"]
    cohort.is_paid = data.get("is_paid", False)
    cohort.minimum_price_cents = data.get("minimum_price_cents", 0)
    cohort.max_seats = data.get("max_seats")

    # Track which survey internal IDs are in the new design
    new_survey_internal_ids = set()
    surveys = {}  # internal_id -> Survey

    for survey_data in data.get("surveys", []):
        internal_id = survey_data["id"]
        new_survey_internal_ids.add(internal_id)
        survey = _update_or_create_survey_for_cohort(cohort, survey_data)
        surveys[internal_id] = survey

    # Track which scheduler slugs we create/update
    new_scheduler_slugs = set()

    for schedule_data in data.get("schedules", []):
        scheduler = _create_or_update_scheduler(cohort, surveys, schedule_data)
        new_scheduler_slugs.add(scheduler.slug)

    # Delete schedulers that are no longer in the design
    _cleanup_removed_schedulers(cohort, new_scheduler_slugs)

    # Delete surveys that are no longer in the design (if safe)
    _cleanup_removed_surveys(cohort, new_survey_internal_ids)

    # Set onboarding survey if specified
    cohort.onboarding_survey = surveys.get(data.get("onboarding_survey"))
    cohort.save()

    return cohort


def _generate_survey_slug(cohort: Cohort, internal_id: str) -> str:
    """Generate a survey slug for a cohort-specific survey."""
    return f"{cohort.pk}_{internal_id}"


def _survey_metadata_changed(survey: Survey, survey_data: dict) -> bool:
    """Check if survey metadata (name, description, title_template) has changed."""
    return (
        survey.name != survey_data["name"] or
        survey.description != survey_data.get("description", "") or
        survey.title_template != survey_data.get("title_template", "{survey_name}") or
        survey.estimated_time_minutes != survey_data.get("estimated_time_minutes")
    )


def _questions_changed(survey: Survey, survey_data: dict) -> bool:
    """
    Check if questions have changed between existing survey and new design.

    Compares:
    - Set of question keys (additions/removals)
    - For matching keys: text, type, section, order, is_required, choices
    """
    # Build dict of new questions from design data
    new_questions = {}
    order = 0
    for section_data in survey_data.get("sections", []):
        section_title = section_data.get("title", "")
        for q in section_data.get("questions", []):
            new_questions[q["key"]] = {
                "text": q["text"],
                "question_type": q["type"],
                "section": section_title,
                "order": order,
                "is_required": q.get("is_required", True),
                "choices": q.get("choices"),
            }
            order += 1

    # Build dict of existing questions
    existing_questions = {
        q.key: {
            "text": q.text,
            "question_type": q.question_type,
            "section": q.section.title if q.section else "",
            "order": q.order,
            "is_required": q.is_required,
            "choices": q.choices,
        }
        for q in survey.questions.select_related('section').all()
    }

    # Compare keys first (additions/removals)
    if set(new_questions.keys()) != set(existing_questions.keys()):
        return True

    # Compare each question's fields
    for key, new_q in new_questions.items():
        existing_q = existing_questions[key]
        if new_q != existing_q:
            return True

    return False


def _create_survey_for_cohort(cohort: Cohort, survey_data: dict) -> Survey:
    """
    Create a new Survey for this cohort.

    Survey slug is generated as: {cohort_id}_{internal_id}
    """
    internal_id = survey_data["id"]
    slug = _generate_survey_slug(cohort, internal_id)

    survey = Survey.objects.create(
        slug=slug,
        name=survey_data["name"],
        description=survey_data.get("description", ""),
        title_template=survey_data.get("title_template", "{survey_name}"),
        estimated_time_minutes=survey_data.get("estimated_time_minutes"),
    )

    _create_questions_for_survey(survey, survey_data)
    return survey


def _update_or_create_survey_for_cohort(cohort: Cohort, survey_data: dict) -> Survey:
    """
    Update an existing survey or create a new one for this cohort.

    Surveys are matched by their generated slug: {cohort_id}_{internal_id}

    Update behavior:
    - Survey metadata (name, description, title_template) is always updated
    - Questions are recreated if they have changed AND survey has no submissions
    - If questions changed but survey has submissions, logs an error and skips question update
    """
    internal_id = survey_data["id"]
    slug = _generate_survey_slug(cohort, internal_id)
    existing = Survey.objects.filter(slug=slug).first()

    if existing:
        # Update survey metadata if changed
        if _survey_metadata_changed(existing, survey_data):
            existing.name = survey_data["name"]
            existing.description = survey_data.get("description", "")
            existing.title_template = survey_data.get("title_template", "{survey_name}")
            existing.estimated_time_minutes = survey_data.get("estimated_time_minutes")
            existing.save()

        # Recreate questions if they changed
        if _questions_changed(existing, survey_data):
            if SurveySubmission.objects.filter(survey=existing).exists():
                logger.error(
                    f"Cannot modify questions for survey '{existing.name}' (id: {internal_id}) "
                    f"because it has existing submissions. Questions left unchanged."
                )
            else:
                existing.questions.all().delete()
                existing.sections.all().delete()
                _create_questions_for_survey(existing, survey_data)

        return existing

    return _create_survey_for_cohort(cohort, survey_data)


def _create_questions_for_survey(survey: Survey, survey_data: dict) -> None:
    """
    Create questions for an existing survey from design data.
    """
    question_order = 0
    section_order = 0
    for section_data in survey_data.get("sections", []):
        section_title = section_data.get("title", "")
        
        section = SurveySection.objects.create(
            survey=survey,
            title=section_title,
            description=section_data.get("description", ""),
            order=section_order
        )
        section_order += 1

        for question_data in section_data.get("questions", []):
            Question.objects.create(
                survey=survey,
                key=question_data["key"],
                text=question_data["text"],
                question_type=question_data["type"],
                section=section,
                order=question_order,
                is_required=question_data.get("is_required", True),
                choices=question_data.get("choices"),
            )
            question_order += 1


def _create_or_update_scheduler(
    cohort: Cohort,
    surveys: dict[str, Survey],
    schedule_data: dict
) -> TaskScheduler:
    """
    Create or update a TaskScheduler linking a cohort to a survey.

    Args:
        cohort: The Cohort instance.
        surveys: Dictionary mapping survey internal IDs to Survey instances.
        schedule_data: Dictionary containing scheduler configuration.

    Returns:
        The created or updated TaskScheduler instance.
    """
    scheduler_slug = schedule_data["slug"]
    survey_internal_id = schedule_data["survey_id"]
    survey = surveys[survey_internal_id]

    scheduler, _ = TaskScheduler.objects.update_or_create(
        cohort=cohort,
        slug=scheduler_slug,
        defaults={
            "survey": survey,
            "frequency": schedule_data["frequency"],
            "is_cumulative": schedule_data.get("is_cumulative", False),
            "task_title_template": schedule_data.get("task_title_template", ""),
            "task_description_template": schedule_data.get("task_description_template", ""),
            "day_of_week": schedule_data.get("day_of_week"),
            "offset_days": schedule_data.get("offset_days"),
            "offset_from": schedule_data.get("offset_from"),
        }
    )
    return scheduler


def _cleanup_removed_schedulers(cohort: Cohort, kept_scheduler_slugs: set[str]) -> None:
    """
    Delete schedulers that are no longer in the design.

    Args:
        cohort: The cohort being updated.
        kept_scheduler_slugs: Set of scheduler slugs to keep.

    Note:
        Schedulers with existing UserSurveyResponse records will NOT be deleted
        to preserve historical data. A warning will be logged.
    """
    for scheduler in cohort.task_schedulers.all():
        if scheduler.slug not in kept_scheduler_slugs:
            # Check for existing responses
            if UserSurveyResponse.objects.filter(scheduler=scheduler).exists():
                # Don't delete - has user responses
                # In production, you might want to log this
                continue
            scheduler.delete()


def _cleanup_removed_surveys(cohort: Cohort, kept_survey_internal_ids: set[str]) -> None:
    """
    Delete surveys that are no longer in the design, if safe to do so.

    A survey is safe to delete if:
    1. It's not used by any TaskScheduler in OTHER cohorts
    2. It's not used as an onboarding survey for OTHER cohorts

    Args:
        cohort: The cohort being updated.
        kept_survey_internal_ids: Set of survey internal IDs that should be kept.
    """
    # Build the set of survey slugs that should be kept
    kept_survey_slugs = {
        _generate_survey_slug(cohort, internal_id)
        for internal_id in kept_survey_internal_ids
    }

    # Get survey IDs that were previously linked to this cohort
    previous_survey_ids = set(
        cohort.task_schedulers.values_list('survey_id', flat=True)
    )

    for survey_id in previous_survey_ids:
        survey = Survey.objects.filter(pk=survey_id).first()
        if not survey or survey.slug in kept_survey_slugs:
            continue

        # Check if survey is used by schedulers in OTHER cohorts
        other_cohort_schedulers = TaskScheduler.objects.filter(
            survey=survey
        ).exclude(cohort=cohort).exists()

        if other_cohort_schedulers:
            continue

        # Check if survey is used as onboarding survey in OTHER cohorts
        other_cohort_onboarding = Cohort.objects.filter(
            onboarding_survey=survey
        ).exclude(pk=cohort.pk).exists()

        if other_cohort_onboarding:
            continue

        # Safe to delete
        survey.delete()
