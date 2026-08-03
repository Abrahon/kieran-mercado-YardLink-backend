from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from .serializers import BusinessLandscaperProfileSerializer
from subscriptions.models import Subscription
from rest_framework.exceptions import NotFound
from datetime import date, timedelta
from django.db.models import Q
from bookings.models import ServiceBooking
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from .models import Addon
from profiles.models import LandscaperProfilies
from .serializers import AddonSerializer
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.response import Response
from django.db import IntegrityError, transaction
from django.core.exceptions import ObjectDoesNotExist
# landscapers/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import WorkingHours, DAYS_OF_WEEK
from .serializers import WorkingHoursSerializer,ServiceSerializer,ServiceQuoteSerializer
from bookings.models import BookingStatus
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from services.permissions import IsLandscaper
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Service,BusinessProfile
from django.db.models import F, Avg
from django.db.models.functions import ACos, Cos, Sin, Radians
from django.db.models import Q
from django.db.models import Count, Avg, Q
from rest_framework import generics, status
# from .serializers import UpdateServiceSerializer
from bookings.models import BookingRequest, BookingRequestItem
from rest_framework.exceptions import PermissionDenied
from landscapers.models import BusinessProfile
from accounts.models import User
from accounts.enums import RoleChoices
from profiles.models import LandscaperProfilies
from reviews.models import LandscaperReview
from connections.models import ConnectionRequest
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from rest_framework.exceptions import APIException
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils.timezone import now
from django.db.models.functions import TruncMonth
from django.db.models import Count
from .models import Service
from datetime import datetime, timedelta
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied
from rest_framework import generics
from rest_framework.exceptions import ValidationError, PermissionDenied, APIException
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from common.permissions import IsLandscaper
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from .models import Service, BusinessProfile
from .serializers import ServiceSerializer
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from .models import Service
from .serializers import StandardServiceSerializer
from django.db.models import Avg, Count, Q
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from .models import ClientCustomService
from profiles.models import ClientProfile
from .serializers import ClientCustomServiceSerializer
from common .permissions import IsLandscaper
from decimal import Decimal, InvalidOperation
from django.db import transaction
from bookings.models import BookingRequest
from property.models import Property
from profiles.serializers import ClientProfileSerializer
from rest_framework.decorators import api_view, permission_classes
from .serializers import PublicServiceSerializer, PublicAddonSerializer
from django.db import transaction
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from django.utils.dateparse import parse_date, parse_time
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import ServiceQuote
from .serializers import ServiceQuoteSerializer
from decimal import Decimal
from django.db import transaction
from rest_framework.response import Response
from rest_framework import generics, permissions
from django.db import transaction
from django.db.models import Sum
from decimal import Decimal
from jobs.models import Job, JobItem
from .models import ServiceQuote
from .serializers import ServiceQuoteSerializer

from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from .models import ServiceQuote
from .serializers import ServiceQuoteSerializer
from subscriptions.helpers import can_use_pro_features, get_landscaper_plan

from rest_framework import generics, permissions, serializers
from django.db import IntegrityError
from landscapers.models import Addon, BusinessProfile











# =========================
# CREATE BUSINESS PROFILE
# =========================

class CompleteLandscaperProfileView(generics.CreateAPIView):
    serializer_class = BusinessLandscaperProfileSerializer
    permission_classes = [IsLandscaper]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        user = self.request.user

        #  already exists check
        if BusinessProfile.objects.filter(user=user).exists():
            raise ValidationError({"detail": "Business profile already exists."})

        # 🧠 PLAN CHECK
        plan = get_landscaper_plan(user)

        # -----------------------------
        # BASIC PLAN RESTRICTIONS
        # -----------------------------
        if plan == "basic":
            # restrict pro-only fields if they are in request
            if self.request.FILES.get("profile_image"):
                raise ValidationError({
                    "detail": "Profile image is only available in Pro plan."
                })

            # you can also restrict other fields here later

        # -----------------------------
        # SAVE PROFILE
        # -----------------------------
        try:
            with transaction.atomic():
                serializer.context["user"] = user
                serializer.save()

        except Exception as e:
            raise APIException(f"Business profile creation failed: {str(e)}")


# =========================
# UPDATE BUSINESS PROFILE
# =========================

class UpdateBusinessProfileView(generics.UpdateAPIView):
    serializer_class = BusinessLandscaperProfileSerializer
    permission_classes = [IsAuthenticated, IsLandscaper]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        profile = getattr(self.request.user, "landscaper_profile", None)

        if not profile:
            raise ValidationError("Business profile not found for this user.")

        return profile




# =========================
# GET BUSINESS PROFILE

class GetBusinessProfileView(generics.RetrieveAPIView):
    serializer_class = BusinessLandscaperProfileSerializer
    permission_classes = [IsAuthenticated, IsLandscaper]

    def get_object(self):
        profile = getattr(self.request.user, "landscaper_profile", None)

        if not profile:
            raise ValidationError("Business profile not found for this user.")

        return profile







