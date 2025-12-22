
import pytz

from django import forms
from allauth.account.forms import SignupForm
from .models import UserProfile

class FullSignupForm(SignupForm):
    """Extended signup form with timezone and email preferences."""
    timezone = forms.ChoiceField(
        choices=[(tz, tz) for tz in pytz.common_timezones],
        initial='America/New_York',
        required=True,
        help_text="Your timezone for accurate daily check-in dates"
    )
    email_product_updates = forms.BooleanField(
        required=False,
        initial=False,
        label="Sign up for updates to our mailing list",
        help_text=""
    )
    email_daily_reminder = forms.BooleanField(
        required=False,
        initial=False,
        label="Send me reminders to complete my daily tasks",
        help_text="Optional daily reminders to complete my tasks"
    )

    field_order = [
        'email',
        'password1',
        'password2',
        'timezone',
        'email_product_updates',
        'email_daily_reminder'
    ]

    def get_email_preference_fields(self):
        """Returns only the email preference fields for easier rendering."""
        return [
            self['email_product_updates'],
            self['email_daily_reminder']
        ]

    @property
    def email_preference_field_names(self):
        """Returns the names of the email preference fields for easier filtering in templates."""
        return [field.name for field in self.get_email_preference_fields()]

    def save(self, request):
        """Save the user and create associated UserProfile."""
        user = super().save(request)
        
        # Create or update UserProfile with timezone and email preferences
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'timezone': self.cleaned_data['timezone'],
                'email_product_updates': self.cleaned_data['email_product_updates'],
                'email_daily_reminder': self.cleaned_data['email_daily_reminder'],
            }
        )
        
        return user

class UserProfileForm(forms.ModelForm):
    """Form for updating user profile settings."""
    class Meta:
        model = UserProfile
        fields = ['timezone', 'email_product_updates', 'email_daily_reminder']
        widgets = {
            'timezone': forms.Select(),
            'email_product_updates': forms.CheckboxInput(),
            'email_daily_reminder': forms.CheckboxInput(),
        }
