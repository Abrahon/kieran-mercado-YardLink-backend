from rest_framework import serializers
from .models import Plan,Subscription
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from subscriptions.models import Subscription, SubscriptionLog

User = get_user_model()

from decimal import Decimal


class PlanSerializer(serializers.ModelSerializer):

    final_price = serializers.SerializerMethodField()

    class Meta:
        model = Plan

        fields = [
            "id",
            "name",
            "description",
            "features",
            "price",
            "discount",
            "final_price",
            "duration",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_discount(self, value):

        if value < 0 or value > 100:
            raise serializers.ValidationError(
                "Discount must be between 0 and 100."
            )

        return value

    def validate_features(self, value):

        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Features must be a list."
            )

        for item in value:

            if not isinstance(item, str):
                raise serializers.ValidationError(
                    "Each feature must be a string."
                )

        return value

    def get_final_price(self, obj):

        price = Decimal(obj.price)

        discount = Decimal(obj.discount)

        final_price = price - (
            price * discount / Decimal("100")
        )

        return float(final_price)



class SubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)
    payment_provider = serializers.CharField(read_only=True)

    apple_original_transaction_id = serializers.CharField(
        read_only=True
    )

    apple_transaction_id = serializers.CharField(
        read_only=True
    )  
    remaining_days = serializers.SerializerMethodField()
    is_trial = serializers.SerializerMethodField() 
    trial_remaining_days = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()  # override status dynamically
    is_active = serializers.SerializerMethodField()  # override is_active dynamically

    class Meta:
        model = Subscription
        fields = [
            "id",
            "user",
            "user_name",     
            "user_email",
            "plan",
            "plan_name",
            "payment_provider",
            "apple_original_transaction_id",
            "apple_transaction_id",
            "status",
            "is_active",
            "is_trial",
            "trial_remaining_days", 
            "start_date",
            "end_date",
            "remaining_days",
            "created_at",
        ]
        read_only_fields = (
            "id",
            "user",
            "status",
            "start_date",
            "end_date",
            "created_at",
            "user_name",
            "user_email",
            "plan_name",
            "is_trial",
        )


    def get_remaining_days(self, obj):
        remaining = (obj.end_date - timezone.now()).days
        return max(remaining, 0)
    
    def get_is_trial(self, obj):
        trial_period_days = 14
        trial_end_date = obj.start_date + timedelta(days=trial_period_days)
        return timezone.now() <= trial_end_date
    


    def get_trial_remaining_days(self, obj):
        trial_days = 14
        trial_end = obj.start_date + timedelta(days=trial_days)
        now = timezone.now()
        if now <= trial_end:
            return max((trial_end - now).days, 0)
        return None  # not a trial anymore

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user
        plan = attrs.get("plan")

        if user is None:
            raise serializers.ValidationError({"user": "User must be authenticated."})

        # Role validation
        if user.role not in ["client", "landscaper"]:
            raise serializers.ValidationError(
                {"user": "Only clients or landscapers can subscribe."}
            )

        # Plan active
        if not plan.is_active:
            raise serializers.ValidationError({"plan": "This plan is inactive."})

        # One active subscription per user
        if Subscription.objects.filter(user=user, status="active").exists():
            raise serializers.ValidationError(
                {"subscription": "User already has an active subscription."}
            )

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user
        plan = validated_data["plan"]

        start_date = timezone.now()
        duration_days = 30 if plan.duration == "monthly" else 365
        end_date = start_date + timedelta(days=duration_days)

        # Double-check before creating
        if Subscription.objects.filter(user=user, status="active").exists():
            raise serializers.ValidationError(
                {"subscription": "User already has an active subscription."}
            )
    def get_status(self, obj):
        if not obj.is_trial and obj.end_date < timezone.now():
            return "expired"  # Paid subscription expired
        return obj.status

    # -----------------------------
    # Dynamic is_active
    # -----------------------------
    def get_is_active(self, obj):
        if not obj.is_trial and obj.end_date < timezone.now():
            return False  # Paid subscription expired
        return obj.is_active


        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status="active",
            is_active=True,        
            start_date=start_date,
            end_date=end_date,
        )



class SubscriptionUpgradeSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    plan_price = serializers.DecimalField(source="plan.price", max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "user", "plan_name", "plan_price", "start_date", "end_date", "status", "auto_renew"]

        

# admin subscriptions 

