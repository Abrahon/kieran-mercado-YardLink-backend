

from django.db import transaction
from narwhals.selectors import datetime
from .models import BusinessProfile,ClientCustomService
from services.serializers import ServiceSerializer
import json
from .models import Service
from rest_framework import serializers
from .models import WorkingHours, DAYS_OF_WEEK
import json
from .models import Addon
from services.models import Service  
from django.core.exceptions import ValidationError
from profiles.models import ClientProfile
from landscapers.models import BusinessProfile
from rest_framework import serializers
from subscriptions.helpers import get_landscaper_plan
from profiles.models import ClientProfile
from .models import ClientCustomService
from property.models import Property
from cloudinary.models import CloudinaryField
from rest_framework import serializers
from .models import ServiceQuote
from property.serializers import PropertySerializer
# from profiles.serializers import ClientProfileMiniSerializer
from landscapers.models import BusinessProfile
from decimal import Decimal, InvalidOperation




class BusinessLandscaperProfileSerializer(serializers.ModelSerializer):
    profile_image = serializers.ImageField(required=False, allow_null=True)
    insurance_doc = serializers.ImageField(required=False, allow_null=True)
    license_doc = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = BusinessProfile
        fields = [
            "id",
            "business_name",
            "business_email",
            "business_phone",
            "tagline",
            "description",
            "latitude",
            "longitude",
            "service_radius_km",
            "profile_image",
            "quickbooks_connected",
            "insurance_doc",
            "license_doc",
            "is_profile_completed",
        ]
        read_only_fields = ["is_profile_completed", "quickbooks_connected"]

    # -----------------------------
    # PLAN-BASED FIELD VALIDATION
    # -----------------------------
    def validate_profile_image(self, value):
        user = self.context["request"].user

        if get_landscaper_plan(user) == "basic":
            raise serializers.ValidationError(
                "Profile image is only available in Pro plan"
            )
        return value

    def validate(self, attrs):
        """
        Ensure only one of insurance_doc or license_doc is uploaded
        """
        insurance = attrs.get("insurance_doc") or getattr(self.instance, "insurance_doc", None)
        license_doc = attrs.get("license_doc") or getattr(self.instance, "license_doc", None)

        if insurance and license_doc:
            raise serializers.ValidationError(
                "You can upload either insurance OR license document, not both."
            )

        return attrs


    def validate_latitude(self, value):
        try:
            value = Decimal(str(value))
        except (InvalidOperation, TypeError):
            raise serializers.ValidationError("Invalid latitude value")

        if value < -90 or value > 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90")

        return value


    def validate_longitude(self, value):
        try:
            value = Decimal(str(value))
        except (InvalidOperation, TypeError):
            raise serializers.ValidationError("Invalid longitude value")

        if value < -180 or value > 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180")

        return value

    # -----------------------------
    # CREATE
    # -----------------------------
    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user

        if hasattr(user, "landscaper_profile"):
            raise serializers.ValidationError("Business profile already exists.")

        return BusinessProfile.objects.create(user=user, **validated_data)



    def update(self, instance, validated_data):
        # -----------------------------
        # Update business profile fields
        # -----------------------------
        instance.latitude = validated_data.get("latitude", instance.latitude)
        instance.longitude = validated_data.get("longitude", instance.longitude)

        profile_image = validated_data.get("profile_image")
        if profile_image is not None:
            instance.profile_image = profile_image

        instance.save()

        # -----------------------------
        # Update personal profile fields (LandscaperProfilies)
        # -----------------------------
        # Get or create personal profile
        personal_profile, created = LandscaperProfilies.objects.get_or_create(user=instance.user)

        name = validated_data.get("name")
        phone = validated_data.get("phone")
        if name is not None:
            personal_profile.name = name
        if phone is not None:
            personal_profile.phone = phone

        personal_profile.save()

        return instance

    def update(self, instance, validated_data):
        for field in [
            "business_name",
            "business_email",
            "business_phone",
            "tagline",
            "description",
            "latitude",
            "longitude",
            "service_radius_km",
            "profile_image",
            "insurance_doc",
            "license_doc",
        ]:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        instance.save()

        # Update personal profile if needed
        personal_profile, _ = LandscaperProfilies.objects.get_or_create(
            user=instance.user
        )

        if "name" in validated_data:
            personal_profile.name = validated_data["name"]

        if "phone" in validated_data:
            personal_profile.phone = validated_data["phone"]

        personal_profile.save()

        return instance




# serializers.py

from rest_framework import serializers


