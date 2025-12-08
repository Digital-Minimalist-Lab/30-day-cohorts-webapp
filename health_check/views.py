from django.http import HttpRequest, JsonResponse
from django.db import connection
from datetime import datetime


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
