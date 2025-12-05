from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.db import connection
from django.contrib import messages
import json
from datetime import datetime
from .forms import UserProfileForm
from surveys.models import Survey, SurveySubmission
from allauth.account.views import LoginView, SignupView, LoginForm, SignupForm
from cohorts.services import aggregate_checkin_data


class CustomLoginView(LoginView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['signup_form'] = SignupForm()
        context['login_form'] = context.pop('form')
        return context

class CustomSignupView(SignupView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['login_form'] = LoginForm()
        context['signup_form'] = context.pop('form')
        return context


def health_check(request: HttpRequest) -> JsonResponse:
    """
    Health check endpoint for monitoring and load balancers.
    
    Verifies database connectivity and returns JSON with status.
    Used by deployment platforms (Fly.io, etc.) to monitor application health.
    
    Returns:
        JsonResponse with status 200 if healthy, 500 if unhealthy
    """
    try:
        # Check database connectivity
        connection.ensure_connection()
        return JsonResponse({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=500)


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """User profile page with settings and data view."""
    from .models import UserProfile
    from cohorts.models import Enrollment
    
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
        checkins = SurveySubmission.objects.none()
        
        checkins = SurveySubmission.objects.filter(
            user=request.user, cohort=cohort, survey__purpose=Survey.Purpose.DAILY_CHECKIN,
        ).prefetch_related('answers', 'answers__question').order_by('completed_at')
        
        aggregated_data = aggregate_checkin_data(checkins)
    
    return render(request, 'accounts/profile.html', {
        'form': form,
        'cohort': cohort,
        'checkins': checkins,
        'checkin_aggregation': aggregated_data,
    })


@login_required
def export_user_data(request: HttpRequest) -> HttpResponse:
    """Export all user data (GDPR compliance)."""
    from .models import UserProfile
    from cohorts.models import Enrollment
    
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
        'submissions': [s.to_dict() for s in SurveySubmission.objects.filter(user=user).order_by('completed_at')],
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
            return redirect('cohorts:homepage')
        else:
            messages.error(request, 'Please type DELETE to confirm account deletion.')
    
    return render(request, 'accounts/delete_account.html')


def privacy_policy(request: HttpRequest) -> HttpResponse:
    """Privacy policy page."""
    return render(request, 'accounts/privacy.html')


def protocol_view(request: HttpRequest) -> HttpResponse:
    """30-day digital declutter protocol page."""
    return render(request, 'accounts/protocol.html')


def resources_view(request: HttpRequest) -> HttpResponse:
    """Resources page."""
    return render(request, 'accounts/resources.html')