class ServiceListCreateView(generics.ListCreateAPIView):
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # -------------------------
        # CLIENT: See all services
        # -------------------------
        if hasattr(user, "clientprofile"):
            queryset = Service.objects.all()

        # -------------------------
        # LANDSCAPER: See own services
        # -------------------------
        elif hasattr(user, "landscaper_profile"):
            queryset = Service.objects.filter(
                business=user.landscaper_profile
            )

        else:
            return Service.objects.none()

        # -------------------------
        # SEARCH PARAMS
        # -------------------------
        search = self.request.query_params.get("search")
        min_price = self.request.query_params.get("min_price")
        max_price = self.request.query_params.get("max_price")

        # -------------------------
        # NAME SEARCH
        # -------------------------
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
            )

        # -------------------------
        # PRICE FILTER
        # -------------------------
        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        return queryset

    def perform_create(self, serializer):
        business = getattr(
            self.request.user,
            "landscaper_profile",
            None
        )

        if not business:
            raise PermissionDenied(
                "Only landscapers can create services."
            )

        serializer.save(business=business)



class ServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ServiceSerializer
    permission_classes = [IsLandscaper]

    def get_queryset(self):
        try:
            business = self.request.user.landscaper_profile
        except BusinessProfile.DoesNotExist:
            return Service.objects.none()
        return Service.objects.filter(business=business)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)  # supports PATCH
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        try:
            with transaction.atomic():
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)
        except ValidationError as ve:
            return Response(
                {"success": False, "message": "Update failed.", "errors": ve.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"success": False, "message": f"Update failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"success": True, "message": "Service updated successfully.", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {
                "success": True,
                "message": "Service deleted successfully."
            },
            status=status.HTTP_200_OK
        )



# select clinet landscaper service 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_landscaper_services(request, landscaper_id):

    # -----------------------------
    # GET LANDSCAPER BUSINESS PROFILE
    # -----------------------------
    business = get_object_or_404(
        BusinessProfile,
        user_id=landscaper_id
    )

    # -----------------------------
    # GET SERVICES
    # -----------------------------
    services = Service.objects.filter(
        business=business,
        is_active=True
    ).order_by("-is_pinned", "-created_at")

    serializer = ServiceSerializer(
        services,
        many=True,
        context={"request": request}
    )

    return Response({
        "landscaper_id": landscaper_id,
        "business_id": business.id,
        "business_name": business.business_name,
        "count": services.count(),
        "services": serializer.data
    })



class ServiceAddonListView(generics.ListAPIView):
    serializer_class = PublicAddonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        service_id = self.kwargs.get("service_id")
        return Addon.objects.filter(
            applicable_services__id=service_id,
            is_active=True
        ).select_related("business").distinct().order_by("name")







# ================================
# Client Views
# ================================


