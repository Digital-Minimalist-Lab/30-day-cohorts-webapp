"""Tests for cohorts/services/cohort_import.py"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from cohorts.models import Cohort, TaskScheduler, UserSurveyResponse
from cohorts.services.cohort_import import (
    validate_cohort_design,
    import_cohort_from_dict,
    _questions_changed,
    _survey_metadata_changed,
)
from surveys.models import Survey, Question, SurveySubmission

User = get_user_model()


def make_cohort_design(
    name="Test Cohort",
    cohort_start="2025-01-01",
    cohort_end="2025-01-31",
    surveys=None,
    schedules=None,
):
    """Helper to create a valid cohort design dict."""
    if surveys is None:
        surveys = [
            {
                "id": "test-survey",
                "name": "Test Survey",
                "description": "A test survey",
                "title_template": "{survey_name}",
                "sections": [
                    {
                        "title": "Section 1",
                        "questions": [
                            {"key": "q1", "text": "Question 1", "type": "text"},
                            {"key": "q2", "text": "Question 2", "type": "radio", "choices": {"a": "A", "b": "B"}},
                        ]
                    }
                ]
            }
        ]
    if schedules is None:
        schedules = [
            {"slug": "test-survey", "survey_id": "test-survey", "frequency": "ONCE", "offset_days": 0, "offset_from": "COHORT_START"}
        ]

    return {
        "name": name,
        "dates": {
            "cohort_start": cohort_start,
            "cohort_end": cohort_end,
        },
        "surveys": surveys,
        "schedules": schedules,
    }


class ValidateCohortDesignTests(TestCase):
    """Tests for validate_cohort_design()"""

    def test_valid_design_returns_empty_list(self):
        data = make_cohort_design()
        errors = validate_cohort_design(data)
        self.assertEqual(errors, [])

    def test_missing_name_returns_error(self):
        data = make_cohort_design()
        del data["name"]
        errors = validate_cohort_design(data)
        self.assertEqual(len(errors), 1)
        self.assertIn("name", errors[0].lower())

    def test_missing_dates_returns_error(self):
        data = make_cohort_design()
        del data["dates"]
        errors = validate_cohort_design(data)
        self.assertEqual(len(errors), 1)

    def test_missing_surveys_returns_error(self):
        data = make_cohort_design()
        del data["surveys"]
        errors = validate_cohort_design(data)
        self.assertEqual(len(errors), 1)


class ChangeDetectionTests(TestCase):
    """Tests for _survey_metadata_changed and _questions_changed helpers."""

    def setUp(self):
        self.survey = Survey.objects.create(
            slug="test-survey",
            name="Test Survey",
            description="Test description",
            title_template="{survey_name}",
        )
        Question.objects.create(
            survey=self.survey, key="q1", text="Question 1",
            question_type="text", section="Section 1", order=0,
            is_required=True, choices=None
        )

    def test_survey_metadata_unchanged(self):
        survey_data = {
            "id": "test",
            "name": "Test Survey",
            "description": "Test description",
            "title_template": "{survey_name}",
            "sections": []
        }
        self.assertFalse(_survey_metadata_changed(self.survey, survey_data))

    def test_survey_metadata_changed_name(self):
        survey_data = {
            "id": "test",
            "name": "Different Name",
            "description": "Test description",
            "title_template": "{survey_name}",
            "sections": []
        }
        self.assertTrue(_survey_metadata_changed(self.survey, survey_data))

    def test_questions_unchanged(self):
        survey_data = {
            "id": "test",
            "name": "Test Survey",
            "sections": [{
                "title": "Section 1",
                "questions": [
                    {"key": "q1", "text": "Question 1", "type": "text", "is_required": True}
                ]
            }]
        }
        self.assertFalse(_questions_changed(self.survey, survey_data))

    def test_questions_changed_new_question(self):
        survey_data = {
            "id": "test",
            "name": "Test Survey",
            "sections": [{
                "title": "Section 1",
                "questions": [
                    {"key": "q1", "text": "Question 1", "type": "text"},
                    {"key": "q2", "text": "Question 2", "type": "text"},  # New question
                ]
            }]
        }
        self.assertTrue(_questions_changed(self.survey, survey_data))

    def test_questions_changed_removed_question(self):
        survey_data = {
            "id": "test",
            "name": "Test Survey",
            "sections": []  # No questions
        }
        self.assertTrue(_questions_changed(self.survey, survey_data))

    def test_questions_changed_text_modified(self):
        survey_data = {
            "id": "test",
            "name": "Test Survey",
            "sections": [{
                "title": "Section 1",
                "questions": [
                    {"key": "q1", "text": "Different text", "type": "text", "is_required": True}
                ]
            }]
        }
        self.assertTrue(_questions_changed(self.survey, survey_data))

    def test_questions_changed_type_modified(self):
        survey_data = {
            "id": "test",
            "name": "Test Survey",
            "sections": [{
                "title": "Section 1",
                "questions": [
                    {"key": "q1", "text": "Question 1", "type": "textarea", "is_required": True}  # Changed type
                ]
            }]
        }
        self.assertTrue(_questions_changed(self.survey, survey_data))


class CreateCohortTests(TestCase):
    """Tests for import_cohort_from_dict() in create mode (cohort_id=None)"""

    def test_creates_cohort_with_correct_fields(self):
        data = make_cohort_design(name="My Cohort", cohort_start="2025-02-01", cohort_end="2025-02-28")
        cohort = import_cohort_from_dict(data)

        self.assertEqual(cohort.name, "My Cohort")
        self.assertEqual(str(cohort.start_date), "2025-02-01")
        self.assertEqual(str(cohort.end_date), "2025-02-28")
        self.assertTrue(cohort.is_active)

    def test_name_override(self):
        data = make_cohort_design(name="Original Name")
        cohort = import_cohort_from_dict(data, name_override="Override Name")
        self.assertEqual(cohort.name, "Override Name")

    def test_creates_survey_and_questions(self):
        data = make_cohort_design()
        cohort = import_cohort_from_dict(data)

        # Survey slug is generated as {cohort_id}_{internal_id}
        expected_slug = f"{cohort.pk}_test-survey"
        survey = Survey.objects.get(slug=expected_slug)
        self.assertEqual(survey.name, "Test Survey")
        self.assertEqual(survey.questions.count(), 2)

        q1 = survey.questions.get(key="q1")
        self.assertEqual(q1.text, "Question 1")
        self.assertEqual(q1.question_type, "text")

    def test_creates_scheduler(self):
        data = make_cohort_design()
        cohort = import_cohort_from_dict(data)

        self.assertEqual(cohort.task_schedulers.count(), 1)
        scheduler = cohort.task_schedulers.first()
        self.assertEqual(scheduler.slug, "test-survey")
        self.assertEqual(scheduler.frequency, TaskScheduler.Frequency.ONCE)

    def test_creates_cohort_specific_survey(self):
        """Each cohort gets its own surveys (no sharing between cohorts)."""
        data = make_cohort_design(name="Cohort 1")
        cohort1 = import_cohort_from_dict(data)

        data2 = make_cohort_design(name="Cohort 2")
        cohort2 = import_cohort_from_dict(data2)

        # Should have 2 surveys with different slugs
        self.assertEqual(Survey.objects.count(), 2)
        self.assertTrue(Survey.objects.filter(slug=f"{cohort1.pk}_test-survey").exists())
        self.assertTrue(Survey.objects.filter(slug=f"{cohort2.pk}_test-survey").exists())

    def test_creates_new_survey(self):
        data = make_cohort_design()
        self.assertEqual(Survey.objects.count(), 0)

        cohort = import_cohort_from_dict(data)

        self.assertEqual(Survey.objects.count(), 1)
        # Slug format is {cohort_id}_{internal_id}
        self.assertEqual(Survey.objects.first().slug, f"{cohort.pk}_test-survey")


class UpdateCohortTests(TestCase):
    """Tests for import_cohort_from_dict() in update mode (cohort_id provided)"""

    def setUp(self):
        """Create an existing cohort with survey and scheduler."""
        self.cohort = Cohort.objects.create(
            name="Original Cohort",
            start_date="2025-01-01",
            end_date="2025-01-31",
        )
        # Survey slug matches the expected format: {cohort_id}_{internal_id}
        self.survey = Survey.objects.create(
            slug=f"{self.cohort.pk}_original",
            name="Original Survey",
            description="Original description",
        )
        Question.objects.create(
            survey=self.survey, key="orig_q1", text="Original Q1",
            question_type="text", section="Section 1", order=0, is_required=True
        )
        self.scheduler = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            slug="original-scheduler",
            frequency=TaskScheduler.Frequency.ONCE,
            offset_days=0,
            offset_from=TaskScheduler.OffsetFrom.COHORT_START,
        )

    def test_updates_cohort_fields(self):
        data = make_cohort_design(
            name="Updated Cohort",
            cohort_start="2025-03-01",
            cohort_end="2025-03-31",
            surveys=[{
                "id": "original",
                "name": "Original Survey",
                "sections": [{"title": "S1", "questions": [{"key": "q1", "text": "Q1", "type": "text"}]}]
            }],
            schedules=[{"slug": "original-scheduler", "survey_id": "original", "frequency": "ONCE", "offset_days": 0, "offset_from": "COHORT_START"}]
        )

        cohort = import_cohort_from_dict(data, cohort_id=self.cohort.pk)

        self.assertEqual(cohort.pk, self.cohort.pk)
        self.assertEqual(cohort.name, "Updated Cohort")
        self.assertEqual(str(cohort.start_date), "2025-03-01")
        self.assertEqual(str(cohort.end_date), "2025-03-31")

    def test_updates_existing_survey_and_recreates_questions(self):
        """In update mode, existing surveys should be updated and questions recreated."""
        data = make_cohort_design(
            surveys=[{
                "id": "original",
                "name": "Updated Survey Name",
                "description": "Updated description",
                "sections": [
                    {"title": "New Section", "questions": [
                        {"key": "new_q1", "text": "New Question 1", "type": "textarea"},
                        {"key": "new_q2", "text": "New Question 2", "type": "integer"},
                    ]}
                ]
            }],
            schedules=[{"slug": "original-scheduler", "survey_id": "original", "frequency": "ONCE", "offset_days": 0, "offset_from": "COHORT_START"}]
        )

        cohort = import_cohort_from_dict(data, cohort_id=self.cohort.pk)

        # Survey should be updated (matched by cohort_id + internal_id)
        survey = Survey.objects.get(slug=f"{cohort.pk}_original")
        self.assertEqual(survey.name, "Updated Survey Name")
        self.assertEqual(survey.description, "Updated description")

        # Questions should be recreated
        self.assertEqual(survey.questions.count(), 2)
        self.assertTrue(survey.questions.filter(key="new_q1").exists())
        self.assertTrue(survey.questions.filter(key="new_q2").exists())
        self.assertFalse(survey.questions.filter(key="orig_q1").exists())

    def test_logs_error_and_skips_questions_if_changed_with_submissions(self):
        """Should log error and skip question update if questions changed but survey has submissions."""
        # Create a submission for the survey
        SurveySubmission.objects.create(survey=self.survey)

        data = make_cohort_design(
            surveys=[{
                "id": "original",
                "name": "Updated Survey Name",
                "description": "Updated description",
                "sections": [
                    {"title": "New Section", "questions": [
                        {"key": "new_q1", "text": "New Question 1", "type": "textarea"},
                    ]}
                ]
            }],
            schedules=[{"slug": "original-scheduler", "survey_id": "original", "frequency": "ONCE", "offset_days": 0, "offset_from": "COHORT_START"}]
        )

        with self.assertLogs('cohorts.services.cohort_import', level='ERROR') as log:
            cohort = import_cohort_from_dict(data, cohort_id=self.cohort.pk)

        # Should log an error about submissions
        self.assertTrue(any('existing submissions' in msg for msg in log.output))

        # Metadata should still be updated
        survey = Survey.objects.get(slug=f"{cohort.pk}_original")
        self.assertEqual(survey.name, "Updated Survey Name")

        # But questions should be unchanged (original preserved)
        self.assertEqual(survey.questions.count(), 1)
        self.assertTrue(survey.questions.filter(key="orig_q1").exists())
        self.assertFalse(survey.questions.filter(key="new_q1").exists())

    def test_allows_metadata_update_with_submissions_if_questions_unchanged(self):
        """Should allow updating survey metadata even with submissions, if questions are unchanged."""
        # Create a submission for the survey
        SurveySubmission.objects.create(survey=self.survey)

        # Same questions, just different metadata
        data = make_cohort_design(
            surveys=[{
                "id": "original",
                "name": "Updated Survey Name",  # Changed
                "description": "Updated description",  # Changed
                "sections": [
                    {"title": "Section 1", "questions": [
                        {"key": "orig_q1", "text": "Original Q1", "type": "text", "is_required": True},  # Same
                    ]}
                ]
            }],
            schedules=[{"slug": "original-scheduler", "survey_id": "original", "frequency": "ONCE", "offset_days": 0, "offset_from": "COHORT_START"}]
        )

        # Should NOT raise - questions are unchanged
        cohort = import_cohort_from_dict(data, cohort_id=self.cohort.pk)

        # Metadata should be updated
        survey = Survey.objects.get(slug=f"{cohort.pk}_original")
        self.assertEqual(survey.name, "Updated Survey Name")
        self.assertEqual(survey.description, "Updated description")

    def test_creates_new_survey_in_update_mode(self):
        """New surveys in the design should be created."""
        data = make_cohort_design(
            surveys=[
                {
                    "id": "original",
                    "name": "Original Survey",
                    "sections": [{"title": "S1", "questions": [{"key": "q1", "text": "Q1", "type": "text"}]}]
                },
                {
                    "id": "new-survey",
                    "name": "New Survey",
                    "sections": [{"title": "S1", "questions": [{"key": "nq1", "text": "NQ1", "type": "text"}]}]
                }
            ],
            schedules=[
                {"slug": "original-scheduler", "survey_id": "original", "frequency": "ONCE", "offset_days": 0, "offset_from": "COHORT_START"},
                {"slug": "new-scheduler", "survey_id": "new-survey", "frequency": "DAILY"},
            ]
        )

        cohort = import_cohort_from_dict(data, cohort_id=self.cohort.pk)

        self.assertEqual(Survey.objects.count(), 2)
        self.assertTrue(Survey.objects.filter(slug=f"{cohort.pk}_new-survey").exists())

    def test_deletes_removed_scheduler(self):
        """Schedulers not in the new design should be deleted."""
        # Create a second scheduler that will be removed
        survey2 = Survey.objects.create(slug=f"{self.cohort.pk}_to-remove", name="To Remove")
        scheduler2 = TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=survey2,
            slug="to-remove-scheduler",
            frequency=TaskScheduler.Frequency.DAILY,
        )

        # New design only has original survey/scheduler
        data = make_cohort_design(
            surveys=[{
                "id": "original",
                "name": "Original Survey",
                "sections": [{"title": "S1", "questions": [{"key": "q1", "text": "Q1", "type": "text"}]}]
            }],
            schedules=[{"slug": "original-scheduler", "survey_id": "original", "frequency": "ONCE", "offset_days": 0, "offset_from": "COHORT_START"}]
        )

        cohort = import_cohort_from_dict(data, cohort_id=self.cohort.pk)

        self.assertEqual(cohort.task_schedulers.count(), 1)
        self.assertFalse(TaskScheduler.objects.filter(pk=scheduler2.pk).exists())

    def test_does_not_delete_scheduler_with_responses(self):
        """Schedulers with user responses should NOT be deleted."""
        user = User.objects.create_user(username="testuser", email="test@example.com", password="test")
        submission = SurveySubmission.objects.create(survey=self.survey)
        UserSurveyResponse.objects.create(
            submission=submission,
            user=user,
            cohort=self.cohort,
            scheduler=self.scheduler,
            task_instance_id=0,
        )

        # New design has no schedules (would normally delete all)
        # Questions must match exactly to avoid SurveyHasSubmissionsError
        data = make_cohort_design(
            surveys=[{
                "id": "original",
                "name": "Original Survey",
                "sections": [{"title": "Section 1", "questions": [
                    {"key": "orig_q1", "text": "Original Q1", "type": "text", "is_required": True}
                ]}]
            }],
            schedules=[]  # Empty - would delete scheduler
        )

        cohort = import_cohort_from_dict(data, cohort_id=self.cohort.pk)

        # Scheduler should still exist because it has responses
        self.assertTrue(TaskScheduler.objects.filter(pk=self.scheduler.pk).exists())

    def test_raises_error_for_nonexistent_cohort_id(self):
        data = make_cohort_design()

        with self.assertRaises(Cohort.DoesNotExist):
            import_cohort_from_dict(data, cohort_id=99999)


class SurveyCleanupTests(TestCase):
    """Tests for survey cleanup safety when updating cohorts."""

    def setUp(self):
        """Create cohort with survey."""
        self.cohort = Cohort.objects.create(
            name="Cohort 1",
            start_date="2025-01-01",
            end_date="2025-01-31",
        )
        # Use a shared survey slug (not cohort-specific) to simulate legacy/shared surveys
        self.survey = Survey.objects.create(slug="shared-survey", name="Shared Survey")
        Question.objects.create(survey=self.survey, key="q1", text="Q1", question_type="text", order=0)
        TaskScheduler.objects.create(
            cohort=self.cohort,
            survey=self.survey,
            slug="shared-scheduler",
            frequency=TaskScheduler.Frequency.ONCE,
            offset_days=0,
            offset_from=TaskScheduler.OffsetFrom.COHORT_START,
        )

    def test_does_not_delete_survey_used_by_other_cohort(self):
        """Surveys used by other cohorts should NOT be deleted."""
        # Create another cohort using the same survey
        other_cohort = Cohort.objects.create(
            name="Other Cohort",
            start_date="2025-02-01",
            end_date="2025-02-28",
        )
        TaskScheduler.objects.create(
            cohort=other_cohort,
            survey=self.survey,
            slug="other-scheduler",
            frequency=TaskScheduler.Frequency.DAILY,
        )

        # Update first cohort with a different survey
        data = make_cohort_design(
            surveys=[{
                "id": "new-survey",
                "name": "New Survey",
                "sections": [{"title": "S1", "questions": [{"key": "q1", "text": "Q1", "type": "text"}]}]
            }],
            schedules=[{"slug": "new-scheduler", "survey_id": "new-survey", "frequency": "ONCE", "offset_days": 0, "offset_from": "COHORT_START"}]
        )

        import_cohort_from_dict(data, cohort_id=self.cohort.pk)

        # shared-survey should still exist (used by other_cohort)
        self.assertTrue(Survey.objects.filter(slug="shared-survey").exists())

    def test_does_not_delete_survey_used_as_onboarding_by_other_cohort(self):
        """Surveys used as onboarding by other cohorts should NOT be deleted."""
        other_cohort = Cohort.objects.create(
            name="Other Cohort",
            start_date="2025-02-01",
            end_date="2025-02-28",
            onboarding_survey=self.survey,  # Using our survey as onboarding
        )

        # Update first cohort with a different survey
        data = make_cohort_design(
            surveys=[{
                "id": "new-survey",
                "name": "New Survey",
                "sections": [{"title": "S1", "questions": [{"key": "q1", "text": "Q1", "type": "text"}]}]
            }],
            schedules=[{"slug": "new-scheduler", "survey_id": "new-survey", "frequency": "ONCE", "offset_days": 0, "offset_from": "COHORT_START"}]
        )

        import_cohort_from_dict(data, cohort_id=self.cohort.pk)

        # shared-survey should still exist (used as onboarding by other_cohort)
        self.assertTrue(Survey.objects.filter(slug="shared-survey").exists())

