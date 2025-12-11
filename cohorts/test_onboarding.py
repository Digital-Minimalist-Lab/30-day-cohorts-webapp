"""
Tests for the onboarding flow.

Tests the complete flow:
1. User signs up
2. User is redirected to entry survey
3. User completes entry survey
4. User is redirected to checkout
5. User completes checkout (payment or free)
6. User is redirected to success page
"""
from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from cohorts.models import Cohort, Enrollment, UserSurveyResponse
from surveys.models import Survey, SurveySubmission, Question

User = get_user_model()


class OnboardingFlowTests(TestCase):
    """Test the complete onboarding flow with entry survey."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create a cohort
        self.cohort = Cohort.objects.create(
            name='Test Cohort',
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=37),
            minimum_price_cents=0,
            is_paid=False,  # Free cohort for testing
            max_seats=10,
        )

        # Get or create entry survey (it may already exist from migrations)
        self.entry_survey, created = Survey.objects.get_or_create(
            slug='entry-survey',
            defaults={
                'name': 'Entry Survey',
                'purpose': Survey.Purpose.ENTRY,
                'description': 'Baseline survey'
            }
        )

        # Add questions to the survey if they don't exist
        Question.objects.get_or_create(
            survey=self.entry_survey,
            key='mood_1to5',
            defaults={
                'text': 'How do you feel? (1-5)',
                'question_type': Question.QuestionType.INTEGER,
                'order': 1,
            }
        )
        Question.objects.get_or_create(
            survey=self.entry_survey,
            key='baseline_screentime_min',
            defaults={
                'text': 'Average daily smartphone usage (minutes)',
                'question_type': Question.QuestionType.INTEGER,
                'order': 2,
            }
        )
        Question.objects.get_or_create(
            survey=self.entry_survey,
            key='intention_text',
            defaults={
                'text': 'Why are you interested in participating?',
                'question_type': Question.QuestionType.TEXTAREA,
                'order': 3,
            }
        )

    def test_join_start_redirects_to_entry_survey_for_authenticated_user(self):
        """Test that authenticated users are redirected to entry survey."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
        )
        self.client.force_login(user)
        
        response = self.client.get(reverse('cohorts:join_start'))
        
        # Should redirect to entry survey
        self.assertEqual(response.status_code, 302)
        self.assertIn('join/entry-survey', response['Location'])

    def test_join_entry_survey_creates_pending_enrollment(self):
        """Test that accessing entry survey creates a pending enrollment."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
        )
        self.client.force_login(user)
        
        response = self.client.get(reverse('cohorts:join_entry_survey'))
        
        # Should create pending enrollment
        enrollment = Enrollment.objects.filter(user=user, cohort=self.cohort).first()
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment.status, 'pending')
        
        # Should redirect to the entry survey form
        self.assertEqual(response.status_code, 302)
        self.assertIn('entry-survey', response['Location'])

    def test_entry_survey_completion_redirects_to_checkout(self):
        """Test that completing entry survey redirects to checkout."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
        )
        self.client.force_login(user)
        
        # Create enrollment
        Enrollment.objects.create(
            user=user,
            cohort=self.cohort,
            status='pending'
        )
        
        # Submit entry survey
        survey_url = reverse('cohorts:onboarding_entry_survey', kwargs={
            'cohort_id': self.cohort.id,
            'survey_slug': self.entry_survey.slug,
            'due_date': self.cohort.start_date.isoformat()
        })
        
        response = self.client.post(survey_url, {
            'mood_1to5': '4',
            'baseline_screentime_min': '180',
            'intention_text': 'I want to reduce my screen time',
        })
        
        # Should redirect to checkout
        self.assertEqual(response.status_code, 302)
        self.assertIn('checkout', response['Location'])
        
        # Should have created a survey submission
        self.assertTrue(
            UserSurveyResponse.objects.filter(
                user=user,
                cohort=self.cohort,
                submission__survey=self.entry_survey
            ).exists()
        )

    def test_join_entry_survey_skips_if_already_completed(self):
        """Test that users who already completed entry survey skip to checkout."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
        )
        self.client.force_login(user)
        
        # Create enrollment
        enrollment = Enrollment.objects.create(
            user=user,
            cohort=self.cohort,
            status='pending'
        )
        
        # Create a completed entry survey
        submission = SurveySubmission.objects.create(survey=self.entry_survey)
        UserSurveyResponse.objects.create(
            user=user,
            cohort=self.cohort,
            submission=submission,
            due_date=self.cohort.start_date
        )
        
        # Try to access entry survey
        response = self.client.get(reverse('cohorts:join_entry_survey'))
        
        # Should skip to checkout
        self.assertEqual(response.status_code, 302)
        self.assertIn('checkout', response['Location'])

    def test_free_cohort_completes_enrollment_after_entry_survey(self):
        """Test that free cohort enrollment completes after entry survey and checkout."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
        )
        self.client.force_login(user)

        # Go through entry survey flow
        self.client.get(reverse('cohorts:join_entry_survey'))

        # Complete entry survey
        survey_url = reverse('cohorts:onboarding_entry_survey', kwargs={
            'cohort_id': self.cohort.id,
            'survey_slug': self.entry_survey.slug,
            'due_date': self.cohort.start_date.isoformat()
        })
        self.client.post(survey_url, {
            'mood_1to5': '4',
            'baseline_screentime_min': '180',
            'intention_text': 'I want to reduce my screen time',
        })

        # Access checkout (should auto-complete for free cohort)
        response = self.client.get(reverse('cohorts:join_checkout'))

        # Should redirect to success
        self.assertEqual(response.status_code, 302)
        self.assertIn('success', response['Location'])

        # Enrollment should be marked as 'free'
        enrollment = Enrollment.objects.get(user=user, cohort=self.cohort)
        self.assertEqual(enrollment.status, 'free')

    def test_paid_cohort_rejects_amount_below_minimum(self):
        """Test that checkout rejects payment amounts below the minimum price."""
        # Delete the free cohort so the paid cohort is the only joinable one
        self.cohort.delete()

        # Create a paid cohort with minimum price
        paid_cohort = Cohort.objects.create(
            name='Paid Cohort',
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=37),
            minimum_price_cents=2000,  # $20 minimum
            is_paid=True,
            max_seats=10,
        )

        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
        )
        self.client.force_login(user)

        # Create enrollment
        Enrollment.objects.create(
            user=user,
            cohort=paid_cohort,
            status='pending'
        )

        # Try to submit amount below minimum ($15 when minimum is $20)
        response = self.client.post(reverse('cohorts:join_checkout'), {
            'amount': '15.00',
        })

        # Should not redirect (form should show errors)
        self.assertEqual(response.status_code, 200)

        # Should show form with validation error
        self.assertContains(response, 'Minimum amount is $20.00')

        # Enrollment should still be pending (not paid)
        enrollment = Enrollment.objects.get(user=user, cohort=paid_cohort)
        self.assertEqual(enrollment.status, 'pending')

    def test_paid_cohort_accepts_amount_at_minimum(self):
        """Test that checkout accepts payment at exactly the minimum price."""
        # Delete the free cohort so the paid cohort is the only joinable one
        self.cohort.delete()

        # Create a paid cohort with minimum price
        paid_cohort = Cohort.objects.create(
            name='Paid Cohort',
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=37),
            minimum_price_cents=2000,  # $20 minimum
            is_paid=True,
            max_seats=10,
        )

        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
        )
        self.client.force_login(user)

        # Create enrollment
        Enrollment.objects.create(
            user=user,
            cohort=paid_cohort,
            status='pending'
        )

        # Submit amount at minimum ($20)
        response = self.client.post(reverse('cohorts:join_checkout'), {
            'amount': '20.00',
        })

        # Should redirect to Stripe checkout
        self.assertEqual(response.status_code, 302)
        self.assertIn('payments/create-checkout', response['Location'])
        self.assertIn('amount=2000', response['Location'])
        enrollment = Enrollment.objects.get(user=user, cohort=paid_cohort)
        self.assertEqual(enrollment.status, 'pending')

    def test_paid_cohort_accepts_amount_above_minimum(self):
        """Test that checkout accepts payment amounts above the minimum price."""
        # Delete the free cohort so the paid cohort is the only joinable one
        self.cohort.delete()

        # Create a paid cohort with minimum price
        paid_cohort = Cohort.objects.create(
            name='Paid Cohort',
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=37),
            minimum_price_cents=2000,  # $20 minimum
            is_paid=True,
            max_seats=10,
        )

        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
        )
        self.client.force_login(user)

        # Create enrollment
        Enrollment.objects.create(
            user=user,
            cohort=paid_cohort,
            status='pending'
        )

        # Submit amount above minimum ($50)
        response = self.client.post(reverse('cohorts:join_checkout'), {
            'amount': '50.00',
        })

        # Should redirect to Stripe checkout
        self.assertEqual(response.status_code, 302)
        self.assertIn('payments/create-checkout', response['Location'])
        self.assertIn('amount=5000', response['Location'])
        enrollment = Enrollment.objects.get(user=user, cohort=paid_cohort)
        self.assertEqual(enrollment.status, 'pending')


    def test_paid_cohort_but_free_accepts_amount_above_minimum(self):
        """Test that checkout accepts payment amounts above the minimum price."""
        # Delete the free cohort so the paid cohort is the only joinable one
        self.cohort.delete()

        # Create a paid cohort with minimum price
        paid_cohort = Cohort.objects.create(
            name='Paid Cohort',
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=37),
            minimum_price_cents=0,  # $0 minimum
            is_paid=True,
            max_seats=10,
        )

        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
        )
        self.client.force_login(user)

        # Create enrollment
        Enrollment.objects.create(
            user=user,
            cohort=paid_cohort,
            status='pending'
        )

        # Submit amount above minimum ($50)
        response = self.client.post(reverse('cohorts:join_checkout'), {
            'amount': '0.00',
        })

        # Should redirect to Stripe checkout
        self.assertEqual(response.status_code, 302)
        self.assertIn('success', response['Location'])
        enrollment = Enrollment.objects.get(user=user, cohort=paid_cohort)
        self.assertEqual(enrollment.status, 'paid')
        self.assertEqual(enrollment.amount_paid_cents, 0)

