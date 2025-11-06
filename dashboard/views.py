from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest, HttpResponse
from cohorts.models import Cohort, Enrollment
from checkins.models import DailyCheckin


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Simple dashboard redirect to homepage."""
    # Dashboard functionality is integrated into homepage
    # This is kept for backwards compatibility
    from cohorts.views import homepage
    return homepage(request)


@login_required
def data_view(request: HttpRequest) -> HttpResponse:
    """
    View user's data with disclaimer about gamification.
    Hidden by default to avoid attention economy manipulation.
    """
    enrollment = Enrollment.objects.filter(user=request.user).select_related('cohort').order_by('-enrolled_at').first()
    
    if not enrollment:
        return render(request, 'dashboard/no_data.html')
    
    cohort = enrollment.cohort
    
    # Get all check-ins for charts
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
    else:
        avg_mood = None
        avg_digital_satisfaction = None
        avg_screentime = None
        mood_change = None
        screentime_change = None
    
    context = {
        'cohort': cohort,
        'checkins': checkins,
        'avg_mood': avg_mood,
        'avg_digital_satisfaction': avg_digital_satisfaction,
        'avg_screentime': avg_screentime,
        'mood_change': mood_change,
        'screentime_change': screentime_change,
    }
    
    return render(request, 'dashboard/data_view.html', context)


@login_required
def chart_data(request: HttpRequest, cohort_id: int) -> JsonResponse:
    """
    JSON endpoint for chart data visualization.
    
    Returns user's check-in data (mood, digital satisfaction, screentime)
    as JSON for Chart.js visualization. Requires user to be enrolled
    in the specified cohort.
    
    Args:
        request: Django request object with authenticated user
        cohort_id: ID of the cohort to get data for
        
    Returns:
        JsonResponse with dates, mood, digital_satisfaction, and screentime arrays
        or error message with 403 status if not enrolled
    """
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    # Verify user is enrolled in this cohort
    enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
    if not enrollment:
        return JsonResponse({'error': 'Not enrolled in this cohort'}, status=403)
    
    # Get check-ins
    checkins = DailyCheckin.objects.filter(
        user=request.user,
        cohort=cohort
    ).order_by('date')
    
    data = {
        'dates': [c.date.isoformat() for c in checkins],
        'mood': [c.mood_1to5 for c in checkins],
        'digital_satisfaction': [c.digital_satisfaction_1to5 for c in checkins],
        'screentime': [c.screentime_min for c in checkins],
    }
    
    return JsonResponse(data)

