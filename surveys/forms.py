from django import forms
from .models import EntrySurvey, ExitSurvey


class EntrySurveyForm(forms.ModelForm):
    """Form for entry survey."""
    class Meta:
        model = EntrySurvey
        fields = ['mood_1to5', 'baseline_screentime_min', 'intention_text', 'challenge_text']
        widgets = {
            'mood_1to5': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'baseline_screentime_min': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
                'placeholder': 'Estimated daily screen time in minutes'
            }),
            'intention_text': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
                'rows': 4,
                'placeholder': 'Why are you interested in participating in the digital detox?'
            }),
            'challenge_text': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
                'rows': 3,
                'placeholder': 'Name one thing you would like to reclaim (hobby, time with loved ones, etc.)'
            }),
        }
        labels = {
            'mood_1to5': 'How do you feel right now? (1=low, 5=high)',
            'baseline_screentime_min': 'Average daily smartphone usage (minutes)',
            'intention_text': 'Why are you interested in participating?',
            'challenge_text': 'What would you like to reclaim?',
        }


class ExitSurveyForm(forms.ModelForm):
    """Form for exit survey."""
    class Meta:
        model = ExitSurvey
        fields = ['mood_1to5', 'final_screentime_min', 'wins_text', 'insight_text']
        widgets = {
            'mood_1to5': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'final_screentime_min': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
                'placeholder': 'Current daily screen time in minutes'
            }),
            'wins_text': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
                'rows': 4,
                'placeholder': 'What were your wins during this 30-day journey?'
            }),
            'insight_text': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
                'rows': 4,
                'placeholder': 'What insights did you gain about your relationship with digital media?'
            }),
        }
        labels = {
            'mood_1to5': 'How do you feel now? (1=low, 5=high)',
            'final_screentime_min': 'Current daily screen time (minutes)',
            'wins_text': 'Your wins',
            'insight_text': 'Your insights',
        }

