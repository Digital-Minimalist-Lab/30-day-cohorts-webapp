from django import forms
from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    """Form for updating user profile settings."""
    class Meta:
        model = UserProfile
        fields = ['timezone', 'email_daily_reminder', 'email_weekly_reminder']
        widgets = {
            'timezone': forms.Select(),
            'email_daily_reminder': forms.CheckboxInput(),
            'email_weekly_reminder': forms.CheckboxInput(),
        }

