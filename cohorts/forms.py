from typing import Any, Dict, Optional
from django import forms
from django.core.validators import MinValueValidator
from allauth.account.forms import SignupForm
import pytz
from .models import Cohort
from accounts.models import UserProfile


class CohortForm(forms.ModelForm):
    """Form for creating and updating cohorts."""
    class Meta:
        model = Cohort
        fields = ['name', 'start_date', 'end_date', 'minimum_price_cents', 'is_paid', 'max_seats', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g., January 2024 Cohort'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date'
            }),
            'minimum_price_cents': forms.NumberInput(attrs={
                'placeholder': 'Minimum price in cents (e.g., 1000 = $10.00)'
            }),
            'is_paid': forms.CheckboxInput(),
            'max_seats': forms.NumberInput(attrs={
                'placeholder': 'Leave blank for unlimited'
            }),
            'is_active': forms.CheckboxInput(),
        }
        help_texts = {
            'minimum_price_cents': 'Minimum price in cents (e.g., 1000 = $10.00)',
            'is_paid': 'Whether this cohort requires payment',
            'max_seats': 'Maximum number of seats (leave blank for unlimited)',
            'is_active': 'Whether this cohort is currently accepting enrollments',
        }
    
    def clean(self) -> Optional[Dict[str, Any]]:
        """Validate that end_date is after start_date."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise forms.ValidationError(
                    'End date must be after start date.'
                )
        
        return cleaned_data


class EnrollmentSignupForm(SignupForm):
    """Extended signup form with timezone and email preferences."""
    timezone = forms.ChoiceField(
        choices=[(tz, tz) for tz in pytz.common_timezones],
        initial='America/New_York',
        required=True,
        help_text="Your timezone for accurate daily check-in dates"
    )
    email_daily_reminder = forms.BooleanField(
        required=False,
        initial=False,
        label="Send me daily check-in reminders",
        help_text="Optional email reminders for daily reflections"
    )
    email_weekly_reminder = forms.BooleanField(
        required=False,
        initial=False,
        label="Send me weekly reflection reminders",
        help_text="Optional email reminders for weekly intentions"
    )

    def save(self, request):
        """Save the user and create associated UserProfile."""
        user = super().save(request)
        
        # Create or update UserProfile with timezone and email preferences
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'timezone': self.cleaned_data['timezone'],
                'email_daily_reminder': self.cleaned_data['email_daily_reminder'],
                'email_weekly_reminder': self.cleaned_data['email_weekly_reminder'],
            }
        )
        
        return user


class PaymentAmountForm(forms.Form):
    """Form for selecting payment amount (pay-what-you-want)."""
    amount_cents = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'placeholder': 'Enter amount in dollars',
            'step': '1',
            'min': '1'
        }),
        help_text="Choose an amount that feels meaningful to you"
    )
    
    def __init__(self, *args, minimum_price_cents=1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.minimum_price_cents = minimum_price_cents
        self.fields['amount_cents'].validators.append(
            MinValueValidator(minimum_price_cents, message=f"Minimum amount is ${minimum_price_cents / 100:.2f}")
        )
        # Set initial value to minimum price in dollars
        if not self.is_bound:
            self.initial['amount_cents'] = minimum_price_cents // 100
    
    def clean_amount_cents(self):
        """Convert dollars to cents and validate."""
        amount_dollars = self.cleaned_data['amount_cents']
        amount_cents = amount_dollars * 100
        
        if amount_cents < self.minimum_price_cents:
            raise forms.ValidationError(
                f"Minimum amount is ${self.minimum_price_cents / 100:.2f}"
            )
        
        return amount_cents

