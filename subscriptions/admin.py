from django.contrib import admin
from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration",
        "is_active",
        "stripe_product_id",
        "stripe_price_id",
    )

    search_fields = (
        "name",
    )

    list_filter = (
        "duration",
        "is_active",
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "plan",
        "status",
        "is_active",
        "payment_provider",
        "apple_transaction_id",
        "apple_original_transaction_id",
        "start_date",
        "end_date",
    )

    search_fields = (
        "user__email",
        "plan__name",
        "apple_transaction_id",
        "apple_original_transaction_id",
    )

    list_filter = (
        "status",
        "is_active",
        "payment_provider",
        "plan",
    )