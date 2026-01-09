from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('content_type', 'object_id', 'recipient_email', 'price_cents')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'get_total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'user__username', 'id')
    inlines = [OrderItemInline]
    readonly_fields = ('created_at', 'updated_at')

    def get_total_amount(self, obj):
        return f"${obj.total_amount_cents / 100:.2f}"
    get_total_amount.short_description = 'Total Amount'

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'recipient_email', 'get_price', 'content_type', 'object_id')
    list_filter = ('content_type',)
    search_fields = ('recipient_email', 'order__user__email', 'order__id')
    
    def get_price(self, obj):
        return f"${obj.price_cents / 100:.2f}"
    get_price.short_description = 'Price'
