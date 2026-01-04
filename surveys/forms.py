from django import forms
from .models import Question
from django.forms.widgets import TextInput, Textarea, NumberInput, RadioSelect

import logging

logger = logging.getLogger(__name__)


class PicoRadioSelect(RadioSelect):
    template_name = 'widgets/pico_radio.html'

    def __init__(self, text, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text = text
        self.label = text
        self.hide_label = True

    # remove aria-invalid from the internal elements
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        option['attrs'].pop('aria-invalid', None)
        return option
    
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['label'] = self.text
        context['widget']['hide_label'] = self.hide_label
        return context

class DynamicSurveyForm(forms.Form):
    """
    A form that is dynamically built from a Survey's Questions.

    Intended to be used as the 'form_class' in a FormView. 
    """
    def __init__(self, *args, survey, **kwargs):
        self.survey = survey
        super().__init__(*args, **kwargs)
        
        # Store section info and info questions for rendering
        self._field_sections = {}
        self._info_questions = {}  # Store INFO type questions by key

        # Query sections, then questions
        self._sections = list(self.survey.sections.prefetch_related('questions').all())

        for section in self._sections:
            for question in section.questions.all():
                field_key = question.key
                
                # Skip INFO type - these are display-only, no form field needed
                if question.question_type == Question.QuestionType.INFO:
                    self._field_sections[field_key] = section
                    self._info_questions[field_key] = question
                    continue
                
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
                self._field_sections[field_key] = section
    
    def get_fields_by_section(self):
        """
        Returns fields grouped by section for template rendering.
        Returns a list of tuples: [(section, [items]), ...]
        Where 'section' is a SurveySection object or None.
        Items are dicts with either 'field' (bound field) or 'info' (info question).
        """
        sections = []
        
        for section in self._sections:
            current_items = []
            for question in section.questions.all():
                # Add either info question or bound field
                if question.key in self._info_questions:
                    current_items.append({
                        'is_info': True,
                        'text': question.text,
                        'strength': question.strength,
                        'key': question.key
                    })
                elif question.key in self.fields:
                    current_items.append({
                        'is_info': False,
                        'field': self[question.key],
                        'strength': question.strength,
                    })
            
            sections.append((section, current_items))
        
        return sections

    def get_field_class(self, question_type):
        if question_type == Question.QuestionType.INTEGER:
            return forms.IntegerField
        if question_type == Question.QuestionType.DECIMAL:
            return forms.DecimalField
        if question_type == Question.QuestionType.RADIO:
            return forms.ChoiceField
        return forms.CharField # Default for TEXT and TEXTAREA

    def get_field_widget(self, question):
        """Get the widget instance for a given question."""
        base_attrs = {}

        if question.question_type == Question.QuestionType.TEXTAREA:
            attrs = base_attrs.copy()
            attrs['rows'] = 4
            return Textarea(attrs=attrs)
        if question.question_type == Question.QuestionType.RADIO:
            return PicoRadioSelect(text=question.text, attrs=base_attrs)
        if question.question_type == Question.QuestionType.INTEGER:
            return NumberInput(attrs=base_attrs)
        if question.question_type == Question.QuestionType.DECIMAL:
            return NumberInput(attrs=base_attrs)
        return TextInput(attrs=base_attrs) # Default for TEXT
