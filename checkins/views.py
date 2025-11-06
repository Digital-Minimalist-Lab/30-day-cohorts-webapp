from typing import Optional
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from django.utils import timezone
import pytz
from cohorts.models import Cohort, Enrollment
from .models import DailyCheckin, WeeklyReflection
from .forms import DailyCheckinForm, WeeklyReflectionForm


def get_user_today(user: AbstractUser) -> date:
    """
    Get today's date in user's timezone.
    
    Args:
        user: Django User instance with associated UserProfile
        
    Returns:
        datetime.date: Today's date in user's timezone
    """
    from accounts.models import UserProfile
    
    # Get or create profile (defensive programming)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    user_tz = pytz.timezone(profile.timezone)
    return timezone.now().astimezone(user_tz).date()


@login_required
def daily_checkin(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """Daily 5-step keystone habit reflection."""
    cohort = get_object_or_404(Cohort, id=cohort_id)
    today = get_user_today(request.user)
    
    # Check if user is enrolled
    enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
    if not enrollment:
        messages.error(request, 'You must be enrolled in this cohort.')
        return redirect('cohorts:cohort_list')
    
    # Check if already completed today
    existing_checkin = DailyCheckin.objects.filter(
        user=request.user,
        cohort=cohort,
        date=today
    ).first()
    
    if existing_checkin:
        messages.info(request, f'You have already completed today\'s check-in ({today}).')
        return redirect('cohorts:homepage')
    
    if request.method == 'POST':
        form = DailyCheckinForm(request.POST)
        if form.is_valid():
            checkin = form.save(commit=False)
            checkin.user = request.user
            checkin.cohort = cohort
            checkin.date = today
            checkin.save()
            messages.success(request, 'Daily check-in completed!')
            return redirect('cohorts:homepage')
    else:
        form = DailyCheckinForm()
    
    return render(request, 'checkins/daily_checkin.html', {
        'form': form,
        'cohort': cohort,
        'today': today,
    })


@login_required
def weekly_reflection(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """Weekly reflection and goal setting."""
    cohort = get_object_or_404(Cohort, id=cohort_id)
    today = get_user_today(request.user)
    
    # Check if user is enrolled
    enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
    if not enrollment:
        messages.error(request, 'You must be enrolled in this cohort.')
        return redirect('cohorts:cohort_list')
    
    # Calculate which week we're in
    days_since_start = (today - cohort.start_date).days
    week_days = {1: 7, 2: 14, 3: 21, 4: 28}
    
    # Find the appropriate week index (with catch-up logic)
    current_week_index = None
    for week_index, week_day in week_days.items():
        if days_since_start >= week_day and days_since_start < week_day + 7:
            # Check if this week is already done
            existing = WeeklyReflection.objects.filter(
                user=request.user,
                cohort=cohort,
                week_index=week_index
            ).first()
            if not existing:
                current_week_index = week_index
                break
    
    if current_week_index is None:
        messages.info(request, 'No weekly reflection available at this time.')
        return redirect('cohorts:homepage')
    
    # Check if already completed
    existing_reflection = WeeklyReflection.objects.filter(
        user=request.user,
        cohort=cohort,
        week_index=current_week_index
    ).first()
    
    if existing_reflection:
        messages.info(request, f'You have already completed Week {current_week_index} reflection.')
        return redirect('cohorts:homepage')
    
    if request.method == 'POST':
        form = WeeklyReflectionForm(request.POST)
        if form.is_valid():
            reflection = form.save(commit=False)
            reflection.user = request.user
            reflection.cohort = cohort
            reflection.week_index = current_week_index
            reflection.save()
            messages.success(request, f'Week {current_week_index} reflection completed!')
            return redirect('cohorts:homepage')
    else:
        form = WeeklyReflectionForm()
    
    return render(request, 'checkins/weekly_reflection.html', {
        'form': form,
        'cohort': cohort,
        'week_index': current_week_index,
    })


@login_required
def past_checkins(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """View past daily check-ins."""
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    # Check if user is enrolled
    enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
    if not enrollment:
        messages.error(request, 'You must be enrolled in this cohort.')
        return redirect('cohorts:cohort_list')
    
    checkins = DailyCheckin.objects.filter(
        user=request.user,
        cohort=cohort
    ).order_by('-date')
    
    return render(request, 'checkins/past_checkins.html', {
        'cohort': cohort,
        'checkins': checkins,
    })


@login_required
def past_reflections(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """View past weekly reflections."""
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    # Check if user is enrolled
    enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
    if not enrollment:
        messages.error(request, 'You must be enrolled in this cohort.')
        return redirect('cohorts:cohort_list')
    
    reflections = WeeklyReflection.objects.filter(
        user=request.user,
        cohort=cohort
    ).order_by('week_index')
    
    return render(request, 'checkins/past_reflections.html', {
        'cohort': cohort,
        'reflections': reflections,
    })

