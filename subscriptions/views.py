import stripe
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions
from django.http import HttpResponse
from .serializers import PlanSerializer, SubscriptionSerializer,AdminSubscriptionSerializer,SubscriptionUpgradeSerializer,AppleVerifySerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from django.db.models import Count, Sum
from .models import Plan
from common.permissions import IsLandscaper
from rest_framework import status
from django.db.models import Q
stripe.api_key = settings.STRIPE_SECRET_KEY
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from subscriptions.models import Subscription
from subscriptions.serializers import SubscriptionSerializer
from common.permissions import IsAdmin
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
import stripe
from datetime import datetime
from rest_framework.permissions import IsAdminUser
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.conf import settings
from datetime import datetime, timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination

from subscriptions.models import Subscription
from .models import Subscription, Plan
from .serializers import (
    AdminPlanOptionSerializer,
    AdminLandscaperSubscriptionEditSerializer,
)
from decimal import Decimal
import stripe
from django.conf import settings
from .models import Plan, Subscription
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.utils import timezone
import stripe
from subscriptions.models import Subscription, SubscriptionStatus, SubscriptionLog
from profiles.models import LandscaperProfilies
User = get_user_model()
from django.conf import settings
from django.db import transaction

from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
from .models import Plan
from .serializers import PlanSerializer
from datetime import datetime
from django.utils import timezone
from django.db.models import Sum, Count, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from .models import Plan, Subscription, SubscriptionStatus
stripe.api_key = settings.STRIPE_SECRET_KEY
from notifications.models import Notification






class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"

class PlanListCreateView(generics.ListCreateAPIView):

    serializer_class = PlanSerializer

    def get_queryset(self):

        # Admin sees all
        if self.request.user.is_authenticated and self.request.user.role == "admin":
            return Plan.objects.all()

        # Public only sees active plans
        return Plan.objects.filter(is_active=True)

    def get_permissions(self):

        if self.request.method == "POST":
            return [IsAdmin()]

        return [permissions.AllowAny()]

    @transaction.atomic
    def perform_create(self, serializer):

        plan = serializer.save()

        # Stripe interval mapping
        interval = (
            "year"
            if plan.duration == "yearly"
            else "month"
        )

        try:

            # Create Stripe Product
            product = stripe.Product.create(
                name=plan.name,
                description=plan.description or ""
            )

            # Create Stripe Price
            price = stripe.Price.create(
                product=product.id,
                unit_amount=int(plan.final_price * 100),
                currency="usd",
                recurring={
                    "interval": interval
                },
            )

            # Save Stripe IDs
            plan.stripe_product_id = product.id
            plan.stripe_price_id = price.id

            plan.save(update_fields=[
                "stripe_product_id",
                "stripe_price_id",
                "updated_at"
            ])

        except stripe.error.StripeError as e:

            raise serializers.ValidationError({
                "stripe": str(e)
            })
        

class PlanRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer

    def get_permissions(self):
        return [IsAdmin()] if self.request.method in ["PUT", "PATCH", "DELETE"] else [permissions.AllowAny()]



# ================================================
# Helper: safe start/end dates
# ================================================
def safe_subscription_dates(stripe_sub, plan=None):
    """
    Returns start and end datetimes for subscription.
    Falls back to timezone.now() and plan duration if Stripe fields are missing.
    """
    start_ts = stripe_sub.get("current_period_start")
    end_ts = stripe_sub.get("current_period_end")

    start = timezone.make_aware(datetime.fromtimestamp(start_ts)) if start_ts else timezone.now()

    if end_ts:
        end = timezone.make_aware(datetime.fromtimestamp(end_ts))
    elif plan:
        end = start + timedelta(days=plan.duration_days)
    else:
        end = start + timedelta(days=30)  # default fallback

    return start, end





# @api_view(["POST"])

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):

    stripe.api_key = settings.STRIPE_SECRET_KEY

    plan_id = request.data.get("plan_id")
    is_trial = request.data.get("is_trial", True) 

    if not plan_id:
        return Response({"detail": "plan_id is required"}, status=400)

    plan = Plan.objects.filter(id=plan_id).first()
    if not plan:
        return Response({"detail": "Invalid plan"}, status=400)

    # ================================
    # Ensure Stripe customer exists
    # ================================
    if not request.user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=request.user.email,
            name=request.user.name or request.user.email,
        )
        request.user.stripe_customer_id = customer.id
        request.user.save()

    try:

        # ================================
        # FIX: Only apply trial when allowed
        # ================================
        subscription_data = {}

        if is_trial:
            subscription_data["trial_period_days"] = 14

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=request.user.stripe_customer_id,

            line_items=[{
                "price": plan.stripe_price_id,
                "quantity": 1
            }],

            metadata={
                "user_id": str(request.user.id),
                "plan_id": str(plan.id),
                "is_trial": str(is_trial),  # ✅ track it
            },

            subscription_data=subscription_data,

            # success_url="https://yourdomain.com/success/?session_id={CHECKOUT_SESSION_ID}",
            # cancel_url="https://yourdomain.com/cancel/",
            
            success_url="http://127.0.0.1:8000/success/?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://127.0.0.1:8000/cancel/",
        )

        return Response({
            "checkout_url": session.url,
            "is_trial": is_trial
        })

    except Exception as e:
        print("Stripe error:", str(e))
        return Response({"detail": "Stripe error"}, status=500)


# ================================================
# Stripe Webhook
# ================================================

