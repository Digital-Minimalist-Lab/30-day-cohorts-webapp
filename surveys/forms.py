from django import forms
from .models import Question
from django.forms.widgets import TextInput, Textarea, NumberInput, RadioSelect

import logging

logger = logging.getLogger(__name__)

class DynamicSurveyForm(forms.Form):
    """
    A form that is dynamically built from a Survey's Questions.
    """
    def __init__(self, *args, survey, **kwargs):
        self.survey = survey
        super().__init__(*args, **kwargs)

        for question in self.survey.questions.all():
            field_key = question.key
            field_class = self.get_field_class(question.question_type)
            field_widget = self.get_field_widget(question)
            
            field_kwargs = {
                'label': question.text,
                'required': question.is_required,
                'widget': field_widget,
            }
            if question.question_type == Question.QuestionType.RADIO:
                field_kwargs['choices'] = list(question.choices.items()) if question.choices else []
            
            self.fields[field_key] = field_class(**field_kwargs)

    def get_field_class(self, question_type):
        if question_type == Question.QuestionType.INTEGER:
            return forms.IntegerField
        if question_type == Question.QuestionType.RADIO:
            return forms.ChoiceField
        return forms.CharField # Default for TEXT and TEXTAREA

    def get_field_widget(self, question):
        """Get the widget instance for a given question."""
        base_attrs = {'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'}

        if question.question_type == Question.QuestionType.TEXTAREA:
            attrs = base_attrs.copy()
            attrs['rows'] = 4
            return Textarea(attrs=attrs)
        if question.question_type == Question.QuestionType.RADIO:
            # These classes are applied to each <input type="radio"> tag.
            radio_attrs = {'class': 'h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500'}
            return RadioSelect(attrs=radio_attrs)
        if question.question_type == Question.QuestionType.INTEGER:
            return NumberInput(attrs=base_attrs)
        return TextInput(attrs=base_attrs) # Default for TEXT
