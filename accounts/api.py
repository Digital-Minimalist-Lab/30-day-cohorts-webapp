import json
from django.http import JsonResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import UserProfile

@login_required
@require_POST
def update_profile_preferences(request: HttpRequest) -> JsonResponse:
    """
    API endpoint to toggle profile preferences (emails, view settings).
    
    Path: /api/accounts/preferences/
    Method: POST
    Body: 
    {
        "product_updates": optional boolean,
        "daily_reminders": optional boolean,
        "view_past_submissions": optional boolean
    }
    """
    # Handle both JSON (if sent) and Form Data (HTMX default)
    data = {}
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        data = request.POST

    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'Profile not found.'}, status=404)

    def get_bool(key):
        val = data.get(key)
        if val is None: return None
        if isinstance(val, bool): return val
        return str(val).lower() == 'true'

    daily_reminders = get_bool('daily_reminders')
    if daily_reminders is not None:
        profile.email_daily_reminder = daily_reminders

    product_updates = get_bool('product_updates')
    if product_updates is not None:
        profile.email_product_updates = product_updates

    view_past_submissions = get_bool('view_past_submissions')
    if view_past_submissions is not None:
        profile.view_past_submissions = view_past_submissions

    profile.save()
    
    return JsonResponse({'status': 'success'})
