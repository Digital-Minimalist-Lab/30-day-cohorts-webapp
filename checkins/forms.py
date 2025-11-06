from django import forms
from .models import DailyCheckin, WeeklyReflection


class DailyCheckinForm(forms.ModelForm):
    """Form for daily 5-step keystone habit reflection."""
    class Meta:
        model = DailyCheckin
        fields = [
            'mood_1to5',
            'digital_satisfaction_1to5',
            'screentime_min',
            'proud_moment_text',
            'digital_slip_text',
            'reflection_text'
        ]
        widgets = {
            'mood_1to5': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'digital_satisfaction_1to5': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'screentime_min': forms.NumberInput(attrs={
                'placeholder': 'Screen time in minutes (estimated or actual)'
            }),
            'proud_moment_text': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'One thing you\'re proud of that replaced scrolling...'
            }),
            'digital_slip_text': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'If you slipped, describe what happened (optional)'
            }),
            'reflection_text': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '1-2 sentences about how today went...'
            }),
        }
        labels = {
            'mood_1to5': 'Step 1: How do you feel today? (1=low, 5=high)',
            'digital_satisfaction_1to5': 'Step 2: Satisfaction with your digital use today? (1=low, 5=high)',
            'screentime_min': 'Step 3: Screen time today (minutes)',
            'proud_moment_text': 'Step 4: One thing you\'re proud of',
            'digital_slip_text': 'Step 5a: Did you slip into digital use? (optional)',
            'reflection_text': 'Step 5b: How did today go?',
        }


class WeeklyReflectionForm(forms.ModelForm):
    """Form for weekly reflection and goal setting."""
    class Meta:
        model = WeeklyReflection
        fields = ['goal_text', 'reflection_text']
        widgets = {
            'goal_text': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
                'rows': 4,
                'placeholder': 'What\'s your intention for this week?'
            }),
            'reflection_text': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
                'rows': 4,
                'placeholder': 'Reflect on last week (optional)'
            }),
        }
        labels = {
            'goal_text': 'Your intention for this week',
            'reflection_text': 'Reflection on last week (optional)',
        }