class ServiceSerializer(serializers.ModelSerializer):

    business = serializers.ReadOnlyField(
        source="business.id"
    )

    class Meta:
        model = Service

        fields = [
            "id",
            "business",
            "name",
            "description",
            "base_price",
            "pricing_type",
            "min_price",
            "is_active",
            "is_pinned",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "business",
            "created_at",
            "updated_at",
            "is_pinned",
        ]

    def validate_name(self, value):

        request = self.context.get("request")

        if not request:
            raise serializers.ValidationError(
                "Request context is missing."
            )

        user = request.user

        if not user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication required."
            )

        try:
            business = BusinessProfile.objects.get(user=user)

        except BusinessProfile.DoesNotExist:
            raise serializers.ValidationError(
                "You must have a business profile to create services."
            )

        # allow same name on update
        if self.instance and self.instance.name == value:
            return value

        exists = Service.objects.filter(
            business=business,
            name=value
        ).exclude(
            id=getattr(self.instance, "id", None)
        ).exists()

        if exists:
            raise serializers.ValidationError(
                "A service with this name already exists for your business."
            )

        return value

    def validate(self, attrs):

        pricing_type = attrs.get(
            "pricing_type",
            getattr(self.instance, "pricing_type", None)
        )

        base_price = attrs.get(
            "base_price",
            getattr(self.instance, "base_price", None)
        )

        min_price = attrs.get(
            "min_price",
            getattr(self.instance, "min_price", None)
        )

        # FIXED pricing validation
        if pricing_type == Service.PricingType.FIXED:

            if base_price is None:
                raise serializers.ValidationError(
                    {
                        "base_price": "Fixed pricing requires base_price."
                    }
                )

            attrs["min_price"] = None

        # REQUEST pricing validation
        if pricing_type == Service.PricingType.REQUEST:

            if base_price is not None:
                raise serializers.ValidationError(
                    {
                        "base_price": "Request pricing should not include base_price."
                    }
                )

            if min_price is None:
                raise serializers.ValidationError(
                    {
                        "min_price": "Request pricing requires min_price."
                    }
                )

        return attrs

# -------------------------
# CLIENT (FULL PROFILE)


class ClientProfileMiniSerializer(serializers.ModelSerializer):

    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = ClientProfile
        fields = ["id", "name", "email"]

# from rest_framework import serializers
from profiles.models import LandscaperProfilies


class LandscaperProfileMiniSerializer(serializers.ModelSerializer):

    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = LandscaperProfilies
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "profile_image",
        ]


# -------------------------
# MAIN SERIALIZER
# -------------------------

class ClientCustomServiceSerializer(serializers.ModelSerializer):

    client = ClientProfileMiniSerializer(read_only=True)

    landscaper = serializers.PrimaryKeyRelatedField(
        queryset=BusinessProfile.objects.all()
    )

    property = PropertySerializer(read_only=True)

    booking_id = serializers.ReadOnlyField(source="booking.id")

    class Meta:
        model = ClientCustomService
        fields = [
            "id",
            "client",
            "landscaper",
            "property",

            "name",
            "description",
            "note",
            "price",
            "status",
            "is_active",

            "preferred_date",
            "preferred_time",

            "recurring_type",
            "recurring_day_of_week",

            "booking_id",
            "created_at",
            "updated_at"
        ]


class AddonSerializer(serializers.ModelSerializer):
    business = serializers.ReadOnlyField(source="business.id")
    applicable_services = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Service.objects.all()
    )

    class Meta:
        model = Addon
        fields = [
            "id",
            "business",
            "name",
            "price",
            "applicable_services",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "business", "created_at", "updated_at"]

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price must be zero or positive.")
        return value

    def validate_applicable_services(self, services):
        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Request context not available.")

        try:
            business = request.user.landscaper_profile  
        except BusinessProfile.DoesNotExist:
            raise serializers.ValidationError("Landscaper profile not found.")

        # Ensure all services belong to this business
        for service in services:
            if service.business != business:
                raise serializers.ValidationError(
                    f"Service '{service.name}' does not belong to your business."
                )
        return services



# client
class PublicServiceSerializer(serializers.ModelSerializer):
    business_id = serializers.IntegerField(source="business.id", read_only=True)
    business_name = serializers.CharField(source="business.business_name", read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "business_id",
            "business_name",
            "name",
            "description",
            "base_price",
            "pricing_type",
            "min_price",
            "is_active",
        ]


class PublicAddonSerializer(serializers.ModelSerializer):
    business_id = serializers.IntegerField(source="business.id", read_only=True)
    business_name = serializers.CharField(source="business.business_name", read_only=True)

    class Meta:
        model = Addon
        fields = [
            "id",
            "business_id",
            "business_name",
            "name",
            "price",
            "is_active",
        ]

