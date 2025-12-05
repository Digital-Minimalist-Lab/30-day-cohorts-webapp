from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
    

@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Simple dashboard redirect to homepage."""
    # Dashboard functionality is integrated into homepage
    # This is kept for backwards compatibility
    from cohorts.views import homepage
    return homepage(request)
