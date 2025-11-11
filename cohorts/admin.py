from django.contrib import admin
from .models import Cohort, Enrollment


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'minimum_price_cents', 'is_paid', 'seats_display', 'is_active']
    list_filter = ['is_active', 'is_paid', 'start_date']
    search_fields = ['name']
    date_hierarchy = 'start_date'
    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'start_date', 'end_date', 'is_active']
        }),
        ('Pricing', {
            'fields': ['is_paid', 'minimum_price_cents']
        }),
        ('Capacity', {
            'fields': ['max_seats'],
            'description': 'Leave blank for unlimited seats'
        }),
    ]
    
    def seats_display(self, obj):
        """Display seats taken / max seats."""
        enrolled_count = obj.enrollments.count()
        if obj.max_seats is None:
            return f"{enrolled_count} / ∞"
        return f"{enrolled_count} / {obj.max_seats}"
    seats_display.short_description = 'Seats'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'cohort', 'status', 'amount_paid_cents', 'paid_at', 'enrolled_at']
    list_filter = ['status', 'cohort', 'paid_at']
    search_fields = ['user__email', 'cohort__name']
    date_hierarchy = 'enrolled_at'
    readonly_fields = ['enrolled_at']

