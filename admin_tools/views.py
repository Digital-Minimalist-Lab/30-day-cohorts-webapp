from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import HttpResponse, HttpRequest
from django.contrib.auth import get_user_model
from cohorts.models import Cohort, Enrollment
from checkins.models import DailyCheckin, WeeklyReflection
from surveys.models import EntrySurvey, ExitSurvey
import csv
from datetime import datetime

User = get_user_model()


@staff_member_required
def user_list(request: HttpRequest) -> HttpResponse:
    """List all users and their enrollments."""
    users = User.objects.all().order_by('-date_joined')
    
    # Get enrollment counts
    user_data = []
    for user in users:
        enrollments_count = Enrollment.objects.filter(user=user).count()
        checkins_count = DailyCheckin.objects.filter(user=user).count()
        user_data.append({
            'user': user,
            'enrollments_count': enrollments_count,
            'checkins_count': checkins_count,
        })
    
    return render(request, 'admin_tools/user_list.html', {
        'user_data': user_data,
    })


@staff_member_required
def export_cohort_csv(request: HttpRequest, cohort_id: int) -> HttpResponse:
    """Export cohort analytics as CSV."""
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="cohort_{cohort.id}_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    
    # Header
    writer.writerow([
        'User Email',
        'Enrolled At',
        'Paid At',
        'Entry Survey Completed',
        'Daily Check-ins Count',
        'Weekly Reflections Count',
        'Exit Survey Completed',
    ])
    
    # Data rows
    enrollments = Enrollment.objects.filter(cohort=cohort).select_related('user')
    for enrollment in enrollments:
        user = enrollment.user
        entry_survey = EntrySurvey.objects.filter(user=user, cohort=cohort).exists()
        checkins_count = DailyCheckin.objects.filter(user=user, cohort=cohort).count()
        reflections_count = WeeklyReflection.objects.filter(user=user, cohort=cohort).count()
        exit_survey = ExitSurvey.objects.filter(user=user, cohort=cohort).exists()
        
        writer.writerow([
            user.email,
            enrollment.enrolled_at.isoformat(),
            enrollment.paid_at.isoformat() if enrollment.paid_at else 'N/A',
            'Yes' if entry_survey else 'No',
            checkins_count,
            reflections_count,
            'Yes' if exit_survey else 'No',
        ])
    
    return response


@staff_member_required
def create_cohort(request: HttpRequest) -> HttpResponse:
    """Create a new cohort with proper form validation."""
    from cohorts.forms import CohortForm
    
    if request.method == 'POST':
        form = CohortForm(request.POST)
        if form.is_valid():
            cohort = form.save()
            messages.success(request, f'Cohort "{cohort.name}" created successfully.')
            return redirect('admin:cohorts_cohort_changelist')
    else:
        form = CohortForm()
    
    return render(request, 'admin_tools/create_cohort.html', {
        'form': form,
    })

