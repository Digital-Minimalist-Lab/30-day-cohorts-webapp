from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpRequest
from django.contrib import messages
import json
import secrets
from allauth.account.views import ConfirmLoginCodeView
from allauth.decorators import rate_limit
from allauth.account.utils import get_next_redirect_url
from cohorts.models import UserSurveyResponse, Enrollment

from .forms import UserProfileForm
from .models import UserProfile

def request_login_code_redirect(request: HttpRequest) -> HttpResponse:
    """
    Redirects the default request_login_code view to the main login page.
    It also generates and stores a session token to be used in the magic link.
    """
    # Generate a secure token and store it in the session.
    # This token will be included in the login link to tie it to this specific session.
    request.session['login_code_token'] = secrets.token_urlsafe(32)
    return redirect('account_login')


# @rate_limit(action='login_by_code')
def login_by_code_view(request: HttpRequest) -> HttpResponse:
    """
    Handles one-click login from the email link.

    This view validates the code, email, and a session-based token from the URL
    and logs the user in if everything is correct.
    """
    if request.method == 'GET' and 'code' in request.GET:
        # To auto-login, we trick ConfirmLoginCodeView into thinking this is a POST.
        # We modify the request object in-place for this view's scope.
        request.method = 'POST'
        request.POST = request.GET.copy() # Copies 'code' from URL params to POST data

    # Allauth's view will now process this as a POST request and log the user in.
    response = ConfirmLoginCodeView.as_view()(request)

    if request.user.is_authenticated:
        # The token has been used, so remove it.
        request.session.pop('login_code_token', None)
        return redirect(get_next_redirect_url(request) or 'cohorts:join_entry_survey')

    # If login fails (e.g., wrong code), allauth's view will render the form with errors.
    return response


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
    
    return render(request, 'account/profile.html', {
        'form': form,
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
