from django import forms
from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    """Form for updating user profile settings."""
    class Meta:
        model = UserProfile
        fields = ['timezone', 'email_daily_reminder', 'email_weekly_reminder']
        widgets = {
            'timezone': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'email_daily_reminder': forms.CheckboxInput(attrs={'class': 'rounded'}),
            'email_weekly_reminder': forms.CheckboxInput(attrs={'class': 'rounded'}),
        }

