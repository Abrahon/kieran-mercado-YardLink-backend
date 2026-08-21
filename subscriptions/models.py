from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from .enums import SubscriptionDuration, SubscriptionStatus
from decimal import Decimal 
from django.core.exceptions import ValidationError
# from .models import Subscription

User = get_user_model()

# plan model

class Plan(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    # NEW: features list
    features = models.JSONField(
        default=list,
        blank=True,
        help_text="List of plan features"
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    discount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    duration = models.CharField(
        max_length=20,
        choices=SubscriptionDuration.choices,
        default=SubscriptionDuration.MONTHLY
    )

    stripe_product_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    stripe_price_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    # apple_product_id = models.CharField(
    #     max_length=255,
    #     blank=True,
    #     null=True,
    #     unique=True
    # )

    trial_notified_days = models.JSONField(
        default=list,
        blank=True
    )

    last_day_notified = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price"]

        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["duration"]),
        ]

    def clean(self):

        if self.discount < 0 or self.discount > 100:
            raise ValidationError({
                "discount": "Discount must be between 0 and 100."
            })

        if self.price < 0:
            raise ValidationError({
                "price": "Price cannot be negative."
            })

        # validate features
        if self.features:

            if not isinstance(self.features, list):
                raise ValidationError({
                    "features": "Features must be a list."
                })

            for feature in self.features:

                if not isinstance(feature, str):
                    raise ValidationError({
                        "features": "Each feature must be a string."
                    })

    @property
    def duration_days(self):

        mapping = {
            SubscriptionDuration.MONTHLY: 30,
            SubscriptionDuration.YEARLY: 365,
        }

        return mapping.get(self.duration, 30)

    @property
    def final_price(self):

        price = Decimal(self.price)

        discount = Decimal(self.discount)

        return price - (
            price * discount / Decimal("100")
        )

    def __str__(self):
        return f"{self.name} ({self.duration})"




class Subscription(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )

    # ==============================
    # Stripe
    # ==============================

    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    # ==============================
    # Apple IAP
    # ==============================

    apple_original_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True
    )

    apple_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True
    )

    # ==============================
    # Payment Provider
    # ==============================

    payment_provider = models.CharField(
        max_length=20,
        choices=[
            ("stripe", "Stripe"),
            ("apple", "Apple"),
            ("manual", "Manual"),
        ],
        default="stripe"
    )

    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE
    )

    is_trial = models.BooleanField(default=False)

    start_date = models.DateTimeField()

    end_date = models.DateTimeField()

    auto_renew = models.BooleanField(default=True)

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    discount_override = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    trial_extended_days = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    BASE_TRIAL_DAYS = 14

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["user"]),
        ]

    def clean(self):

        if self.discount_override < 0 or self.discount_override > 100:
            raise ValidationError({
                "discount_override": "Discount must be between 0 and 100."
            })

    @property
    def effective_discount(self):

        if self.discount_override and self.discount_override > 0:
            return Decimal(self.discount_override)

        return Decimal(self.plan.discount or 0)

    @property
    def effective_price(self):

        price = Decimal(self.plan.price)

        discount = self.effective_discount

        return price - (
            price * discount / Decimal("100")
        )

    @property
    def total_trial_days(self):

        return self.BASE_TRIAL_DAYS + self.trial_extended_days

    @property
    def trial_end_date(self):

        return self.start_date + timedelta(days=self.total_trial_days)

    def refresh_dates_by_plan(self, from_now=False):

        base_time = timezone.now() if from_now else self.start_date

        self.start_date = base_time

        if self.is_trial:
            self.end_date = (
                base_time + timedelta(days=self.total_trial_days)
            )

        else:
            self.end_date = (
                base_time + timedelta(days=self.plan.duration_days)
            )

    def extend_trial(self, extra_days):

        if extra_days < 0:
            raise ValidationError(
                "extra_days cannot be negative."
            )

        self.trial_extended_days += extra_days

        if self.is_trial:

            self.end_date = (
                self.start_date + timedelta(days=self.total_trial_days)
            )

        self.save(update_fields=[
            "trial_extended_days",
            "end_date",
            "updated_at"
        ])

    def check_auto_renew(self):

        now = timezone.now()

        if self.is_trial:
            return False

        if (
            self.auto_renew
            and self.status in [
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.EXPIRED
            ]
            and self.end_date <= now
        ):

            self.start_date = now

            self.end_date = (
                now + timedelta(days=self.plan.duration_days)
            )

            self.status = SubscriptionStatus.ACTIVE

            self.save(update_fields=[
                "start_date",
                "end_date",
                "status",
                "updated_at"
            ])

            return True

        return False

    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"
    


class SubscriptionLog(models.Model):
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="logs"
    )

    action = models.CharField(max_length=50)

    performed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    reason = models.TextField(blank=True, null=True)

    level = models.CharField(
        max_length=20,
        choices=[
            ("info", "Info"),
            ("warning", "Warning"),
            ("critical", "Critical"),
        ],
        default="info"
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["subscription"]),
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
        ]