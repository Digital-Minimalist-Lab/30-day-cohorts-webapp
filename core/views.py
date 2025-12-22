from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse

# This is a temporary landing page which exists until the rest of the application is ready.
# That should be _fine_. There is now way this will go wrong.
def landing(request: HttpRequest) -> HttpResponse:
    context = None
    return render(request, 'core/landing.html', context)

def privacy_policy(request: HttpRequest) -> HttpResponse:
    """Privacy policy page."""
    return render(request, 'core/privacy.html')


def protocol_view(request: HttpRequest) -> HttpResponse:
    """30-day digital declutter protocol page."""
    return render(request, 'core/protocol.html')


def resources_view(request: HttpRequest) -> HttpResponse:
    """Resources page."""
    return render(request, 'core/resources.html')


def feedback_view(request: HttpRequest) -> HttpResponse:
    """Feedback page."""
    return redirect("https://docs.google.com/forms/d/e/1FAIpQLSdb0eSiUg6NS4Etj06TYLdbF0LAX-e1wrvHQHsM67VcABbTjQ/viewform?usp=dialog")