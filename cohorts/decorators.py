from functools import wraps
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from .models import Cohort, Enrollment

def enrollment_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        cohort_id = kwargs.get('cohort_id')
        enrollment = None

        if cohort_id:
            # If a cohort_id is provided, get that specific enrollment.
            cohort = get_object_or_404(Cohort, id=cohort_id)
            enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).select_related('cohort').first()
        else:
            # Otherwise, get the user's most recent enrollment.
            enrollment = Enrollment.objects.filter(user=request.user).select_related('cohort').order_by('-enrolled_at').first()
        
        if not enrollment:
            messages.error(request, "You are not enrolled in this cohort.")
            return redirect('cohorts:dashboard')
        
        # Prepare context for the decorated view.
        # Create a new context dict or update an existing one.
        context = kwargs.get('context', {})
        
        context.update({
            'enrollment': enrollment,
            'cohort': enrollment.cohort,
        })
        kwargs['context'] = context
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view
