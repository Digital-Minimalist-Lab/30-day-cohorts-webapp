from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from .models import Survey
from .forms import DynamicSurveyForm

@staff_member_required
def survey_preview(request, slug):
    """
    Preview a survey form without requiring a cohort enrollment.
    Only accessible to staff members.
    """
    survey = get_object_or_404(Survey, slug=slug)
    form = DynamicSurveyForm(survey=survey)
    
    context = {
        'survey': survey,
        'form': form,
        'page_title': f"Preview: {survey.name}",
        'description': survey.description,
        'cohort_name': "Preview Mode",
        'preview_mode': True,
    }
    
    # Reuse the default survey template
    return render(request, 'surveys/views/default/survey_form.html', context)
