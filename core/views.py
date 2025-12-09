from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

def privacy_policy(request: HttpRequest) -> HttpResponse:
    """Privacy policy page."""
    return render(request, 'core/privacy.html')


def protocol_view(request: HttpRequest) -> HttpResponse:
    """30-day digital declutter protocol page."""
    return render(request, 'core/protocol.html')


def resources_view(request: HttpRequest) -> HttpResponse:
    """Resources page."""
    return render(request, 'core/resources.html')