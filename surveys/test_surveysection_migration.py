from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Migration0012Test(TransactionTestCase):
    """
    Tests the data migration in 0012_surveysection_alter_question_section.
    Verifies that:
    1. SurveySections are created from unique 'section' strings.
    2. Questions are linked to the new SurveySections.
    3. If the first question in a section is 'info', it becomes the description.
    """
    
    # Define the migration states we are testing between
    migrate_from = [('surveys', '0011_survey_estimated_time_minutes')]
    migrate_to = [('surveys', '0012_surveysection_alter_question_section')]

    def setUp(self):
        # Initialize the migration executor
        executor = MigrationExecutor(connection)
        
        # Revert the database to the state before the migration we want to test
        # This ensures we have the schema as it was in 0011 (Question.section is a CharField)
        executor.migrate(self.migrate_from)
        
        # Get the historical versions of the models
        old_apps = executor.loader.project_state(self.migrate_from).apps
        Survey = old_apps.get_model('surveys', 'Survey')
        Question = old_apps.get_model('surveys', 'Question')
        
        # Create a survey
        self.survey = Survey.objects.create(name="Test Survey", slug="test-survey")
        
        # Scenario 1: Standard section with text questions
        # Section: "Basics"
        Question.objects.create(
            survey=self.survey,
            key="q1",
            text="What is your name?",
            question_type="text",
            section="Basics",
            order=1
        )
        
        # Scenario 2: Section starting with an INFO question
        # Section: "Context"
        # This info question should be converted to the section description
        Question.objects.create(
            survey=self.survey,
            key="context_intro",
            text="This section gathers context about your day.",
            question_type="info",
            section="Context",
            order=2
        )
        Question.objects.create(
            survey=self.survey,
            key="q2",
            text="How was your day?",
            question_type="text",
            section="Context",
            order=3
        )
        
        # Scenario 3: Section with INFO question that is NOT first
        # Section: "Outro"
        Question.objects.create(
            survey=self.survey,
            key="q3",
            text="Any final thoughts?",
            question_type="text",
            section="Outro",
            order=4
        )
        Question.objects.create(
            survey=self.survey,
            key="outro_info",
            text="Thanks for participating.",
            question_type="info",
            section="Outro",
            order=5
        )
        
        # Scenario 4: Section starting with TWO INFO questions
        # Section: "DoubleInfo"
        # The first info question should be converted to description.
        # The second info question should remain as a question.
        Question.objects.create(
            survey=self.survey,
            key="di_1",
            text="Info 1",
            question_type="info",
            section="DoubleInfo",
            order=6
        )
        Question.objects.create(
            survey=self.survey,
            key="di_2",
            text="Info 2",
            question_type="info",
            section="DoubleInfo",
            order=7
        )
        Question.objects.create(
            survey=self.survey,
            key="di_3",
            text="Actual Question",
            question_type="text",
            section="DoubleInfo",
            order=8
        )

    def test_standard_scenarios(self):
        # Run the migration to 0012
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # Reload the graph to ensure it's up to date
        executor.migrate(self.migrate_to)
        
        # Get the models as they exist after the migration
        new_apps = executor.loader.project_state(self.migrate_to).apps
        SurveySection = new_apps.get_model('surveys', 'SurveySection')
        Question = new_apps.get_model('surveys', 'Question')
        
        # --- Assertions ---
        
        # 1. Check "Basics" section
        # Should exist, have no description, and contain q1
        basics_section = SurveySection.objects.get(title="Basics", survey__slug="test-survey")
        self.assertEqual(basics_section.description, "")
        self.assertEqual(basics_section.questions.count(), 1)
        self.assertEqual(basics_section.questions.first().key, "q1")
        
        # 2. Check "Context" section
        # Should exist, have description from the info question, and contain q2. 
        # The info question should be deleted.
        context_section = SurveySection.objects.get(title="Context", survey__slug="test-survey")
        self.assertEqual(context_section.description, "This section gathers context about your day.")
        self.assertEqual(context_section.questions.count(), 1)
        self.assertEqual(context_section.questions.first().key, "q2")
        self.assertFalse(Question.objects.filter(key="context_intro").exists())

    def test_two_info_questions(self):
        # Run the migration to 0012
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # Reload the graph to ensure it's up to date
        executor.migrate(self.migrate_to)
        
        # Get the models as they exist after the migration
        new_apps = executor.loader.project_state(self.migrate_to).apps
        SurveySection = new_apps.get_model('surveys', 'SurveySection')
        Question = new_apps.get_model('surveys', 'Question')
        
        # 3. Check "Outro" section
        # Should exist, have no description (first q was not info).
        # Should contain both q3 and outro_info (since outro_info was not first).
        outro_section = SurveySection.objects.get(title="Outro", survey__slug="test-survey")
        self.assertEqual(outro_section.description, "")
        self.assertEqual(outro_section.questions.count(), 2)
        self.assertTrue(Question.objects.filter(key="outro_info").exists())
        self.assertEqual(Question.objects.get(key="outro_info").section.id, outro_section.id)
        
        # 4. Check "DoubleInfo" section
        double_info_section = SurveySection.objects.get(title="DoubleInfo", survey__slug="test-survey")
        self.assertEqual(double_info_section.description, "Info 1<br><br>Info 2")
        # Should contain di_2 and di_3. di_1 is deleted.
        self.assertEqual(double_info_section.questions.count(), 1)
        self.assertTrue(Question.objects.filter(key="di_3").exists())
        # Verify di_2 is the first question in the section now
        self.assertEqual(double_info_section.questions.order_by('order').first().key, "di_3")