@csrf_exempt
def stripe_webhook(request):

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    if not sig_header:
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    event_type = event["type"]
    data = event["data"]["object"]

    # =========================================================
    # 1. CHECKOUT COMPLETED
    # =========================================================
    # =========================================================
    # 1. CHECKOUT COMPLETED
    # =========================================================
    if event_type == "checkout.session.completed":

        try:
            if data.get("mode") != "subscription":
                return HttpResponse(status=200)

            subscription_id = data.get("subscription")
            metadata = data.get("metadata", {})

            user_id = metadata.get("user_id")
            plan_id = metadata.get("plan_id")

            if not user_id or not plan_id:
                return HttpResponse(status=200)

            user = User.objects.filter(id=user_id).first()
            plan = Plan.objects.filter(id=plan_id).first()

            if not user or not plan:
                return HttpResponse(status=200)

            stripe_sub = stripe.Subscription.retrieve(subscription_id)

            now = timezone.now()

            # =====================================================
            # 🚨 TRIAL LOGIC (ONLY ONCE PER USER)
            # =====================================================
            existing_trial = Subscription.objects.filter(
                user=user,
                is_trial=True
            ).exists()

            if not existing_trial:
                # FIRST TIME USER → 14 DAYS TRIAL
                start_date = now
                end_date = now + timedelta(days=14)
                is_trial = True

            else:
                # PAID SUBSCRIPTION (FROM STRIPE)
                start_ts = getattr(stripe_sub, "current_period_start", None)
                end_ts = getattr(stripe_sub, "current_period_end", None)

                start_date = (
                    datetime.fromtimestamp(start_ts, tz=timezone.utc)
                    if start_ts else now
                )

                end_date = (
                    datetime.fromtimestamp(end_ts, tz=timezone.utc)
                    if end_ts else (start_date + timedelta(days=plan.duration_days))
                )

                is_trial = False

            # =====================================================
            # SAFETY CHECK (VERY IMPORTANT)
            # =====================================================
            if end_date <= start_date:
                end_date = start_date + timedelta(days=plan.duration_days)

            # =====================================================
            # SAVE SUBSCRIPTION
            # =====================================================
            Subscription.objects.update_or_create(
                stripe_subscription_id=subscription_id,
                defaults={
                    "user": user,
                    "plan": plan,
                    "stripe_customer_id": stripe_sub.customer,
                    "status": stripe_sub.status,
                    "is_active": stripe_sub.status in ["active", "trialing"],
                    "is_trial": is_trial,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

            return HttpResponse(status=200)

        except Exception as e:
            print("checkout.session.completed error:", str(e))
            return HttpResponse(status=200)

            
    # =========================================================
    # 2. PAYMENT SUCCESS (RENEWALS)
    # =========================================================
    elif event_type == "invoice.payment_succeeded":

        try:
            subscription_id = data.get("subscription")

            if not subscription_id:
                return HttpResponse(status=200)

            stripe_sub = stripe.Subscription.retrieve(subscription_id)

            start_ts = stripe_sub.get("current_period_start")
            end_ts = stripe_sub.get("current_period_end")

            if not start_ts or not end_ts:
                return HttpResponse(status=200)

            start_date = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            end_date = datetime.fromtimestamp(end_ts, tz=timezone.utc)

            if end_date <= start_date:
                end_date = start_date + timedelta(days=30)

            Subscription.objects.filter(
                stripe_subscription_id=subscription_id
            ).update(
                status=stripe_sub.get("status"),
                is_active=stripe_sub.get("status") in ["active", "trialing"],
                is_trial=(stripe_sub.get("status") == "trialing"),
                start_date=start_date,
                end_date=end_date,
                updated_at=timezone.now(),
            )

        except Exception as e:
            print("invoice.payment_succeeded error:", str(e))

        return HttpResponse(status=200)

    # =========================================================
    # 3. PAYMENT FAILED
    # =========================================================
    elif event_type == "invoice.payment_failed":

        try:
            Subscription.objects.filter(
                stripe_subscription_id=data.get("subscription")
            ).update(
                status="past_due",
                is_active=False,
                updated_at=timezone.now(),
            )
        except Exception as e:
            print("invoice.payment_failed error:", str(e))

        return HttpResponse(status=200)

    # =========================================================
    # 4. SUB UPDATED
    # =========================================================
    elif event_type == "customer.subscription.updated":

        try:
            Subscription.objects.filter(
                stripe_subscription_id=data.get("id")
            ).update(
                status=data.get("status"),
                is_active=data.get("status") in ["active", "trialing"],
                is_trial=(data.get("status") == "trialing"),
                updated_at=timezone.now(),
            )
        except Exception as e:
            print("subscription.updated error:", str(e))

        return HttpResponse(status=200)

    # =========================================================
    # 5. CANCELLED
    # =========================================================
    elif event_type == "customer.subscription.deleted":

        try:
            Subscription.objects.filter(
                stripe_subscription_id=data.get("id")
            ).update(
                status="cancelled",
                is_active=False,
                updated_at=timezone.now(),
            )
        except Exception as e:
            print("subscription.deleted error:", str(e))

        return HttpResponse(status=200)

    # =========================================================
    # DEFAULT FALLBACK (IMPORTANT FIX)
    # =========================================================
    return HttpResponse(status=200)




# apple payemnt endpoint

@csrf_exempt
@api_view(["POST"])
def apple_iap_webhook(request):

    signed_payload = request.data.get(
        "signedPayload"
    )

    if not signed_payload:
        return Response(
            {"detail": "signedPayload is required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:

        notification = verify_apple_notification(
            signed_payload
        )

        # Process notification here

        return Response(
            {"status": "ok"},
            status=status.HTTP_200_OK
        )

    except Exception as e:

        return Response(
            {
                "detail": "Invalid Apple notification."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

# subscription list
class SubscriptionListView(generics.ListAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [IsLandscaper]

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)


class SubscriptionCreateView(generics.CreateAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [IsLandscaper]
    

    def perform_create(self, serializer):
        plan = get_object_or_404(Plan, id=self.request.data.get("plan"))
        print()
        serializer.save(user=self.request.user, plan=plan)



# resume and trail
class AdminPauseSubscriptionAPIView(APIView):
    """
    Admin can pause or resume a subscription.
    PATCH body: {"is_active": false} → pause
                {"is_active": true} → resume
    Response includes plan_name, plan_price, subscription details, and current status.
    """
    permission_classes = [IsAdminUser]

    def patch(self, request, subscription_id):
        subscription = get_object_or_404(Subscription, id=subscription_id)

        # Get is_active from request
        is_active = request.data.get("is_active")
        if is_active is None:
            return Response(
                {"detail": "The 'is_active' field is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Convert to boolean safely
        subscription.is_active = bool(is_active)
        subscription.save(update_fields=["is_active"])

        # Determine status message
        status_text = "active" if subscription.is_active else "paused"
        message = f"Subscription {status_text} successfully."

        serializer = SubscriptionUpgradeSerializer(subscription)

        return Response({
            "status": "success",
            "message": message,
            "subscription_status": status_text,
            "subscription": serializer.data
        }, status=status.HTTP_200_OK)


# # ----------------------------
# # CREATE STRIPE CHECKOUT SESSION
# # ----------------------------

# Optional success/cancel pages
def success(request):
    session_id = request.GET.get("session_id")
    if session_id:
        return HttpResponse(f"Payment succeeded! Session ID: {session_id}")
    return HttpResponse("Payment succeeded! (No session ID received)")


def cancel(request):
    session_id = request.GET.get("session_id")
    if session_id:
        return HttpResponse(f"Payment canceled! Session ID: {session_id}")
    return HttpResponse("Payment canceled!")




# add Admin Dashboard Stats API
class AdminDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        now = timezone.now()
        month_start = now.replace(day=1)

        # Total plans
        total_plans = Plan.objects.count()

        # ✅ FIXED ACTIVE LOGIC (IMPORTANT)
        active_subscriptions = Subscription.objects.filter(
            is_active=True,
            end_date__gte=now
        ).count()

        # Expired subscriptions (FIXED)
        expired_subscriptions = Subscription.objects.filter(
            is_active=True,
            end_date__lt=now
        ).count()

        # Monthly revenue (safe version)
        monthly_revenue = Subscription.objects.filter(
            start_date__gte=month_start,
            is_active=True,
            end_date__gte=now
        ).aggregate(
            total=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("plan__price")
                        - (F("plan__price") * F("discount_override") / Decimal("100")),
                        output_field=DecimalField()
                    )
                ),
                Decimal("0")
            )
        )["total"]

        # Subscribers by plan (FIXED)
        subscribers_by_plan = (
            Subscription.objects.filter(
                is_active=True,
                end_date__gte=now
            )
            .values("plan__name")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        return Response({
            "total_plans": total_plans,
            "active_subscriptions": active_subscriptions,
            "expired_subscriptions": expired_subscriptions,
            "monthly_revenue": monthly_revenue,
            "subscribers_by_plan": list(subscribers_by_plan),
        })
    



# admin plan delete
class AdminPlanDeleteView(generics.DestroyAPIView):
    queryset = Plan.objects.all()
    permission_classes = [IsAuthenticated, IsAdmin]

    def perform_destroy(self, instance):
        # Prevent deleting a plan with active subscriptions
        if Subscription.objects.filter(plan=instance, status="active").exists():
            raise ValidationError({
                "detail": "Cannot delete plan with active subscriptions."
            })
        # Delete the plan
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Plan deleted successfully."},
            status=status.HTTP_200_OK
        )



# subscriptions/views.py
class AdminSubscriptionDeleteView(APIView):
    """
    Admin API to cancel/delete any user's subscription safely.
    If the subscription does not exist on Stripe, it continues and only updates the DB.
    """
    permission_classes = [IsAdmin]

    def delete(self, request, subscription_id):
        # 1️⃣ Get the subscription object
        subscription = get_object_or_404(Subscription, id=subscription_id)

        # 2️⃣ Cancel Stripe subscription if ID exists
        stripe_subscription_id = subscription.stripe_subscription_id
        if stripe_subscription_id:
            try:
                stripe.Subscription.delete(stripe_subscription_id)
            except stripe.error.InvalidRequestError as e:
                if "No such subscription" in str(e):
                    # Stripe subscription not found, just log and continue
                    print(f"[Stripe] Subscription not found: {stripe_subscription_id}")
                else:
                    return Response(
                        {"detail": f"Stripe error: {str(e)}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        # 3️ Update subscription in DB
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.is_active = False
        subscription.end_date = timezone.now()
        subscription.save(update_fields=["status", "is_active", "end_date"])

        # 4️⃣ Check if user has other active subscriptions
        user = subscription.user
        has_active = Subscription.objects.filter(
            user=user,
            status=SubscriptionStatus.ACTIVE,
            is_active=True
        ).exists()

        # 5️⃣ Downgrade landscaper profile if no active subscriptions
        profile = LandscaperProfilies.objects.filter(user=user).first()
        if profile and not has_active:
            # profile.plan = LandscaperProfilies.BASIC
            profile.save(update_fields=["plan"])

        return Response(
            {
                "detail": "Subscription cancelled and landscaper downgraded if no active plan",
                "subscription_status": subscription.status,
                "plan_after_cancellation": profile.plan if profile else "N/A"
            },
            status=status.HTTP_200_OK
        )




# extend
class ExtendSubscriptionView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        days = request.data.get("days")

        if not days or int(days) <= 0:
            return Response({"detail": "Valid number of days required"}, status=400)

        subscription = get_object_or_404(Subscription, pk=pk)
        days = int(days)

        now = timezone.now()

        if subscription.is_trial:
            # Extend trial: add days to trial_remaining_days
            # If trial expired, restart from today
            base_date = subscription.end_date if subscription.end_date > now else now
            subscription.end_date = base_date + timedelta(days=days)
        else:
            # Paid subscription: add days to end_date
            base_date = subscription.end_date if subscription.end_date > now else now
            subscription.end_date = base_date + timedelta(days=days)
            subscription.status = "active"
            subscription.is_active = True

        subscription.save(update_fields=["end_date", "status", "is_active"])
        
        remaining_trial_days = (subscription.end_date - now).days if subscription.is_trial else None
        remaining_paid_days = (subscription.end_date - now).days if not subscription.is_trial else None

        return Response({
            "message": "Subscription extended successfully",
            "subscription_id": subscription.id,
            "is_trial": subscription.is_trial,
            "trial_remaining_days": remaining_trial_days,
            "remaining_days": remaining_paid_days,
            "new_end_date": subscription.end_date
        }, status=200)




# subscriptions/views.py
class SubscriptionListAPIView(APIView):
    """
    Admin-only API to list subscriptions with:
    - search: plan name, user email, or user full name
    - filter by plan (partial match): e.g., 'ProPlan' or 'BasicPlan'
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        # Get query parameters
        search = request.query_params.get("search", "").strip()
        plan_name = request.query_params.get("plan", "").strip()

        # Base queryset: prefetch user and plan for performance
        queryset = Subscription.objects.select_related("user", "plan").order_by("-created_at")

        # Filter by plan name if provided (partial match)
        if plan_name:
            queryset = queryset.filter(plan__name__icontains=plan_name)

        # Apply flexible search across plan name, user email, and user full name
        if search:
            queryset = queryset.filter(
                Q(plan__name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__name__icontains=search)  # Assuming `user.name` exists
            )

        # Serialize results
        serializer = SubscriptionSerializer(queryset, many=True, context={"request": request})

        return Response({
            "count": queryset.count(),
            "subscriptions": serializer.data
        }, status=status.HTTP_200_OK)




@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def confirm_subscription(request):
    session_id = request.query_params.get("session_id")
    if not session_id:
        return Response({"detail": "session_id is required"}, status=400)

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        return Response({"detail": "Invalid session"}, status=400)

    if session.payment_status == "paid" and session.status == "complete":
        plan_id = session.metadata.get("plan_id")
        plan = Plan.objects.filter(id=plan_id).first()
        user = request.user

        if not plan:
            return Response({"detail": "Plan not found"}, status=404)

        # Create subscription if not exists
        subscription, created = Subscription.objects.get_or_create(
            user=user,
            plan=plan,
            defaults={
                "stripe_subscription_id": session.subscription,
                "status": "active",
                "start_date": timezone.now(),
                "end_date": timezone.now() + timedelta(days=plan.duration_days),
                "is_active": True,
            }
        )

        # Upgrade user role if not already
        if user.role != "landscaper":
            user.role = "landscaper"
            user.save(update_fields=["role"])

        return Response({
            "paid": True,
            "detail": "Subscription activated",
            "plan": {
                "id": plan.id,
                "name": plan.name,           # Basic or Pro
                "price": float(plan.price),
                "discount": float(plan.discount),
                "duration": plan.duration,
                "final_price": float(plan.price - (plan.price * plan.discount / 100))
            },
            "subscription": {
                "id": subscription.id,
                "status": subscription.status,
                "start_date": subscription.start_date,
                "end_date": subscription.end_date,
                "remaining_days": (subscription.end_date - timezone.now()).days
            }
        }, status=200)

    return Response({"paid": False, "detail": "Payment not completed"}, status=200)





class MySubscriptionAPIView(APIView):
    """
    API to view the logged-in user's subscriptions,
    including auto-renew status.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get all subscriptions for this user, latest first
        queryset = Subscription.objects.select_related("user", "plan").filter(
            user=request.user
        ).order_by("-created_at")

        # Serialize subscriptions
        serializer = SubscriptionSerializer(queryset, many=True, context={"request": request})

        # Build response including auto_renew
        subscriptions_data = []
        for sub, ser_data in zip(queryset, serializer.data):
            subscriptions_data.append({
                **ser_data,
                "auto_renew": sub.auto_renew,  # add auto_renew field
                "is_trial": sub.is_trial,      # optional, useful to show trial status
                "current_end_date": sub.end_date
            })

        return Response({
            "count": queryset.count(),
            "subscriptions": subscriptions_data
        }, status=status.HTTP_200_OK)
        




# subscriptions/views.py
class CancelOwnSubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, subscription_id):
        """
        Cancel or remove user's subscription.
        Works for trial, active paid, or inactive subscriptions.
        """
        try:
            subscription = Subscription.objects.get(id=subscription_id, user=request.user)
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "Subscription not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Only cancel if not already cancelled/removed
        if subscription.status == "cancelled":
            return Response(
                {"detail": "Subscription already cancelled."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update subscription status to cancelled
        subscription.status = "cancelled"
        subscription.save(update_fields=["status"])

        return Response(
            {
                "detail": f"Subscription {subscription.id} has been cancelled successfully.",
                "subscription_status": subscription.status
            },
            status=status.HTTP_200_OK
        )




class ToggleAutoRenewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, subscription_id):
        """
        Toggle auto-renewal for a paid subscription.
        - Trial subscriptions cannot be auto-renewed.
        - Next renewal will extend subscription for full plan duration.
        """
        try:
            subscription = Subscription.objects.get(id=subscription_id, user=request.user)
        except Subscription.DoesNotExist:
            return Response({"detail": "Subscription not found."}, status=404)

        if subscription.is_trial:
            return Response({"detail": "Trial subscriptions cannot be auto-renewed."}, status=400)

        # auto_renew field must be provided
        auto_renew = request.data.get("auto_renew")
        if auto_renew is None:
            return Response({"detail": "auto_renew field is required."}, status=400)

        # Update subscription auto_renew flag
        subscription.auto_renew = bool(auto_renew)
        subscription.save(update_fields=["auto_renew"])

        return Response({
            "subscription_id": subscription.id,
            "plan_name": subscription.plan.name,
            "auto_renew": subscription.auto_renew,
            "current_end_date": subscription.end_date
        })




# subscription ratio
class SubscriptionRatioAPIView(APIView):
    """
    Returns the subscription ratio between Pro and Basic plans as percentage.
    Only counts ACTIVE subscriptions.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Count active subscriptions per plan
        subscriptions = Subscription.objects.filter(status=SubscriptionStatus.ACTIVE)
        plan_counts = subscriptions.values('plan__name').annotate(count=Count('id'))

        # Initialize counts
        basic_count = 0
        pro_count = 0
        total = 0

        # Map counts
        for item in plan_counts:
            plan_name = item['plan__name'].lower()
            count = item['count']
            total += count
            if plan_name == 'basic':
                basic_count = count
            elif plan_name == 'pro':
                pro_count = count

        # Avoid division by zero
        if total == 0:
            basic_percentage = 0
            pro_percentage = 0
        else:
            basic_percentage = round((basic_count / total) * 100, 2)
            pro_percentage = round((pro_count / total) * 100, 2)

        return Response({
            "total_active_subscriptions": total,
            "basic": {
                "count": basic_count,
                "percentage": basic_percentage
            },
            "pro": {
                "count": pro_count,
                "percentage": pro_percentage
            }
        })



class UpgradePlanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Get user's current active subscription
        subscription = get_object_or_404(Subscription, user=user, is_active=True)

        # Check if user is already on pro
        if subscription.plan.name.lower() == "pro":
            return Response({"detail": "You are already on Pro plan"}, status=status.HTTP_400_BAD_REQUEST)

        # Get the "Pro" plan
        pro_plan = get_object_or_404(Plan, name__iexact="pro")

        # Upgrade subscription
        subscription.plan = pro_plan
        subscription.start_date = timezone.now()
        subscription.end_date = timezone.now() + timedelta(days=pro_plan.duration_days)
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.is_trial = False  # if any trial
        subscription.save()
    
        # =========================
        # ADMIN NOTIFICATION
        # =========================

        admins = User.objects.filter(is_staff=True)

        for admin in admins:
            Notification.objects.create(
                user=admin,
                notification_type="subscription",
                title="Plan Upgraded 🚀",
                message=f"{user.name or user.email} upgraded to Pro Plan",
            )

        serializer = SubscriptionUpgradeSerializer(subscription)
        return Response({
            "detail": "Subscription upgraded to Pro successfully",
            "subscription": serializer.data
        }, status=status.HTTP_200_OK)





class AdminAllSubscriptionUsersBillingView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        subscriptions = (
            Subscription.objects
            .select_related("user", "plan")
            .order_by("-created_at")
        )

        data = []


        for sub in subscriptions:
            latest_invoice_data = None
            stripe_customer_id = sub.stripe_customer_id
            stripe_subscription_id = sub.stripe_subscription_id

            # -----------------------------------------
            # Step 1: recover missing customer id from Stripe
            # -----------------------------------------
            if stripe_subscription_id and not stripe_customer_id:
                try:
                    stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                    stripe_customer_id = stripe_sub.get("customer")

                    # optional: save back to DB for future use
                    if stripe_customer_id and sub.stripe_customer_id != stripe_customer_id:
                        sub.stripe_customer_id = stripe_customer_id
                        sub.save(update_fields=["stripe_customer_id"])
                except Exception:
                    stripe_customer_id = None



            # -----------------------------------------
            # Step 2: fetch latest invoice from Stripe
            # -----------------------------------------
            if stripe_subscription_id:
                try:
                    invoices = stripe.Invoice.list(
                        subscription=stripe_subscription_id,
                        limit=1
                    )

                    if invoices.data:
                        invoice = invoices.data[0]

                        description = f"{sub.plan.name} - {sub.plan.duration}"
                        lines = invoice.get("lines", {}).get("data", [])
                        if lines and lines[0].get("description"):
                            description = lines[0]["description"]

                        amount_paid = invoice.get("amount_paid", 0) or 0
                        amount_due = invoice.get("amount_due", 0) or 0

                        latest_invoice_data = {
                            "invoice_id": invoice.get("id"),
                            "invoice_number": invoice.get("number"),
                            "subscription_date": invoice.get("created"),
                            "description": description,
                            "amount": (amount_paid if amount_paid > 0 else amount_due) / 100.0,
                            "payment_status": invoice.get("status"),
                            "currency": invoice.get("currency"),
                            "invoice_pdf": invoice.get("invoice_pdf"),
                            "hosted_invoice_url": invoice.get("hosted_invoice_url"),
                        }
                except Exception:
                    latest_invoice_data = None

            # -----------------------------------------
            # Step 3: fallback to local DB data
            # -----------------------------------------
            if not latest_invoice_data:
                latest_invoice_data = {
                    "invoice_id": None,
                    "invoice_number": None,
                    "subscription_date": sub.created_at,
                    "description": f"{sub.plan.name} - {sub.plan.duration}",
                    "amount": float(sub.plan.price),
                    "payment_status": sub.status,
                    "currency": "usd",
                    "invoice_pdf": None,
                    "hosted_invoice_url": None,
                }

            data.append({
                "user_id": sub.user.id,
                "name": sub.user.name,
                "email": sub.user.email,
                "role": sub.user.role,
                "subscription_id": sub.id,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": stripe_subscription_id,
                "is_active": sub.is_active,
                "is_trial": sub.is_trial,
                "auto_renew": sub.auto_renew,
                "start_date": sub.start_date,
                "end_date": sub.end_date,
                **latest_invoice_data,
            })

        # =========================
        # ✅ ADD PAGINATION HERE
        # =========================
        paginator = PageNumberPagination()
        paginator.page_size = 10  # optional override

        result_page = paginator.paginate_queryset(data, request)

        return paginator.get_paginated_response(result_page)


# billing 
class AdminUserBillingSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        subscription = (
            Subscription.objects
            .select_related("plan")
            .filter(user=user)
            .order_by("-created_at")
            .first()
        )

        if not subscription:
            return Response({
                "status": "success",
                "current_plan": None,
                "next_billing": None,
                "lifetime_paid": {
                    "amount": 0.0,
                    "payments": 0
                }
            }, status=status.HTTP_200_OK)

        lifetime_paid = 0.0
        total_payments = 0

        stripe_subscription_id = subscription.stripe_subscription_id

        if stripe_subscription_id:
            try:
                invoices = stripe.Invoice.list(
                    subscription=stripe_subscription_id,
                    limit=100
                )

                for inv in invoices.auto_paging_iter():
                    amount_paid = (inv.get("amount_paid", 0) or 0) / 100.0
                    if inv.get("status") == "paid" and amount_paid > 0:
                        lifetime_paid += amount_paid
                        total_payments += 1
            except Exception:
                pass

        # fallback if no Stripe paid invoices found
        if lifetime_paid == 0 and total_payments == 0 and not subscription.is_trial:
            if subscription.status in ["active", "expired", "cancelled"]:
                lifetime_paid = float(subscription.plan.price)
                total_payments = 1

        cycle_map = {
            "monthly": "month",
            "yearly": "year"
        }
        cycle_label = cycle_map.get(subscription.plan.duration.lower(), subscription.plan.duration.lower())

        return Response({
            "status": "success",
            "current_plan": {
                "name": f"{subscription.plan.name} Plan",
                "price": float(subscription.plan.price),
                "billing_cycle": subscription.plan.duration,
                "display_price": f"${float(subscription.plan.price):.2f} / {cycle_label}"
            },
            "next_billing": {
                "date": subscription.end_date,
                "auto_renew": subscription.auto_renew,
                "text": f"Auto-renews {cycle_label}" if subscription.auto_renew else "Auto-renew off"
            },
            "lifetime_paid": {
                "amount": round(lifetime_paid, 2),
                "payments": total_payments
            }
        }, status=status.HTTP_200_OK)



# billing history

class AdminUserBillingHistoryAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, user_id):

        user = get_object_or_404(User, id=user_id)

        subscription = (
            Subscription.objects
            .filter(user=user)
            .order_by("-created_at")
            .first()
        )

        if not subscription:
            return Response({
                "status": "success",
                "billing_history": []
            })

        billing_history = []

        if subscription.stripe_subscription_id:

            try:

                invoices = stripe.Invoice.list(
                    subscription=subscription.stripe_subscription_id,
                    limit=100
                )

                for invoice in invoices.auto_paging_iter():

                    billing_history.append({
                        "invoice_id": invoice.get("id"),
                        "invoice_number": invoice.get("number"),
                        "amount_paid": (
                            invoice.get("amount_paid", 0) or 0
                        ) / 100,
                        "currency": invoice.get("currency"),
                        "status": invoice.get("status"),
                        "invoice_pdf": invoice.get("invoice_pdf"),
                        "hosted_invoice_url": invoice.get(
                            "hosted_invoice_url"
                        ),
                        "created": invoice.get("created")
                    })

            except Exception as e:

                return Response(
                    {"detail": str(e)},
                    status=400
                )

        return Response({
            "status": "success",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email
            },
            "billing_history": billing_history
        })



class AdminLandscaperSubscriptionManageAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get_user_and_validate_landscaper(self, user_id):
        user = get_object_or_404(User, id=user_id)

        if getattr(user, "role", None) != "landscaper":
            return None, Response(
                {
                    "status": "error",
                    "message": "This user is not a landscaper."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return user, None

    def get_active_subscription(self, user):
        return (
            Subscription.objects.filter(user=user, is_active=True)
            .select_related("user", "plan")
            .order_by("-created_at")
            .first()
        )

    def get_available_plans(self):
        return Plan.objects.filter(
            is_active=True,
            name__iexact="Basic"
        ).union(
            Plan.objects.filter(
                is_active=True,
                name__iexact="Pro"
            )
        )

    def get(self, request, user_id):
        user, error_response = self.get_user_and_validate_landscaper(user_id)
        if error_response:
            return error_response

        subscription = self.get_active_subscription(user)

        plans = Plan.objects.filter(
            is_active=True,
            name__in=["Basic", "Pro"]
        ).order_by("price")

        return Response(
            {
                "status": "success",
                "subscription": (
                    AdminLandscaperSubscriptionEditSerializer(subscription).data
                    if subscription else None
                ),
                "available_plans": AdminPlanOptionSerializer(plans, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, user_id):
        user, error_response = self.get_user_and_validate_landscaper(user_id)
        if error_response:
            return error_response

        subscription = self.get_active_subscription(user)

        # If no active subscription exists, create one from selected plan
        if not subscription:
            plan_id = request.data.get("plan_id")
            if not plan_id:
                return Response(
                    {
                        "status": "error",
                        "message": "plan_id is required to create a subscription for this landscaper."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            plan = Plan.objects.filter(
                id=plan_id,
                is_active=True,
                name__in=["Basic", "Pro"]
            ).first()

            if not plan:
                return Response(
                    {
                        "status": "error",
                        "message": "Selected plan is invalid. Only Basic or Pro is allowed."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            is_trial = request.data.get("is_trial", False)
            extend_trial_days = int(request.data.get("extend_trial_days", 0) or 0)
            discount_override = request.data.get("discount_override", 0)
            auto_renew = request.data.get("auto_renew", True)
            subscription_status = request.data.get("status", "active")

            start_date = timezone.now()

            if is_trial:
                total_trial_days = 14 + extend_trial_days
                end_date = start_date + timedelta(days=total_trial_days)
            else:
                end_date = start_date + timedelta(days=plan.duration_days)

            subscription = Subscription.objects.create(
                user=user,
                plan=plan,
                status=subscription_status,
                is_active=True,
                is_trial=is_trial,
                auto_renew=auto_renew,
                start_date=start_date,
                end_date=end_date,
                discount_override=discount_override,
                trial_extended_days=extend_trial_days,
            )

            return Response(
                {
                    "status": "success",
                    "message": "Subscription created successfully.",
                    "data": AdminLandscaperSubscriptionEditSerializer(subscription).data,
                },
                status=status.HTTP_201_CREATED,
            )

        serializer = AdminLandscaperSubscriptionEditSerializer(
            subscription,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            subscription = serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Subscription updated successfully.",
                    "data": AdminLandscaperSubscriptionEditSerializer(subscription).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "status": "error",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )




class AdminSubscriptionActionAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, subscription_id):
        subscription = get_object_or_404(
            Subscription,
            id=subscription_id
        )

        action = request.data.get("action")
        reason = request.data.get("reason", "")

        if not action:
            return Response(
                {"detail": "action is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_data = SubscriptionSerializer(subscription).data

        try:

            # ====================================
            # EXTEND TRIAL
            # ====================================
            if action == "extend_trial":

                days = int(request.data.get("days", 0))

                if days <= 0:
                    return Response(
                        {"detail": "days must be greater than 0"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                subscription.extend_trial(days)

            # ====================================
            # CHANGE PLAN
            # ====================================
            elif action == "change_plan":

                plan_id = request.data.get("plan_id")

                if not plan_id:
                    return Response(
                        {"detail": "plan_id is required"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                plan = get_object_or_404(
                    Plan,
                    id=plan_id
                )

                subscription.plan = plan
                subscription.start_date = timezone.now()
                subscription.end_date = (
                    timezone.now()
                    + timedelta(days=plan.duration_days)
                )
                subscription.is_trial = False
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.is_active = True

                subscription.save()

            # ====================================
            # APPLY DISCOUNT
            # ====================================
            elif action == "apply_discount":

                discount = Decimal(
                    str(request.data.get("discount", 0))
                )

                if discount < 0 or discount > 100:
                    return Response(
                        {
                            "detail":
                            "Discount must be between 0 and 100"
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                subscription.discount_override = discount
                subscription.save()

            # ====================================
            # PAUSE
            # ====================================
            elif action == "pause":

                subscription.is_active = False
                subscription.status = SubscriptionStatus.PAUSED

                subscription.save(
                    update_fields=[
                        "is_active",
                        "status",
                        "updated_at"
                    ]
                )

            # ====================================
            # RESUME
            # ====================================
            elif action == "resume":

                subscription.is_active = True
                subscription.status = SubscriptionStatus.ACTIVE

                subscription.save(
                    update_fields=[
                        "is_active",
                        "status",
                        "updated_at"
                    ]
                )

            # ====================================
            # AUTO RENEW
            # ====================================
            elif action == "toggle_auto_renew":

                subscription.auto_renew = (
                    not subscription.auto_renew
                )

                subscription.save(
                    update_fields=[
                        "auto_renew",
                        "updated_at"
                    ]
                )

            else:
                return Response(
                    {"detail": "Invalid action"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            new_data = SubscriptionSerializer(subscription).data

            # ====================================
            # AUDIT LOG
            # ====================================
            SubscriptionLog.objects.create(
                subscription=subscription,
                action=action,
                performed_by=request.user,
                old_data=old_data,
                new_data=new_data,
                reason=reason,
                metadata={
                    "subscription_id": subscription.id,
                    "plan": subscription.plan.name,
                    "status": subscription.status
                },
                ip_address=request.META.get(
                    "REMOTE_ADDR"
                ),
                user_agent=request.META.get(
                    "HTTP_USER_AGENT"
                ),
            )

            return Response(
                {
                    "message": "Action completed successfully",
                    "subscription": new_data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:

            return Response(
                {
                    "detail": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AdminAssignSubscriptionAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        user_id = request.data.get("user_id")
        plan_id = request.data.get("plan_id")

        if not user_id or not plan_id:
            return Response(
                {"detail": "user_id and plan_id are required"},
                status=400
            )

        user = get_object_or_404(User, id=user_id)
        plan = get_object_or_404(Plan, id=plan_id)

        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            is_active=True,
            is_trial=request.data.get("is_trial", False),
            auto_renew=request.data.get("auto_renew", True),
            start_date=now,
            end_date=now + timedelta(days=plan.duration_days),
        )

        return Response({
            "message": "Subscription assigned successfully",
            "subscription_id": subscription.id,
            "user": user.email,
            "plan": plan.name,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date
        }, status=201)



# susbscription breakdown
from django.db.models import Sum, Count, F, DecimalField
from django.db.models.functions import TruncMonth


class AdminRevenueBreakdownAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):

        revenue = (
            Subscription.objects.filter(is_active=True)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(
                total_revenue=Sum(
                    F("plan__price"),
                    output_field=DecimalField()
                ),
                total_subscriptions=Count("id")
            )
            .order_by("month")
        )

        data = []

        for item in revenue:
            data.append({
                "month": item["month"].strftime("%b"),  # Jan, Feb, Mar
                "year": item["month"].year,
                "total_revenue": item["total_revenue"],
                "total_subscriptions": item["total_subscriptions"]
            })

        return Response(data)



# apple verifications endpoint
class AppleVerifySubscriptionAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = AppleVerifySerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        transaction_id = serializer.validated_data[
            "transaction_id"
        ]

        plan_id = serializer.validated_data[
            "plan_id"
        ]

        plan = get_object_or_404(
            Plan,
            id=plan_id,
            is_active=True
        )

        # Apple verification will go here
        apple_transaction = verify_apple_transaction(
            transaction_id
        )

        if not apple_transaction:
            return Response(
                {
                    "detail": "Apple transaction verification failed."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------
        # Verify Apple product
        # ----------------------------------

        apple_product_id = apple_transaction.get(
            "product_id"
        )

        if apple_product_id != plan.apple_product_id:

            return Response(
                {
                    "detail": "Apple product does not match selected plan."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------
        # Transaction information
        # ----------------------------------

        original_transaction_id = (
            apple_transaction.get(
                "original_transaction_id"
            )
        )

        apple_transaction_id = (
            apple_transaction.get(
                "transaction_id"
            )
        )

        expires_date = apple_transaction.get(
            "expires_date"
        )

        # ----------------------------------
        # Prevent duplicate transaction
        # ----------------------------------

        existing = Subscription.objects.filter(
            apple_transaction_id=apple_transaction_id
        ).first()

        if existing:

            return Response(
                {
                    "detail": "Transaction already processed.",
                    "subscription": SubscriptionSerializer(
                        existing
                    ).data
                },
                status=status.HTTP_200_OK
            )

        # ----------------------------------
        # Create / update subscription
        # ----------------------------------

        subscription = Subscription.objects.filter(
            user=request.user,
            payment_provider="apple"
        ).first()

        if subscription:

            subscription.plan = plan

            subscription.apple_original_transaction_id = (
                original_transaction_id
            )

            subscription.apple_transaction_id = (
                apple_transaction_id
            )

            subscription.payment_provider = "apple"

            subscription.status = SubscriptionStatus.ACTIVE

            subscription.is_active = True

            subscription.is_trial = False

            subscription.start_date = timezone.now()

            if expires_date:
                subscription.end_date = expires_date
            else:
                subscription.end_date = (
                    timezone.now()
                    + timedelta(
                        days=plan.duration_days
                    )
                )

            subscription.save()

        else:

            start_date = timezone.now()

            end_date = (
                expires_date
                if expires_date
                else start_date + timedelta(
                    days=plan.duration_days
                )
            )

            subscription = Subscription.objects.create(

                user=request.user,

                plan=plan,

                payment_provider="apple",

                apple_original_transaction_id=(
                    original_transaction_id
                ),

                apple_transaction_id=(
                    apple_transaction_id
                ),

                status=SubscriptionStatus.ACTIVE,

                is_active=True,

                is_trial=False,

                start_date=start_date,

                end_date=end_date,

                auto_renew=True,
            )

        return Response(
            {
                "message": "Apple subscription verified successfully.",
                "subscription": SubscriptionSerializer(
                    subscription
                ).data
            },
            status=status.HTTP_200_OK
        )