# # landscapers/serializers.py
class WorkingHoursSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(source='get_day_display', read_only=True)

    class Meta:
        model = WorkingHours
        fields = ['id', 'day', 'day_display', 'start_time', 'end_time']




class StandardServiceSerializer(serializers.ModelSerializer):
    # Input in minutes
    time = serializers.IntegerField(
        write_only=True, required=True, help_text="Time in minutes"
    )

    class Meta:
        model = Service
        fields = [
            "id",
            "standard_service",
            "description",
            "price",
            "rate_type",
            "latitude",
            "longitude",
            "time",       # input in minutes
            "is_active",
            "is_pinned",
        ]
        read_only_fields = ["is_active","is_pinned"]

    def create(self, validated_data):
        minutes = validated_data.pop("time")
        validated_data["time"] = round(minutes / 60, 2)  
        validated_data["category"] = Service.CategoryChoices.STANDARD
        validated_data["is_active"] = True
        validated_data["is_pinned"] = False 
        return super().create(validated_data)

    def update(self, instance, validated_data):
        minutes = validated_data.pop("time", None)
        if minutes is not None:
            validated_data["time"] = round(minutes / 60, 2)
        validated_data["category"] = Service.CategoryChoices.STANDARD
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["time"] = float(instance.time)  # display in hours
        return rep




# serializers.py
from jobs.models import Job