class ClientCustomServiceListCreateView(generics.ListCreateAPIView):
    serializer_class = ClientCustomServiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        client = getattr(self.request.user, "clientprofile", None)
        if not client:
            return ClientCustomService.objects.none()

        return (
            ClientCustomService.objects.filter(
                client=client,
                is_active=True
            )
            .select_related(
                "client__user",
                "property",
                "landscaper__user"
            )
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        client = getattr(self.request.user, "clientprofile", None)

        if not client:
            raise PermissionDenied("Client profile not found.")

        property_id = self.request.data.get("property")

        if not property_id:
            raise serializers.ValidationError({
                "property": "Property is required."
            })

        landscaper_id = self.request.data.get("landscaper")

        if not landscaper_id:
            raise serializers.ValidationError({
                "landscaper": "Landscaper is required."
            })

        serializer.save(
            client=client,
            property_id=property_id,
            landscaper_id=landscaper_id,
            status="pending",
            price=None
        )



class ClientCustomServiceRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    """
    GET    -> client retrieves one of their own service requests
    DELETE -> client deletes only if request is still pending
    """
    serializer_class = ClientCustomServiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        client = getattr(self.request.user, "clientprofile", None)
        if not client:
            return ClientCustomService.objects.none()
        return ClientCustomService.objects.filter(
            client=client,
            is_active=True
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != "pending":
            return Response(
                {"error": "Only pending requests can be deleted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.delete()
        return Response(
            {"message": "Service request deleted successfully."},
            status=status.HTTP_200_OK
        )
    



class ClientAcceptedServiceListView(generics.ListAPIView):
    """
    Client sees all accepted services waiting for confirmation
    """
    serializer_class = ClientCustomServiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        client = getattr(self.request.user, "clientprofile", None)

        if not client:
            return ClientCustomService.objects.none()

        return (
            ClientCustomService.objects.filter(
                client=client,
                status="accepted",
                is_active=True
            )
            .select_related(
                "landscaper__user",
                "property",
                "client__user"
            )
            .order_by("-created_at")
        )



@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def client_confirm_service(request, pk):
    action = request.data.get("action")

    if action not in ["confirm", "decline"]:
        return Response({"error": "Invalid action."}, status=400)

    client = getattr(request.user, "clientprofile", None)
    if not client:
        return Response({"error": "Client profile not found."}, status=403)

    try:
        service = ClientCustomService.objects.get(
            pk=pk,
            client=client,
            is_active=True
        )
    except ClientCustomService.DoesNotExist:
        return Response({"error": "Service not found."}, status=404)

    if service.status != "accepted":
        return Response({"error": "Service is not ready for confirmation."}, status=400)

    # -------------------------
    # DECLINE FLOW
    # -------------------------
    if action == "decline":
        service.status = "declined"
        service.save(update_fields=["status", "updated_at"])

        return Response({
            "message": "Service declined successfully.",
            "status": service.status
        }, status=200)

    # -------------------------
    # CONFIRM FLOW
    # -------------------------
    if not service.preferred_date:
        return Response(
            {"error": "Landscaper has not set schedule yet."},
            status=400
        )

    with transaction.atomic():
        service = ClientCustomService.objects.select_for_update().get(
            pk=pk,
            client=client,
            is_active=True
        )

        if not service.landscaper:
            return Response(
                {"error": "No landscaper assigned to this service."},
                status=400
            )

        if service.recurring_type == "weekly":
            booking_type = BookingRequest.BookingType.WEEKLY
        elif service.recurring_type == "biweekly":
            booking_type = BookingRequest.BookingType.BIWEEKLY
        elif service.recurring_type:
            booking_type = BookingRequest.BookingType.CUSTOM
        else:
            booking_type = BookingRequest.BookingType.ONE_TIME

        booking = BookingRequest.objects.create(
            client=service.client,
            landscaper=service.landscaper,
            property=service.property,
            service=None,
            description=f"{service.name}\n\n{service.description or ''}".strip(),
            booking_type=booking_type,
            recurring_day_of_week=service.recurring_day_of_week,
            scheduled_date=service.preferred_date,
            scheduled_time=service.preferred_time,
            price=service.price,
            note=service.note,
            status=BookingRequest.Status.PENDING,
            is_active=True
        )

        # =========================
        # 🔥 CREATE BOOKING ITEMS (FIX)
        # =========================
        BookingRequestItem.objects.create(
            booking=booking,
            item_type=BookingRequestItem.ItemType.CUSTOM,
            name=service.name,
            description=service.description or "",
            price=service.price or 0,
            sort_order=0
        )

        service.status = "confirmed"
        service.booking = booking
        service.save(update_fields=["status", "booking", "updated_at"])
    return Response({
        "message": "Service confirmed successfully.",
        "status": service.status,
        "booking_id": booking.id,
        "custom_service": ClientCustomServiceSerializer(service).data,
        "client": ClientProfileSerializer(client).data
    }, status=status.HTTP_200_OK)




# ================================
# Landscaper Views
# ================================


class LandscaperCustomServicePendingListView(generics.ListAPIView):
    """
    Landsacaper sees all pending custom service requests
    """
    serializer_class = ClientCustomServiceSerializer
    permission_classes = [IsAuthenticated, IsLandscaper]

    def get_queryset(self):
        user = self.request.user

        try:
            landscaper_profile = user.landscaper_profile
        except AttributeError:
            return ClientCustomService.objects.none()

        return (
            ClientCustomService.objects.filter(
                landscaper=landscaper_profile,
                status="pending",
                is_active=True
            )
            .select_related(
                "client__user",   # important for client serializer
                "property" ,
                "landscaper__user"       # important for property serializer
            )
            .order_by("-created_at")
        )




from django.utils.dateparse import parse_date, parse_time
@api_view(["PATCH"])
@permission_classes([IsLandscaper])
def landscaper_accept_service(request, pk):

    price = request.data.get("price")
    scheduled_date_str = request.data.get("scheduled_date")
    scheduled_time_str = request.data.get("scheduled_time")

    if price is None:
        return Response({"error": "Price is required."}, status=400)

    try:
        price = Decimal(str(price))
        if price <= 0:
            return Response({"error": "Price must be greater than 0."}, status=400)
    except Exception:
        return Response({"error": "Invalid price format."}, status=400)

    landscaper = getattr(request.user, "landscaper_profile", None)
    if not landscaper:
        return Response({"error": "Landscaper profile not found."}, status=403)

    try:
        service = ClientCustomService.objects.get(
            pk=pk,
            landscaper=landscaper,
            status="pending",
            is_active=True
        )
    except ClientCustomService.DoesNotExist:
        return Response({"error": "Pending service not found."}, status=404)

    # ✅ APPLY DATE & TIME FOR BOTH TYPES
    scheduled_date = parse_date(scheduled_date_str) if scheduled_date_str else None
    scheduled_time = parse_time(scheduled_time_str) if scheduled_time_str else None

    if scheduled_date:
        service.preferred_date = scheduled_date

    if scheduled_time:
        service.preferred_time = scheduled_time

    # SAVE
    service.price = price
    service.status = "accepted"
    service.save()

    return Response({
        "message": "Service accepted and schedule set successfully.",
        "service_id": service.id,
        "price": str(service.price),
        "status": service.status,
        "scheduled_date": service.preferred_date,
        "scheduled_time": service.preferred_time,
    }, status=200)



# accepet client custom service landscaper
# @api_view(["PATCH"])
# @permission_classes([IsLandscaper])
# def landscaper_accept_service(request, pk):
#     """
#     Accepts custom service and sets price & scheduled date/time
#     """
#     price = request.data.get("price")
#     scheduled_date = request.data.get("scheduled_date")
#     scheduled_time = request.data.get("scheduled_time")

#     if not price:
#         return Response({"error": "Price is required."}, status=400)

#     try:
#         price = Decimal(price)
#         if price <= 0:
#             raise Response({"error": "Price must be > 0"}, status=400)
#     except:
#         return Response({"error": "Invalid price format"}, status=400)

#     service = ClientCustomService.objects.filter(pk=pk, status="pending").first()
#     if not service:
#         return Response({"error": "Pending service not found"}, status=404)

#     service.price = price
#     service.scheduled_date = scheduled_date
#     service.scheduled_time = scheduled_time
#     service.status = "accepted"
#     service.save()

#     return Response({
#         "message": "Service accepted with price & scheduled time.",
#         "service_id": service.id,
#         "price": str(service.price),
#         "scheduled_date": service.scheduled_date,
#         "scheduled_time": service.scheduled_time,
#         "status": service.status
#     })


# active inactive

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def toggle_client_custom_service_active(request, pk):
    try:
        # ✅ Correct attribute: clientprofile
        service = ClientCustomService.objects.get(pk=pk, client=request.user.clientprofile)
    except ClientCustomService.DoesNotExist:
        return Response({"error": "Service not found"}, status=404)

    service.is_active = not service.is_active
    service.save()

    return Response({
        "message": "Custom service status updated.",
        "id": service.id,
        "name": service.name,
        "is_active": service.is_active
    })




class AddonListCreateView(generics.ListCreateAPIView):
    serializer_class = AddonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        business = getattr(self.request.user, "landscaper_profile", None)
        if not business:
            return Addon.objects.none()
        return Addon.objects.filter(business=business)

    def perform_create(self, serializer):
        business = getattr(self.request.user, "landscaper_profile", None)
        if not business:
            raise serializers.ValidationError({"error": "Landscaper profile not found."})

        try:
            serializer.save(business=business)
        except IntegrityError as e:
            # Check if it is the unique constraint error
            if "unique_addon_per_business" in str(e):
                raise serializers.ValidationError({
                    "error": "Addon with this name already exists for your business."
                })
            # Re-raise any other database errors
            raise e



class AddonDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddonSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        try:
            business = self.request.user.landscaper_profile
            return Addon.objects.filter(business=business)
        except ObjectDoesNotExist:
            return Addon.objects.none()

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return Response(
            {
                "message": "Addon updated successfully.",
                "data": response.data
            },
            status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Soft delete instead of hard delete
        instance.is_active = False
        instance.save()

        return Response(
            {"message": "Addon deactivated successfully."},
            status=status.HTTP_200_OK
        )




# # set working hours for landscapers



class WorkingHoursListCreateView(generics.ListCreateAPIView):
    serializer_class = WorkingHoursSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):

        profile = BusinessProfile.objects.filter(
            user=self.request.user
        ).first()

        # ===========================
        # LANDSCAPER VIEW
        # ===========================
        if profile:
            return WorkingHours.objects.filter(
                landscaper=profile
            ).order_by("day", "start_time")

        # ===========================
        # CLIENT VIEW
        # ===========================
        return WorkingHours.objects.filter(
            is_active=True
        ).order_by("day", "start_time")

    @transaction.atomic
    def create(self, request, *args, **kwargs):

        try:
            profile = BusinessProfile.objects.get(
                user=request.user
            )

        except BusinessProfile.DoesNotExist:
            return Response(
                {"detail": "Business profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        data = request.data

        days = data.get("days")
        start_time = data.get("start_time")
        end_time = data.get("end_time")

        # validate days
        if not days:
            return Response(
                {"error": "days field is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # convert single string to list
        if isinstance(days, str):
            days = [days]

        VALID_DAYS = [d[0] for d in DAYS_OF_WEEK]

        # validate time format
        try:
            start_time_obj = datetime.strptime(
                start_time,
                "%H:%M"
            ).time()

            end_time_obj = datetime.strptime(
                end_time,
                "%H:%M"
            ).time()

        except Exception:
            return Response(
                {
                    "error":
                    "Invalid time format. Use HH:MM"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # validate range
        if start_time_obj >= end_time_obj:
            return Response(
                {
                    "error":
                    "End time must be greater than start time."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        created_slots = []
        errors = []

        for day in days:

            # validate day
            if day not in VALID_DAYS:
                errors.append({
                    "day": day,
                    "detail": "Invalid day"
                })
                continue

            # overlap check
            overlapping = WorkingHours.objects.filter(
                landscaper=profile,
                day=day,
                is_active=True,
                start_time__lt=end_time_obj,
                end_time__gt=start_time_obj
            )

            if overlapping.exists():
                errors.append({
                    "day": day,
                    "detail": "Slot overlaps existing slot"
                })
                continue

            # create slot
            slot = WorkingHours.objects.create(
                landscaper=profile,
                day=day,
                start_time=start_time_obj,
                end_time=end_time_obj
            )

            created_slots.append(slot)

        serializer = self.get_serializer(
            created_slots,
            many=True
        )

        return Response(
            {
                "created_slots": serializer.data,
                "errors": errors
            },
            status=status.HTTP_201_CREATED
        )

# update


class WorkingHoursUpdateView(generics.UpdateAPIView):
    serializer_class = WorkingHoursSerializer
    permission_classes = [permissions.IsAuthenticated, IsLandscaper]

    def get_queryset(self):
        profile = BusinessProfile.objects.filter(
            user=self.request.user
        ).first()

        if not profile:
            return WorkingHours.objects.none()

        return WorkingHours.objects.filter(
            landscaper=profile
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # parse safely
        day = request.data.get("day", instance.day)
        start_time = parse_time(
            request.data.get("start_time")
        ) or instance.start_time

        end_time = parse_time(
            request.data.get("end_time")
        ) or instance.end_time

        # validate time range
        if start_time >= end_time:
            return Response(
                {"error": "End time must be greater than start time"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # overlap check (only active)
        overlap = WorkingHours.objects.filter(
            landscaper=instance.landscaper,
            day=day,
            is_active=True,
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exclude(id=instance.id)

        if overlap.exists():
            return Response(
                {"error": "Slot overlaps with existing slot"},
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.day = day
        instance.start_time = start_time
        instance.end_time = end_time
        instance.save()

        serializer = self.get_serializer(instance)

        return Response({
            "message": "Working hours updated successfully",
            "data": serializer.data
        })
# deleet
class WorkingHoursDeleteView(generics.DestroyAPIView):
    serializer_class = WorkingHoursSerializer
    permission_classes = [permissions.IsAuthenticated, IsLandscaper]

    def get_queryset(self):
        profile = BusinessProfile.objects.filter(user=self.request.user).first()
        if not profile:
            return WorkingHours.objects.none()

        return WorkingHours.objects.filter(landscaper=profile)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()

        return Response(
            {"message": "Working hour slot deleted successfully."},
            status=status.HTTP_200_OK
        )
 
# active dective

@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated, IsLandscaper])
def toggle_working_hour(request, pk):

    try:
        profile = BusinessProfile.objects.get(user=request.user)

        slot = WorkingHours.objects.get(
            id=pk,
            landscaper=profile
        )

    except WorkingHours.DoesNotExist:
        return Response(
            {"error": "Slot not found"},
            status=404
        )

    slot.is_active = not slot.is_active
    slot.save()

    return Response({
        "message": "Slot status updated",
        "is_active": slot.is_active
    })


# views.py



# 4️⃣ Toggle active/inactive
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def toggle_service_active(request, pk):
    try:
        service = Service.objects.get(pk=pk, business__user=request.user)
    except Service.DoesNotExist:
        return Response({"error": "Service not found"}, status=404)

    service.is_active = not service.is_active
    service.save()
    return Response({
        "id": service.id,
        "name": service.name,          # updated from standard_service
        "is_active": service.is_active
    })


# service stats 
class ServiceStatsAPIView(APIView):
    """
    Returns statistics for logged-in landscaper's services.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ✅ get landscaper profile
        landscaper = getattr(request.user, "landscaper_profile", None)

        if not landscaper:
            return Response(
                {"error": "Landscaper profile not found."},
                status=status.HTTP_403_FORBIDDEN
            )

        # ✅ FIX: use business instead of landscaper
        queryset = Service.objects.filter(business=landscaper)

        stats = queryset.aggregate(
            total_services=Count("id"),
            active_services=Count("id", filter=Q(is_active=True)),
            pinned_services=Count("id", filter=Q(is_pinned=True)),

            # ✅ FIX: correct price field
            average_price=Avg("base_price")
        )

        return Response(
            {
                "total_services": stats["total_services"] or 0,
                "active_services": stats["active_services"] or 0,
                "pinned_services": stats["pinned_services"] or 0,
                "average_price": round(float(stats["average_price"] or 0), 2),
            },
            status=status.HTTP_200_OK
        )



# for client list vailabe data
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_landscaper_available_dates(request, landscaper_id):

    try:
        landscaper = BusinessProfile.objects.get(id=landscaper_id)
    except BusinessProfile.DoesNotExist:
        return Response({"error": "Landscaper not found"}, status=404)

    working_days = WorkingHours.objects.filter(
        landscaper=landscaper,
        is_active=True
    ).values_list("day", flat=True)

    if not working_days:
        return Response({"available_dates": []})

    today = date.today()
    available_dates = []

    for i in range(30):
        check_date = today + timedelta(days=i)
        weekday = check_date.strftime("%A").upper()

        if weekday not in working_days:
            continue

        # 🔥 CHECK EXISTING BOOKINGS (IMPORTANT)
        jobs_count = Job.objects.filter(
            landscaper=landscaper,
            scheduled_date=check_date,
            is_active=True
        ).count()

        # 🔥 limit per day (you can adjust)
        MAX_JOBS_PER_DAY = 5

        if jobs_count < MAX_JOBS_PER_DAY:
            available_dates.append(check_date)

    return Response({
        "landscaper_id": landscaper.id,
        "available_dates": available_dates
    })

# time slot
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_landscaper_available_slots(request, landscaper_id):

    date_str = request.GET.get("date")

    if not date_str:
        return Response({"error": "date is required"}, status=400)

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        return Response({"error": "Invalid date format"}, status=400)

    try:
        landscaper = BusinessProfile.objects.get(id=landscaper_id)
    except BusinessProfile.DoesNotExist:
        return Response({"error": "Landscaper not found"}, status=404)

    weekday = selected_date.strftime("%A").upper()

    working_hours = WorkingHours.objects.filter(
        landscaper=landscaper,
        day=weekday,
        is_active=True
    )

    slots = []

    for wh in working_hours:
        slots.append({
            "start_time": wh.start_time,
            "end_time": wh.end_time
        })

    # remove booked slots
    booked = Job.objects.filter(
        landscaper=landscaper,
        scheduled_date=selected_date,
        status__in=["upcoming", "in_progress"]
    ).values_list("scheduled_time", flat=True)

    available_slots = [
        slot for slot in slots if slot["start_time"] not in booked
    ]

    return Response({
        "date": selected_date,
        "available_slots": available_slots
    })



# landscaper availability for client booking
from datetime import date, timedelta
from collections import defaultdict

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from landscapers.models import BusinessProfile, WorkingHours
from jobs.models import Job



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_landscaper_availability(request, landscaper_id):

    # ==========================================
    # GET LANDSCAPER
    # ==========================================
    # try:
    #     landscaper = BusinessProfile.objects.get(id=landscaper_id)
    # except BusinessProfile.DoesNotExist:
    #     return Response(
    #         {"error": "Landscaper not found"},
    #         status=404
    #     )
    try:
        landscaper = BusinessProfile.objects.get(user_id=landscaper_id)
    except BusinessProfile.DoesNotExist:
        return Response({"error": "Landscaper not found"}, status=404)
    # ==========================================
    # GET ACTIVE WORKING HOURS
    # ==========================================
    working_hours = WorkingHours.objects.filter(
        landscaper=landscaper,
        is_active=True
    ).order_by("day", "start_time")

    if not working_hours.exists():
        return Response({
            "landscaper_id": landscaper.id,
            "availability": []
        })

    # ==========================================
    # GROUP WORKING HOURS BY DAY
    # ==========================================
    working_map = defaultdict(list)

    for wh in working_hours:
        working_map[wh.day].append({
            "start_time": wh.start_time,
            "end_time": wh.end_time,
        })

    # ==========================================
    # GET BOOKED JOBS
    # ==========================================
    booked_jobs = Job.objects.filter(
        landscaper=landscaper,
        scheduled_date__gte=date.today(),
        is_active=True,
        status__in=["upcoming", "in_progress"]
    )

    # ==========================================
    # GROUP BOOKED TIMES BY DATE
    # ==========================================
    booked_map = defaultdict(list)

    for job in booked_jobs:
        booked_map[job.scheduled_date].append(job.scheduled_time)

    # ==========================================
    # GENERATE 30 DAYS AVAILABILITY
    # ==========================================
    availability = []

    today = date.today()

    MAX_JOBS_PER_DAY = 5

    for i in range(30):

        check_date = today + timedelta(days=i)

        weekday = check_date.strftime("%A").upper()

        # skip non-working day
        if weekday not in working_map:
            continue

        # today's booked slots
        booked_slots = booked_map.get(check_date, [])

        # max daily limit
        if len(booked_slots) >= MAX_JOBS_PER_DAY:
            continue

        available_slots = []

        for slot in working_map[weekday]:

            # skip booked slot
            if slot["start_time"] in booked_slots:
                continue

            available_slots.append({
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
            })

        # skip empty dates
        if not available_slots:
            continue

        availability.append({
            "date": check_date,
            "slots": available_slots
        })

    # ==========================================
    # RESPONSE
    # ==========================================
    return Response({
        "landscaper_id": landscaper.id,
        "availability": availability
    })
    
# views.py

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_performance_monthly(request):
    """
    Return total number of services created per month for last 12 months.
    """
    # ✅ FIX: get landscaper profile
    landscaper = getattr(request.user, "landscaper_profile", None)

    if not landscaper:
        return Response(
            {"error": "Landscaper profile not found."},
            status=status.HTTP_403_FORBIDDEN
        )

    today = now()

    # ✅ generate last 12 months correctly
    month_labels = []
    month_start_dates = []

    for i in range(12):
        month = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        month_start_dates.append(month)
        month_labels.append(month.strftime("%b %Y"))

    month_labels.reverse()
    month_start_dates.reverse()

    # ✅ FIX: use business instead of landscaper
    services_qs = (
        Service.objects.filter(
            business=landscaper,
            created_at__gte=month_start_dates[0]
        )
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    # map counts
    counts = {label: 0 for label in month_labels}

    for item in services_qs:
        label = item["month"].strftime("%b %Y")
        counts[label] = item["count"]

    return Response({
        "months": month_labels,
        "service_count": counts
    })

# pinned service /unpinned service
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def toggle_service_pin(request, service_id):
    """
    Toggle pin/unpin for a particular service.
    Only the owner (landscaper) can pin their service.
    """
    try:
        service = Service.objects.get(id=service_id, landscaper=request.user)
    except Service.DoesNotExist:
        return Response({"error": "Service not found"}, status=404)

    service.is_pinned = not service.is_pinned
    service.save(update_fields=["is_pinned"])

    return Response({
        "id": service.id,
        "standard_service": service.standard_service,
        "is_pinned": service.is_pinned
    })

@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def send_quote(request, pk):

    landscaper = getattr(request.user, "landscaper_profile", None)
    if not landscaper:
        return Response({"error": "Landscaper profile not found"}, status=403)

    try:
        quote = ClientCustomService.objects.get(
            id=pk,
            landscaper=landscaper,
            is_active=True
        )
    except ClientCustomService.DoesNotExist:
        return Response({"error": "Quote not found"}, status=404)

    if quote.status != "pending":
        return Response({"error": "Quote already processed"}, status=400)

    price = request.data.get("price")

    if not price:
        return Response({"error": "Price is required"}, status=400)

    try:
        price = Decimal(price)
    except:
        return Response({"error": "Invalid price"}, status=400)

    if price <= 0:
        return Response({"error": "Price must be greater than 0"}, status=400)

    quote.price = price
    quote.status = "quoted"
    quote.note = request.data.get("note", "")
    quote.save()

    return Response({
        "message": "Quote sent successfully",
        "quote_id": quote.id,
        "price": quote.price
    })

@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def confirm_quote(request, pk):

    client = getattr(request.user, "clientprofile", None)
    if not client:
        return Response({"error": "Client profile not found"}, status=403)

    action = request.data.get("action")

    if action not in ["confirm", "decline"]:
        return Response({"error": "Invalid action"}, status=400)

    try:
        quote = ClientCustomService.objects.get(
            id=pk,
            client=client,
            is_active=True
        )
    except ClientCustomService.DoesNotExist:
        return Response({"error": "Quote not found"}, status=404)

    if quote.status != "quoted":
        return Response({"error": "Quote is not ready"}, status=400)

    if action == "decline":
        quote.status = "declined"
        quote.save()
        return Response({"message": "Quote declined"})

    # ✅ CONFIRM → CREATE BOOKING
    booking = BookingRequest.objects.create(
        client=quote.client,
        landscaper=quote.landscaper,
        property=quote.property,
        description=quote.description,
        scheduled_date=quote.preferred_date,
        scheduled_time=quote.preferred_time,
        price=quote.price,
        status="pending",
        is_active=True
    )

    quote.status = "confirmed"
    quote.booking = booking
    quote.save()

    return Response({
        "message": "Quote accepted",
        "booking_id": booking.id
    })

class ClientQuoteListView(generics.ListAPIView):
    serializer_class = ClientCustomServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        client = getattr(self.request.user, "clientprofile", None)
        return ClientCustomService.objects.filter(client=client).order_by("-created_at")
        

class LandscaperQuoteListView(generics.ListAPIView):
    serializer_class = ClientCustomServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        landscaper = getattr(self.request.user, "landscaper_profile", None)
        return ClientCustomService.objects.filter(
            landscaper=landscaper
        ).order_by("-created_at")



# views.py

class ServiceQuoteCreateView(generics.CreateAPIView):
    serializer_class = ServiceQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data,
            context={"request": request}
        )

        serializer.is_valid(raise_exception=True)

        quote = serializer.save()

        return Response(
            ServiceQuoteSerializer(quote).data,
            status=status.HTTP_201_CREATED
        )


class ServiceQuoteCounterView(generics.UpdateAPIView):
    serializer_class = ServiceQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ServiceQuote.objects.all()

    def update(self, request, *args, **kwargs):

        quote = self.get_object()

        landscaper = getattr(request.user, "landscaper_profile", None)

        if not landscaper:
            return Response(
                {"error": "Landscaper profile not found"},
                status=400
            )

        if quote.landscaper != landscaper:
            return Response(
                {"error": "Not allowed"},
                status=403
            )

        if quote.status not in [
            ServiceQuote.Status.PENDING,
            ServiceQuote.Status.COUNTERED
        ]:
            return Response(
                {"error": "Cannot counter this quote"},
                status=400
            )

        counter_price = request.data.get("counter_price")

        if not counter_price:
            return Response(
                {"error": "counter_price is required"},
                status=400
            )

        # ✅ FIX HERE
        quote.price = counter_price

        quote.status = ServiceQuote.Status.COUNTERED

        quote.save(update_fields=[
            "price",
            "status",
            "updated_at"
        ])

        return Response({
            "message": "Quote countered successfully",
            "data": ServiceQuoteSerializer(quote).data
        })




class ClientCounterOfferListView(generics.ListAPIView):
    serializer_class = ServiceQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):

        user = self.request.user

        # -------------------------
        # CLIENT VIEW
        # -------------------------
        if hasattr(user, "clientprofile"):
            return ServiceQuote.objects.filter(
                client=user.clientprofile,
                status__in=[
                    ServiceQuote.Status.PENDING,
                    ServiceQuote.Status.COUNTERED
                ]
            ).select_related(
                "service",
                "landscaper",
                "property"
            ).order_by("-updated_at")

        # -------------------------
        # LANDSCAPER VIEW
        # -------------------------
        if hasattr(user, "landscaper_profile"):
            return ServiceQuote.objects.filter(
                landscaper=user.landscaper_profile,
                status__in=[
                    ServiceQuote.Status.PENDING,
                    ServiceQuote.Status.COUNTERED
                ]
            ).select_related(
                "service",
                "client",
                "property"
            ).order_by("-updated_at")

        return ServiceQuote.objects.none()


def get_final_price(quote):
    try:
        if quote.counter_price and Decimal(str(quote.counter_price)) > 0:
            return Decimal(str(quote.counter_price))

        if quote.requested_price and Decimal(str(quote.requested_price)) > 0:
            return Decimal(str(quote.requested_price))
    except Exception:
        pass

    return Decimal("0.00")


class ServiceQuoteActionView(generics.UpdateAPIView):
    serializer_class = ServiceQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ServiceQuote.objects.all()

    @transaction.atomic
    def update(self, request, *args, **kwargs):

        quote = self.get_object()
        client = getattr(request.user, "clientprofile", None)

        if not client or quote.client != client:
            return Response({"error": "Not allowed"}, status=403)

        action = request.data.get("action")

        # =========================
        # ACCEPT FLOW
        # =========================
        if action == "accept":

            if quote.status == ServiceQuote.Status.CONVERTED:
                return Response({"error": "Already converted"}, status=400)

            # =========================
            # FIX 1: USE ONLY REAL FIELD
            # =========================
            final_price = quote.price

            if not final_price or final_price <= 0:
                return Response(
                    {"error": "Quote price is not set by landscaper"},
                    status=400
                )

            quote.status = ServiceQuote.Status.ACCEPTED
            quote.save()

            # =========================
            # FIX 2: CREATE JOB WITH REAL PRICE
            # =========================
            job = Job.objects.create(
                client=quote.client,
                landscaper=quote.landscaper,
                job_property=quote.property,
                scheduled_date=quote.scheduled_date,
                scheduled_time=quote.scheduled_time,
                total_price=final_price,
                status=Job.Status.UPCOMING,
            )

            # =========================
            # FIX 3: CREATE JOB ITEM WITH SAME PRICE
            # =========================
            JobItem.objects.create(
                job=job,
                item_type=JobItem.ItemType.STANDARD_SERVICE,
                service=quote.service,
                name=quote.service.name,
                price=final_price,
            )

            # =========================
            # FIX 4: FORCE TOTAL RECHECK (IMPORTANT)
            # =========================
            job.total_price = job.items.aggregate(
                total=Sum("price")
            )["total"] or Decimal("0.00")

            job.save(update_fields=["total_price"])

            # mark converted
            quote.status = ServiceQuote.Status.CONVERTED
            quote.save()

            return Response({
                "message": "Quote accepted successfully",
                "quote_id": quote.id,
                "job_id": job.id,
                "total_price": str(job.total_price)
            })
        # =========================
        # REJECT FLOW
        # =========================
        elif action == "reject":
            quote.status = ServiceQuote.Status.REJECTED
            quote.save()

            return Response({
                "message": "Quote rejected successfully",
                "quote_id": quote.id
            })

        else:
            return Response({"error": "Invalid action"}, status=400)
        



from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied


class ServiceQuoteListForLandscaper(generics.ListAPIView):
    serializer_class = ServiceQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        client = getattr(user, "clientprofile", None)
        landscaper = getattr(user, "landscaper_profile", None)

        if client:
            custom_qs = ClientCustomService.objects.filter(
                client=client,
                is_active=True
            ).select_related(
                "client__user",
                "property",
                "landscaper__user"
            )

            quote_qs = ServiceQuote.objects.filter(
                client=client
            ).select_related(
                "client__user",
                "landscaper__user",
                "service",
                "property"
            )

        elif landscaper:
            custom_qs = ClientCustomService.objects.filter(
                landscaper=landscaper
            ).select_related(
                "client__user",
                "property",
                "landscaper__user"
            )

            quote_qs = ServiceQuote.objects.filter(
                landscaper=landscaper.user   # ✅ IMPORTANT FIX
            ).select_related(
                "client__user",
                "landscaper__user",
                "service",
                "property"
            )

        else:
            raise PermissionDenied("No valid profile found.")

        return self._merge_queryset(custom_qs, quote_qs)

    def _merge_queryset(self, custom_qs, quote_qs):
        custom_qs = list(custom_qs)
        quote_qs = list(quote_qs)

        for obj in custom_qs:
            obj.request_type = "custom_request"

        for obj in quote_qs:
            obj.request_type = "quote_request"

        return custom_qs + quote_qs
    
    

from rest_framework import status
from django.shortcuts import get_object_or_404

class ServiceQuoteDeleteView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ServiceQuote.objects.all()

    def delete(self, request, *args, **kwargs):
        quote_id = kwargs.get("pk")

        user = request.user
        client = getattr(user, "clientprofile", None)
        landscaper = getattr(user, "landscaper_profile", None)

        quote = get_object_or_404(ServiceQuote, id=quote_id)

        # -------------------------
        # CLIENT DELETE RULE
        # -------------------------
        if client:
            if quote.client != client:
                return Response(
                    {"error": "You cannot delete this quote."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # -------------------------
        # LANDSCAPER DELETE RULE
        # -------------------------
        elif landscaper:
            if quote.landscaper != landscaper:
                return Response(
                    {"error": "You cannot delete this quote."},
                    status=status.HTTP_403_FORBIDDEN
                )

        else:
            return Response(
                {"error": "Invalid user type."},
                status=status.HTTP_403_FORBIDDEN
            )

        quote.delete()

        return Response(
            {"message": "Quote request deleted successfully."},
            status=status.HTTP_200_OK
        )