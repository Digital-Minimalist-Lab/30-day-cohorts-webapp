from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.db import connection
from django.contrib import messages
import json
from datetime import datetime
from .forms import UserProfileForm


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
    from cohorts.models import Cohort, Enrollment
    from checkins.models import DailyCheckin
    
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
    avg_mood = None
    avg_digital_satisfaction = None
    avg_screentime = None
    mood_change = None
    screentime_change = None
    
    if enrollment:
        cohort = enrollment.cohort
        checkins = DailyCheckin.objects.filter(
            user=request.user,
            cohort=cohort
        ).order_by('date')
        
        # Calculate aggregates
        if checkins.exists():
            avg_mood = sum(c.mood_1to5 for c in checkins) / len(checkins)
            avg_digital_satisfaction = sum(c.digital_satisfaction_1to5 for c in checkins) / len(checkins)
            avg_screentime = sum(c.screentime_min for c in checkins) / len(checkins)
            
            # Get first and last for comparison
            first_checkin = checkins.first()
            latest_checkin = checkins.last()
            
            mood_change = latest_checkin.mood_1to5 - first_checkin.mood_1to5
            screentime_change = latest_checkin.screentime_min - first_checkin.screentime_min
    
    return render(request, 'accounts/profile.html', {
        'form': form,
        'cohort': cohort,
        'checkins': checkins,
        'avg_mood': avg_mood,
        'avg_digital_satisfaction': avg_digital_satisfaction,
        'avg_screentime': avg_screentime,
        'mood_change': mood_change,
        'screentime_change': screentime_change,
    })


@login_required
def export_user_data(request: HttpRequest) -> HttpResponse:
    """Export all user data (GDPR compliance)."""
    from .models import UserProfile
    
    user = request.user
    
    # Get or create profile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    # Gather all user data
    data = {
        'user': {
            'email': user.email,
            'date_joined': user.date_joined.isoformat(),
        },
        'profile': {
            'timezone': profile.timezone,
            'email_daily_reminder': profile.email_daily_reminder,
            'email_weekly_reminder': profile.email_weekly_reminder,
        },
        'enrollments': [],
        'entry_surveys': [],
        'daily_checkins': [],
        'weekly_reflections': [],
        'exit_surveys': [],
    }
    
    # Enrollments
    for enrollment in user.enrollments.all():
        data['enrollments'].append({
            'cohort': enrollment.cohort.name,
            'enrolled_at': enrollment.enrolled_at.isoformat(),
            'paid_at': enrollment.paid_at.isoformat() if enrollment.paid_at else None,
        })
    
    # Entry surveys
    for survey in user.entry_surveys.all():
        data['entry_surveys'].append({
            'cohort': survey.cohort.name,
            'mood': survey.mood_1to5,
            'baseline_screentime_min': survey.baseline_screentime_min,
            'intention': survey.intention_text,
            'challenge': survey.challenge_text,
            'completed_at': survey.completed_at.isoformat(),
        })
    
    # Daily check-ins
    for checkin in user.daily_checkins.all():
        data['daily_checkins'].append({
            'cohort': checkin.cohort.name,
            'date': checkin.date.isoformat(),
            'mood': checkin.mood_1to5,
            'digital_satisfaction': checkin.digital_satisfaction_1to5,
            'screentime_min': checkin.screentime_min,
            'proud_moment': checkin.proud_moment_text,
            'digital_slip': checkin.digital_slip_text,
            'reflection': checkin.reflection_text,
        })
    
    # Weekly reflections
    for reflection in user.weekly_reflections.all():
        data['weekly_reflections'].append({
            'cohort': reflection.cohort.name,
            'week': reflection.week_index,
            'goal': reflection.goal_text,
            'reflection': reflection.reflection_text,
            'created_at': reflection.created_at.isoformat(),
        })
    
    # Exit surveys
    for survey in user.exit_surveys.all():
        data['exit_surveys'].append({
            'cohort': survey.cohort.name,
            'mood': survey.mood_1to5,
            'final_screentime_min': survey.final_screentime_min,
            'wins': survey.wins_text,
            'insights': survey.insight_text,
            'completed_at': survey.completed_at.isoformat(),
        })
    
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