# subscriptions/serializers.py
class AdminSubscriptionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    payment_provider = serializers.CharField(read_only=True)

    apple_original_transaction_id = serializers.CharField(
        read_only=True
    )

    apple_transaction_id = serializers.CharField(
        read_only=True
    )
    plan_price = serializers.DecimalField(
        source="plan.price",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    trial_remaining_days = serializers.SerializerMethodField()
    remaining_days = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "id",
            "user_email",
            "user_name",
            "plan_name",
            "payment_provider",
            "apple_original_transaction_id",
            "apple_transaction_id",
            "plan_price",
            "status",
            "is_active",
            "is_trial",
            "trial_remaining_days",
            "remaining_days",
            "start_date",
            "end_date",
            "is_expired",
            "created_at",
        ]

    def get_trial_remaining_days(self, obj):
        if obj.is_trial:
            remaining = (obj.end_date - timezone.now()).days
            return remaining if remaining > 0 else 0
        return None

    def get_remaining_days(self, obj):
        if not obj.is_trial:
            remaining = (obj.end_date - timezone.now()).days
            return remaining if remaining > 0 else 0
        return None

    def get_is_expired(self, obj):
        return obj.end_date < timezone.now()


class AdminLandscaperSubscriptionEditSerializer(serializers.ModelSerializer):
    plan_id = serializers.IntegerField(write_only=True, required=False)
    extend_trial_days = serializers.IntegerField(write_only=True, required=False, min_value=0)

    plan_name = serializers.CharField(source="plan.name", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    remaining_days = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "id",
            "user",
            "user_name",
            "user_email",
            "plan",
            "plan_name",
            "plan_id",
            "status",
            "is_active",
            "is_trial",
            "auto_renew",
            "discount_override",
            "trial_extended_days",
            "extend_trial_days",
            "start_date",
            "end_date",
            "remaining_days",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_name",
            "user_email",
            "plan",
            "plan_name",
            "trial_extended_days",
            "start_date",
            "end_date",
            "remaining_days",
        ]

    def get_remaining_days(self, obj):
        remaining = (obj.end_date - timezone.now()).days
        return max(remaining, 0)

    def validate_discount_override(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Discount must be between 0 and 100.")
        return value

    def validate_plan_id(self, value):
        plan = Plan.objects.filter(
            id=value,
            is_active=True,
            name__in=["Basic", "Pro"]
        ).first()

        if not plan:
            raise serializers.ValidationError("Selected plan is invalid.")
        return value

    def update(self, instance, validated_data):
        plan_id = validated_data.pop("plan_id", None)
        extend_trial_days = validated_data.pop("extend_trial_days", 0)

        if plan_id:
            plan = Plan.objects.get(id=plan_id, is_active=True)
            instance.plan = plan
            instance.start_date = timezone.now()

            if instance.is_trial:
                total_trial_days = 14 + instance.trial_extended_days + extend_trial_days
                instance.end_date = instance.start_date + timedelta(days=total_trial_days)
            else:
                instance.end_date = instance.start_date + timedelta(days=plan.duration_days)

        if "discount_override" in validated_data:
            instance.discount_override = validated_data["discount_override"]

        if "is_trial" in validated_data:
            instance.is_trial = validated_data["is_trial"]

        if "auto_renew" in validated_data:
            instance.auto_renew = validated_data["auto_renew"]

        if "status" in validated_data:
            instance.status = validated_data["status"]

        if "is_active" in validated_data:
            instance.is_active = validated_data["is_active"]

        if extend_trial_days:
            instance.trial_extended_days += extend_trial_days
            if instance.is_trial:
                total_trial_days = 14 + instance.trial_extended_days
                instance.end_date = instance.start_date + timedelta(days=total_trial_days)

        if not instance.is_trial:
            instance.end_date = instance.start_date + timedelta(days=instance.plan.duration_days)

        instance.save()
        return instance

    

from rest_framework import serializers
from .models import Plan, Subscription
from django.utils import timezone
from datetime import timedelta


class AdminPlanOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "price",
            "discount",
            "duration",
        ]

class SubscriptionLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(
        source="performed_by.email",
        read_only=True
    )

    class Meta:
        model = SubscriptionLog
        fields = [
            "id",
            "subscription",
            "action",
            "performed_by",
            "performed_by_name",
            "old_data",
            "new_data",
            "metadata",
            "reason",
            "level",
            "ip_address",
            "created_at",
        ]



class AppleVerifySerializer(serializers.Serializer):

    transaction_id = serializers.CharField(
        required=True,
        max_length=255
    )

    plan_id = serializers.IntegerField(
        required=True
    )

    def validate_transaction_id(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Apple transaction ID is required."
            )

        return value

    def validate_plan_id(self, value):

        if not Plan.objects.filter(
            id=value,
            is_active=True
        ).exists():

            raise serializers.ValidationError(
                "Invalid or inactive plan."
            )

        return value