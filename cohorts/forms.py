from typing import Any, Dict, Optional
from django import forms
from .models import Cohort


class CohortForm(forms.ModelForm):
    """Form for creating and updating cohorts."""
    class Meta:
        model = Cohort
        fields = ['name', 'start_date', 'end_date', 'price_cents', 'is_active']
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
            'price_cents': forms.NumberInput(attrs={
                'placeholder': 'Price in cents (e.g., 1000 = $10.00)'
            }),
            'is_active': forms.CheckboxInput(),
        }
        help_texts = {
            'price_cents': 'Price in cents (e.g., 1000 = $10.00)',
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