class ServiceQuoteSerializer(serializers.ModelSerializer):

    client = ClientProfileMiniSerializer(read_only=True)

    # ✅ FULL SERVICE RESPONSE
    service = ServiceSerializer(read_only=True)

    # ✅ FULL PROPERTY RESPONSE
    property = PropertySerializer(read_only=True)

    # ✅ INPUT FIELD
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(),
        source="property",
        write_only=True
    )

    # ✅ INPUT FIELD
    service_id = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        source="service",
        write_only=True
    )
    request_type = serializers.SerializerMethodField()  # ✅ ADD HERE
    landscaper = serializers.SerializerMethodField()

    class Meta:
        model = ServiceQuote

        fields = [
            "id",

            # SERVICE
            "service",
            "service_id",

            # CLIENT
            "client",

            # LANDSCAPER
            "landscaper",

            # PROPERTY
            "property",
            "property_id",

            # MESSAGE
            "message",


            # LANDSCAPER CONFIRMED
            "scheduled_date",
            "scheduled_time",

            # PRICE
            "price",
            "request_type",  # ✅ ADD TO FIELDS
            # STATUS
            "status",

            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "client",
            "landscaper",
            "price",
            "status",
            "created_at",
            "updated_at",
        ]

    # =====================================
    # LANDSCAPER INFO (FIXED)
    # =====================================

    def get_landscaper(self, obj):
        landscaper = obj.landscaper

        if not landscaper:
            return None

        user = landscaper.user
        profile = getattr(user, "landscaperprofilies", None)

        return {
            "id": landscaper.id,

            # ✅ FIX HERE (IMPORTANT)
            "name": user.name or getattr(profile, "name", None),

            "email": user.email,

            "phone": getattr(profile, "phone", None),
            "address": getattr(profile, "address", None),

            "profile_image": (
                profile.profile_image.url
                if profile and getattr(profile, "profile_image", None)
                else None
            ),
        }
    def get_request_type(self, obj):
        return getattr(obj, "request_type", "quote_request")
    # =====================================
    # VALIDATION
    # =====================================


    # =============================================================
    # INTERCEPT & PARSE THE TIME RANGE STRING BEFORE DRF VALIDATION
    # =============================================================
    def validate_scheduled_time(self, value):
        # If the frontend sent the "09:00 AM - 10:00 AM" format, DRF will pass it 
        # as a string or fail. We grab the raw initial data to parse it cleanly.
        raw_time = self.initial_data.get("scheduled_time")
        
        if raw_time and isinstance(raw_time, str) and " - " in raw_time:
            from datetime import datetime
            try:
                # Extract the first part: "09:00 AM"
                start_time_str = raw_time.split(" - ")[0].strip()
                # Safely transform it into a true Python time object
                return datetime.strptime(start_time_str, "%I:%M %p").time()
            except ValueError:
                raise serializers.ValidationError("Time format must match 'HH:MM AM/PM - HH:MM AM/PM'.")
        
        # If it's already a proper time format or object, return it as-is
        return value
    def validate(self, data):
            # 1. Run your initial create validation logic (pricing type check)
            data = super().validate(data)

            # =============================================================
            # IF CREATING: SKIP UPDATE CONTROLS COMPLETELY
            # =============================================================
            if not self.instance:
                return data

            # =============================================================
            # IF UPDATING: RUN ROLE & AVAILABILITY CONTROLS
            # =============================================================
            request = self.context.get("request")
            user = request.user if request else None
            quote = self.instance
            landscaper_profile = quote.landscaper

            if not user:
                raise serializers.ValidationError({"error": "Authentication credentials are required."})

            # Match how your view/models fetch profiles
            user_landscaper_profile = getattr(user, "landscaperprofile", None) or getattr(user, "landscaperprofilies", None)
            
            is_landscaper = user_landscaper_profile == landscaper_profile or (
                hasattr(landscaper_profile, "user") and landscaper_profile.user == user
            )
            is_client = getattr(user, "clientprofile", None) == quote.client

            if not is_landscaper and not is_client:
                raise serializers.ValidationError({"error": "You do not have permission to modify this quote."})

            if is_client and not is_landscaper:
                restricted_fields = ["price", "scheduled_date", "scheduled_time"]
                if any(field in data for field in restricted_fields):
                    raise serializers.ValidationError({
                        "error": "Clients are not authorized to modify price or schedules directly."
                    })

            # Extract incoming dates
            new_date = data.get("scheduled_date") if "scheduled_date" in data else quote.scheduled_date
            
            # =============================================================
            # ✅ FIX: PARSE "09:00 AM - 10:00 AM" STRING RANGE INTO TIME OBJECT
            # =============================================================
            raw_time = self.initial_data.get("scheduled_time")
            if raw_time and isinstance(raw_time, str) and " - " in raw_time:
                from datetime import datetime
                try:
                    # Extract the first part: "09:00 AM"
                    start_time_str = raw_time.split(" - ")[0].strip()
                    # Parse to datetime object, then convert to time object
                    parsed_time = datetime.strptime(start_time_str, "%I:%M %p").time()
                    data["scheduled_time"] = parsed_time
                    new_time = parsed_time
                except ValueError:
                    raise serializers.ValidationError({"scheduled_time": "Time format must match 'HH:MM AM/PM - HH:MM AM/PM'."})
            else:
                new_time = data.get("scheduled_time") if "scheduled_time" in data else quote.scheduled_time

            # Only enforce availability if BOTH date and time are set
            if new_date and new_time:
                from datetime import date
                
                if new_date < date.today():
                    raise serializers.ValidationError({"scheduled_date": "Scheduled date cannot be in the past."})

                weekday = new_date.strftime("%A").upper()
                
                # Check if this exact start time exists as a valid working hour shift
                shift_exists = WorkingHours.objects.filter(
                    landscaper=landscaper_profile,
                    day=weekday,
                    start_time=new_time,
                    is_active=True
                ).exists()

                if not shift_exists:
                    raise serializers.ValidationError({
                        "scheduled_time": f"This time slot is not within the landscaper's working hours for {weekday.title()}."
                    })

                active_jobs_today = Job.objects.filter(
                    landscaper=landscaper_profile,
                    scheduled_date=new_date,
                    is_active=True,
                    status__in=["upcoming", "in_progress"]
                )
                
                if active_jobs_today.count() >= 5:
                    raise serializers.ValidationError({
                        "scheduled_date": "The landscaper has reached their maximum daily job limit for this date."
                    })

                if active_jobs_today.filter(scheduled_time=new_time).exists():
                    raise serializers.ValidationError({
                        "scheduled_time": "This specific time slot has already been booked by an active job."
                    })

            return data
    # =====================================
    # CREATE FUNCTION
    # =====================================
    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError({"error": "Authentication required."})

        # Safeguard: Verify the user making the request is actually a client
        client = getattr(request.user, "clientprofile", None)
        if not client:
            raise serializers.ValidationError({
                "client": "You must have a Client Profile to submit a quote request."
            })

        service = validated_data["service"]

        # Automatically assign backend-managed fields
        validated_data["client"] = client
        validated_data["landscaper"] = service.business
        validated_data["status"] = ServiceQuote.Status.PENDING
        validated_data["price"] = None

        return ServiceQuote.objects.create(**validated_data)

    # =====================================
    # UPDATE FUNCTION
    # =====================================
    def update(self, instance, validated_data):
        """
        Handles updating quotes while keeping core relationships locked down.
        """
        # Prevent rewriting relationships after the quote is already created
        validated_data.pop("client", None)
        validated_data.pop("service", None)
        validated_data.pop("property", None)

        return super().update(instance, validated_data)