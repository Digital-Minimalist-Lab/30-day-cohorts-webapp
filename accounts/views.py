from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpRequest
from django.contrib import messages
import json

from surveys.models import Survey, SurveySubmission
from cohorts.models import UserSurveyResponse, Enrollment
from cohorts.surveys import aggregate_checkin_data

from .forms import UserProfileForm, FullSignupForm
from .models import UserProfile

def request_login_code_redirect(request: HttpRequest) -> HttpResponse:
    """Redirects the default request_login_code view to the main login page."""
    return redirect('account_login')


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """User profile page with settings and data view."""
    
    # Get or create profile (in case signal didn't fire)
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=profile)
    
    # Get data view information
    enrollment = Enrollment.objects.filter(user=request.user).select_related('cohort').order_by('-enrolled_at').first()
    
    cohort = None
    checkins = None
    aggregated_data = {}
    
    if enrollment:
        cohort = enrollment.cohort
        # Fetch check-in submissions with a single, more efficient query
        # by filtering SurveySubmission through its reverse relationship to UserSurveyResponse.
        checkins = SurveySubmission.objects.filter(
            survey__purpose=Survey.Purpose.DAILY_CHECKIN,
            user_responses__user=request.user,
            user_responses__cohort=cohort
        ).prefetch_related(
            'answers', 'answers__question'
        ).order_by('completed_at').distinct()
        
        aggregated_data = aggregate_checkin_data(checkins)
    
    return render(request, 'account/profile.html', {
        'form': form,
        'cohort': cohort,
        'checkins': checkins,
        'checkin_aggregation': aggregated_data,
    })


@login_required
def export_user_data(request: HttpRequest) -> HttpResponse:
    """Export all user data (GDPR compliance)."""    
    user = request.user
    
    # Get or create profile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    # Gather all user data
    data = {
        'user': {
            'email': user.email,
            'date_joined': user.date_joined.isoformat(),
        },
        'profile': profile.to_dict(),
        'enrollments': [e.to_dict() for e in Enrollment.objects.filter(user=user)],
        'submissions': [s.to_dict() for s in UserSurveyResponse.objects.filter(user=user).order_by('submission__completed_at')],
    }
    
    # Return as JSON file
    response = HttpResponse(
        json.dumps(data, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="user_data_{user.id}.json"'
    return response


@login_required
def delete_account(request: HttpRequest) -> HttpResponse:
    """Delete user account (GDPR compliance - hard delete)."""
    if request.method == 'POST':
        if request.POST.get('confirm') == 'DELETE':
            user = request.user
            user.delete()  # Cascade delete all related data
            messages.success(request, 'Your account has been permanently deleted.')
            return redirect('cohorts:dashboard')
        else:
            messages.error(request, 'Please type DELETE to confirm account deletion.')
    
    return render(request, 'account/delete_account.html')
