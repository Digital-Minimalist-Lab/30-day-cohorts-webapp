from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from cohorts.models import Cohort, Enrollment
from .models import EntrySurvey, ExitSurvey
from .forms import EntrySurveyForm, ExitSurveyForm


@login_required
def entry_survey(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """Entry survey for baseline metrics."""
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    # Check if user is enrolled
    enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
    if not enrollment:
        messages.error(request, 'You must join this cohort first.')
        return redirect('cohorts:cohort_list')
    
    # Check if already completed
    existing_survey = EntrySurvey.objects.filter(user=request.user, cohort=cohort).first()
    if existing_survey:
        messages.info(request, 'You have already completed the entry survey.')
        return redirect('cohorts:homepage')
    
    if request.method == 'POST':
        form = EntrySurveyForm(request.POST)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.user = request.user
            survey.cohort = cohort
            survey.save()
            messages.success(request, 'Entry survey completed!')
            return redirect('cohorts:homepage')
    else:
        form = EntrySurveyForm()
    
    return render(request, 'surveys/entry_survey.html', {
        'form': form,
        'cohort': cohort,
    })


@login_required
def exit_survey(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """Exit survey for final reflections."""
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    # Check if user is enrolled
    enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
    if not enrollment:
        messages.error(request, 'You must be enrolled in this cohort.')
        return redirect('cohorts:cohort_list')
    
    # Check if already completed
    existing_survey = ExitSurvey.objects.filter(user=request.user, cohort=cohort).first()
    if existing_survey:
        messages.info(request, 'You have already completed the exit survey.')
        return redirect('cohorts:homepage')
    
    if request.method == 'POST':
        form = ExitSurveyForm(request.POST)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.user = request.user
            survey.cohort = cohort
            survey.save()
            messages.success(request, 'Exit survey completed! Thank you for participating.')
            return redirect('cohorts:homepage')
    else:
        form = ExitSurveyForm()
    
    # Get entry survey for comparison
    entry_survey = EntrySurvey.objects.filter(user=request.user, cohort=cohort).first()
    
    return render(request, 'surveys/exit_survey.html', {
        'form': form,
        'cohort': cohort,
        'entry_survey': entry_survey,
    })

