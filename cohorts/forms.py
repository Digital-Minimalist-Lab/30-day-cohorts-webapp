from typing import Any, Dict, Optional
from django import forms
from django.core.validators import MinValueValidator
from .models import Cohort

import logging

logger = logging.getLogger(__name__)

class CohortForm(forms.ModelForm):
    """Form for creating and updating cohorts."""
    class Meta:
        model = Cohort
        fields = ['name', 'start_date', 'end_date', 'enrollment_start_date', 'enrollment_end_date', 'minimum_price_cents', 'is_paid', 'max_seats', 'is_active']
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
            'enrollment_start_date': forms.DateInput(attrs={
                'type': 'date'
            }),
            'enrollment_end_date': forms.DateInput(attrs={
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
            'enrollment_start_date': 'The first day users can join.',
            'enrollment_end_date': 'The last day users can join.',
        }
    
    def clean(self) -> Optional[Dict[str, Any]]:
        """Validate date logic."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        enrollment_start = cleaned_data.get('enrollment_start_date')
        enrollment_end = cleaned_data.get('enrollment_end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise forms.ValidationError(
                    'End date must be after start date.'
                )

        if enrollment_start and enrollment_end:
            if enrollment_end < enrollment_start:
                raise forms.ValidationError(
                    'Enrollment end date must be on or after the enrollment start date.'
                )
        
        return cleaned_data


class PaymentAmountForm(forms.Form):
    """Form for selecting payment amount (pay-what-you-want)."""
    amount = forms.DecimalField(
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'placeholder': 'Enter amount in dollars',
            'step': '0.01',
        }),
        help_text="Choose an amount that feels meaningful to you"
    )

    def __init__(self, *args, minimum_price_cents=1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.minimum_price_cents = minimum_price_cents
        minimum_price_dollars = minimum_price_cents / 100

        self.fields['amount'].min_value = minimum_price_dollars
        self.fields['amount'].validators.append(
            MinValueValidator(minimum_price_dollars, message=f"Minimum amount is ${minimum_price_dollars:.2f}")
        )
        self.fields['amount'].widget.attrs['min'] = f'{minimum_price_dollars:.2f}'

        # Set initial value to minimum price in dollars
        if not self.is_bound:
            self.initial['amount'] = f'{minimum_price_dollars:.2f}'


    def clean(self):
        """Validate amount and convert to cents."""
        cleaned_data = super().clean()
        amount_dollars = cleaned_data.get('amount')

        # If amount is None (field validation failed), skip further validation
        if amount_dollars is None:
            return cleaned_data

        amount_cents = int(amount_dollars * 100)

        if amount_cents < self.minimum_price_cents:
            logger.warning("validation error...")
            raise forms.ValidationError(
                f"Minimum amount is ${self.minimum_price_cents / 100:.2f}"
            )

        cleaned_data['amount_cents'] = amount_cents

        return cleaned_data
