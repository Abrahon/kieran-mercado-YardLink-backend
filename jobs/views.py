
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from jobs.serializers import CompletedJobSerializer,ManualOneTimeJobCreateSerializer,ClientJobDetailSerializer,ProblemJobSerializer
from jobs.models import Job, JobItem
from jobs.serializers import (
    JobSerializer,
    JobImageSerializer,
    JobRescheduleSerializer,
    JobItemSerializer,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils.timezone import now
from django.db.models.signals import post_save
from django.dispatch import receiver
from notifications.services import send_push_notification
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.utils.timezone import now
from rest_framework import generics, permissions
from jobs.models import Job
from jobs.serializers import JobSerializer
from rest_framework import generics, permissions
from rest_framework.exceptions import NotFound
from django.db.models import Q
from payments.enums import PaymentStatus
from rest_framework import generics, permissions
from .models import JobReschedule
from rest_framework import generics, permissions
from rest_framework.exceptions import NotFound
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, permissions
from .models import JobReschedule
from rest_framework import generics, permissions
from rest_framework.response import Response
from .models import Job, JobItem, JobImage

from django.db import transaction
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response

from .serializers import JobRescheduleSerializer
from notifications.models import Notification

from django.utils import timezone
from datetime import datetime
from django.db.models import Q
from invoice.models import Invoice

from django.utils import timezone




class UpcomingJobsListView(generics.ListAPIView):

    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):

        user = self.request.user
        landscaper = getattr(user, "landscaper_profile", None)

        if not landscaper:
            return Job.objects.none()

        now = timezone.now()
        today = now.date()
        current_time = now.time()

        # 🔥 STEP 1: auto mark missed jobs (important fix)
        Job.objects.filter(
            landscaper=landscaper,
            status=Job.Status.UPCOMING,
            scheduled_date__lt=today
        ).update(status=Job.Status.MISSED)

        # same day but past time
        Job.objects.filter(
            landscaper=landscaper,
            status=Job.Status.UPCOMING,
            scheduled_date=today,
            scheduled_time__lt=current_time
        ).update(status=Job.Status.MISSED)

        # 🔥 STEP 2: return only valid upcoming jobs
        return Job.objects.filter(
            landscaper=landscaper,
            is_active=True,
            status=Job.Status.UPCOMING
        ).filter(
            Q(scheduled_date__gt=today) |
            Q(scheduled_date=today, scheduled_time__gte=current_time)
        ).order_by("scheduled_date", "scheduled_time")
    



class ClientUpcomingJobsListView(generics.ListAPIView):
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        client_profile = getattr(self.request.user, "clientprofile", None)

        if not client_profile:
            return Job.objects.none()

        today = now().date()
        current_time = now().time()

        queryset = (
            Job.objects.filter(
                client=client_profile,
                is_active=True,
            )
            .exclude(
                status__in=[
                    Job.Status.COMPLETED,
                    Job.Status.CANCELLED,
                    Job.Status.SKIPPED,
                    Job.Status.MISSED,
                ]
            )
            .select_related(
                "client",
                "client__user",
                "booking",
                "landscaper",
                "job_property"
            )
            .prefetch_related(
                "items",
                "images",
                "reschedules"
            )
            .filter(
                Q(scheduled_date__gt=today) |
                Q(scheduled_date=today, scheduled_time__gte=current_time)
            )
            .order_by("scheduled_date", "scheduled_time")
        )

        # 🔹 query params
        selected_date = self.request.query_params.get("date")
        today_flag = self.request.query_params.get("today")

        if selected_date:
            queryset = queryset.filter(scheduled_date=selected_date)

        elif today_flag == "true":
            queryset = queryset.filter(scheduled_date=today)

        return queryset



class ClientUpcomingServiceDetailView(generics.RetrieveAPIView):
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        client_profile = getattr(
            self.request.user,
            "clientprofile",
            None
        )

        if not client_profile:
            return Job.objects.none()

        today = now().date()

        #  AUTO MARK EXPIRED UPCOMING JOBS AS MISSED
        Job.objects.filter(
            client=client_profile,
            status=Job.Status.UPCOMING,
            scheduled_date__lt=today
        ).update(status=Job.Status.MISSED)

        #  ONLY FUTURE/TODAY UPCOMING JOBS
        return Job.objects.filter(
            client=client_profile,
            status=Job.Status.UPCOMING,
            is_active=True,
            scheduled_date__gte=today
        )

    def get_object(self):
        queryset = self.get_queryset()

        job_id = self.kwargs.get("id")

        try:
            return queryset.get(id=job_id)

        except Job.DoesNotExist:
            raise NotFound(
                detail="Upcoming service not found."
            )




# --- Job Detail ---
class JobDetailView(generics.RetrieveAPIView):
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "id"

    def get_queryset(self):
        landscaper = getattr(self.request.user, "landscaper_profile", None)
        if not landscaper:
            return Job.objects.none()
        return Job.objects.filter(landscaper=landscaper)




# --- In Progress Job List ---
from django.db.models import Q

class InProgressJobsListView(generics.ListAPIView):
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        landscaper = getattr(user, "landscaper_profile", None)
        client = getattr(user, "clientprofile", None)

        qs = Job.objects.filter(
            is_active=True
        ).select_related(
            "client",
            "landscaper",
            "booking"
        ).prefetch_related(
            "items",
            "images",
            "reschedules"
        )

        # filter by role
        if landscaper:
            qs = qs.filter(landscaper=landscaper)
        elif client:
            qs = qs.filter(client=client)
        else:
            return Job.objects.none()

        # ✅ IMPORTANT: ensure status is up to date
        for job in qs:
            job.sync_status(save=True)

        # now return ONLY in_progress
        return qs.filter(status=Job.Status.IN_PROGRESS).order_by(
            "-scheduled_date",
            "-scheduled_time"
        )




        
# --- In Progress Job Detail ---
class InProgressJobDetailView(generics.RetrieveAPIView):
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "id"

    def get_queryset(self):
        landscaper = getattr(self.request.user, "landscaper_profile", None)
        if not landscaper:
            return Job.objects.none()

        return Job.objects.filter(
            landscaper=landscaper,
            status=Job.Status.IN_PROGRESS,
            is_active=True
        )




class CompletedJobsListView(generics.ListAPIView):
    serializer_class = CompletedJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        landscaper = getattr(user, "landscaper_profile", None)
        client = getattr(user, "clientprofile", None)

        # -------------------------
        # LANDSCAPER VIEW
        # -------------------------
        if landscaper:
            return Job.objects.filter(
                landscaper=landscaper,
                status=Job.Status.COMPLETED,
                is_active=True
            ).order_by("-completed_at", "-updated_at")

        # -------------------------
        # CLIENT VIEW
        # -------------------------
        if client:
            return Job.objects.filter(
                client=client,
                status=Job.Status.COMPLETED,
                is_active=True
            ).order_by("-completed_at", "-updated_at")

        # -------------------------
        # NO PROFILE
        # -------------------------
        return Job.objects.none()




# --- Toggle One Job Item Complete / Incomplete ---
@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def toggle_job_item_completion(request, item_id):
    landscaper = getattr(request.user, "landscaper_profile", None)
    if not landscaper:
        return Response({"error": "Landscaper profile not found."}, status=status.HTTP_403_FORBIDDEN)

    try:
        item = JobItem.objects.select_related("job").get(
            id=item_id,
            job__landscaper=landscaper
        )
    except JobItem.DoesNotExist:
        return Response({"error": "Job item not found."}, status=status.HTTP_404_NOT_FOUND)

    is_completed = request.data.get("is_completed", None)
    if is_completed is None:
        return Response({"error": "is_completed field is required."}, status=status.HTTP_400_BAD_REQUEST)

    # handle true/false safely from JSON
    if is_completed is True:
        item.mark_complete(user=request.user)
    elif is_completed is False:
        item.mark_incomplete()
    else:
        return Response({"error": "is_completed must be true or false."}, status=status.HTTP_400_BAD_REQUEST)

    item.job.refresh_from_db()

    return Response({
        "message": "Job item updated successfully.",
        "item_id": item.id,
        "item_name": item.name,
        "is_completed": item.is_completed,
        "job_id": item.job.id,
        "job_status": item.job.status,
        "total_price": str(item.job.total_price),
        "completed_items": item.job.completed_items,
        "total_items": item.job.total_items,
    }, status=status.HTTP_200_OK)




class JobImageCreateView(generics.CreateAPIView):
    serializer_class = JobImageSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):

        user = self.request.user
        landscaper = getattr(user, "landscaper_profile", None)

        if not landscaper:
            raise serializers.ValidationError({"error": "Landscaper profile not found."})

        job_id = self.request.data.get("job")

        if not job_id:
            raise serializers.ValidationError({"error": "Job is required."})

        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            raise serializers.ValidationError({"error": "Job not found."})

        if job.landscaper != landscaper:
            raise serializers.ValidationError({"error": "Not allowed."})

        # ❌ REMOVE THIS STRICT CHECK
        # if job.status == Job.Status.UPCOMING:
        #     raise serializers.ValidationError("Images cannot be uploaded before job starts.")

        # =========================
        # SAVE IMAGE
        # =========================
        serializer.save(
            job=job,
            uploaded_by=user
        )

        # 🔥 FIX: always sync status after image upload
        job.sync_status()






@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def add_job_note(request, job_id):

    user = request.user

    landscaper = getattr(user, "landscaper_profile", None)
    client = getattr(user, "clientprofile", None)

    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return Response({"error": "Job not found"}, status=404)

    # permission check
    if landscaper and job.landscaper != landscaper:
        return Response({"error": "Not allowed"}, status=403)

    if client and job.client != client:
        return Response({"error": "Not allowed"}, status=403)

    action = request.data.get("action")
    note = request.data.get("note")

    # =========================
    # UPDATE STATUS ACTIONS
    # =========================
    if action == "cancel":
        job.status = Job.Status.CANCELLED

    elif action == "skip":
        job.status = Job.Status.SKIPPED

    elif action == "reschedule":
        job.status = Job.Status.RESCHEDULED

    elif action is not None:
        return Response({"error": "Invalid action"}, status=400)

    # =========================
    # NOTE UPDATE
    # =========================
    if note is not None:
        job.note = note

    job.save(update_fields=["status", "note", "updated_at"])

    #  IMPORTANT FIX
    job.sync_status()

    return Response({
        "message": "Job updated successfully",
        "job_id": job.id,
        "status": job.status,
        "note": job.note
    }, status=200)



# --- Add Job Reschedule ---
class JobRescheduleCreateView(generics.CreateAPIView):
    serializer_class = JobRescheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        landscaper = getattr(user, "landscaper_profile", None)
        client = getattr(user, "clientprofile", None)

        job = serializer.validated_data.get("job")

        # ============================
        # JOB REQUIRED
        # ============================
        if not job:
            raise serializers.ValidationError({"error": "Job is required."})

        # ============================
        # BLOCK FINISHED JOBS
        # ============================
        if job.status in [
            Job.Status.COMPLETED,
            Job.Status.CANCELLED,
            Job.Status.SKIPPED,
        ]:
            raise serializers.ValidationError(
                {"error": "This job cannot be rescheduled."}
            )

        # ============================
        # VERIFY OWNERSHIP
        # ============================
        if landscaper and job.landscaper != landscaper:
            raise serializers.ValidationError({"error": "Not allowed."})

        if client and job.client != client:
            raise serializers.ValidationError({"error": "Not allowed."})

        # ============================
        # CREATE RESCHEDULE
        # ============================
        with transaction.atomic():

            reschedule = serializer.save(
                requested_by=user,
                old_date=job.scheduled_date,
                old_time=job.scheduled_time,
            )

            # =========================
            # CLIENT FLOW
            # =========================
            if client:

                reschedule.status = JobReschedule.Status.PENDING
                reschedule.save(update_fields=["status"])

                # 🔔 NOTIFY LANDSCAPER
                try:
                    send_push_notification(
                        user=job.landscaper.user,
                        title="Reschedule Request 📅",
                        message=f"{job.client_name} requested to reschedule Job #{job.id}",
                        notification_type="job",
                        data={
                            "job_id": job.id,
                            "reschedule_id": reschedule.id,
                            "type": "reschedule_request",
                        },
                    )
                except Exception as e:
                    print("Notification error (landscaper):", str(e))

            # =========================
            # LANDSCAPER FLOW
            # =========================
            elif landscaper:

                reschedule.status = JobReschedule.Status.APPROVED
                reschedule.save(update_fields=["status"])

                job.scheduled_date = reschedule.new_date
                job.scheduled_time = reschedule.new_time
                job.status = Job.Status.UPCOMING

                job.save(
                    update_fields=[
                        "scheduled_date",
                        "scheduled_time",
                        "status",
                        "updated_at",
                    ]
                )

                # 🔔 NOTIFY CLIENT
                try:
                    notify_user = None

                    if job.client and job.client.user:
                        notify_user = job.client.user

                    elif job.external_client:
                        notify_user = job.external_client

                    if notify_user:
                        send_push_notification(
                            user=notify_user,
                            title="Reschedule Approved ✅",
                            message=f"Your job #{job.id} has been rescheduled by landscaper",
                            notification_type="job",
                            data={
                                "job_id": job.id,
                                "reschedule_id": reschedule.id,
                                "type": "reschedule_approved",
                            },
                        )

                except Exception as e:
                    print("Notification error (client):", str(e))

        # ============================
        # FINAL RESPONSE (IMPORTANT FIX)
        # ============================
        return Response(
            {
                "message": "Job rescheduled successfully",
                "reschedule_id": reschedule.id,
                "job_id": job.id,
                "status": reschedule.status,
            },
            status=status.HTTP_201_CREATED,
        )





# landscaper approval and client requested reschedule list
class PendingRescheduleListView(generics.ListAPIView):
    serializer_class = JobRescheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        landscaper = getattr(user, "landscaper_profile", None)

        if not landscaper:
            return JobReschedule.objects.none()

        return JobReschedule.objects.filter(
            job__landscaper=landscaper,
            status="pending"
        ).select_related("job", "requested_by").order_by("-created_at")






class RescheduleActionView(generics.GenericAPIView):

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        user = request.user
        landscaper = getattr(user, "landscaper_profile", None)

        if not landscaper:
            return Response(
                {"error": "Only landscaper can perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )

        action = request.data.get("action")  # approve / reject
        reason = request.data.get("reason")

        reschedule = get_object_or_404(
            JobReschedule,
            pk=pk,
            job__landscaper=landscaper
        )

        # =========================
        # VALIDATE STATUS
        # =========================
        if reschedule.status != "pending":
            return Response(
                {"error": "Only pending requests can be processed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        job = reschedule.job

        # =========================
        # APPROVE
        # =========================
        if action == "approve":

            job.scheduled_date = reschedule.new_date
            job.scheduled_time = reschedule.new_time
            job.status = "upcoming"

            job.save(update_fields=[
                "scheduled_date",
                "scheduled_time",
                "status"
            ])

            reschedule.status = "approved"
            reschedule.save(update_fields=["status"])

            return Response({
                "message": "Reschedule approved successfully."
            }, status=200)

        # =========================
        # REJECT
        # =========================
        if action == "reject":

            if not reason:
                return Response(
                    {"error": "Reason is required for rejection."},
                    status=400
                )

            reschedule.status = "rejected"
            reschedule.reason = reason
            reschedule.save(update_fields=["status", "reason"])

            return Response({
                "message": "Reschedule rejected."
            }, status=200)

        # =========================
        # INVALID ACTION
        # =========================
        return Response(
            {"error": "Invalid action. Use 'approve' or 'reject'."},
            status=400
        )





# cancel job
@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def update_job_status(request, job_id):

    user = request.user
    landscaper = getattr(user, "landscaper_profile", None)
    client = getattr(user, "clientprofile", None)

    job = get_object_or_404(Job, id=job_id)

    # =========================
    # AUTH CHECK
    # =========================
    if landscaper and job.landscaper != landscaper:
        return Response({"error": "Not allowed"}, status=403)

    if client and job.client != client:
        return Response({"error": "Not allowed"}, status=403)

    action = request.data.get("action")
    note = request.data.get("note")  

    if action and action not in ["cancel", "skip"]:
        return Response({"error": "Invalid action"}, status=400)

    # =========================
    # STATUS UPDATE
    # =========================
    if action == "cancel":
        job.status = Job.Status.CANCELLED

    elif action == "skip":
        job.status = Job.Status.SKIPPED

    # =========================
    # NOTE UPDATE (OPTIONAL)
    # =========================
    if note is not None:
        job.note = note

    # =========================
    # SAVE ONLY ONCE
    # =========================
    job.save(update_fields=["status", "note", "updated_at"])

    # =========================
    # NOTIFY CLIENT ONLY WHEN
    # LANDSCAPER CANCELS JOB
    # =========================
    if landscaper and action == "cancel":

        if job.client and job.client.user:

            Notification.objects.create(
                user=job.client.user,
                notification_type="job",
                title="Job Cancelled ❌",
                message=f"Your Job #{job.id} has been cancelled by the landscaper."
            )

            send_push_notification(
                user=job.client.user,
                title="Job Cancelled ❌",
                message=f"Your Job #{job.id} has been cancelled by the landscaper.",
                notification_type="job",
                data={
                    "job_id": str(job.id),
                    "status": job.status,
                    "type": "job_cancelled"
                }
            )

    return Response({
        "message": "Job updated successfully",
        "job_id": job.id,
        "status": job.status,
        "note": job.note
    })






class ProblemJobsListView(generics.ListAPIView):

    serializer_class = ProblemJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):

        user = self.request.user

        landscaper = getattr(user, "landscaper_profile", None)
        client = getattr(user, "clientprofile", None)

        qs = Job.objects.filter(
            status__in=[
                Job.Status.CANCELLED,
                Job.Status.MISSED
            ]
        ).select_related(
            "booking__property",
            "job_property",
            "client",
            "landscaper",
        )

        if landscaper:
            qs = qs.filter(landscaper=landscaper)

        elif client:
            qs = qs.filter(client=client)

        else:
            return Job.objects.none()

        return qs.order_by("-updated_at")





# manual job created
class ManualOneTimeJobCreateView(generics.CreateAPIView):
    serializer_class = ManualOneTimeJobCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)





class CompletedJobDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        job_id = kwargs.get("pk")

        job = get_object_or_404(
            Job.objects.select_related(
                "client__user",
                "external_client",
                "landscaper",
                "job_property",
                "booking",
            ),
            id=job_id
        )

        # -------------------------
        # CLIENT INFO (SAFE FOR BOTH TYPES)
        # -------------------------
        client_data = {
            "name": job.client_name,
            "email": job.client_email,
            "phone": job.client_phone,
        }

        # -------------------------
        # LANDSCAPER INFO
        # -------------------------
        landscaper_data = {
            "id": job.landscaper.id,
            "business_name": getattr(job.landscaper, "business_name", None),
        }

        # -------------------------
        # PROPERTY INFO
        # -------------------------
        property_data = None
        if job.job_property:
            property_data = {
                "id": job.job_property.id,
                "name": getattr(job.job_property, "name", None),
                "address": getattr(job.job_property, "address", None),
            }

        # -------------------------
        # JOB ITEMS
        # -------------------------
        items_qs = JobItem.objects.filter(job=job).select_related(
            "service",
            "addon",
            "completed_by"
        )

        items_data = []
        for item in items_qs:
            items_data.append({
                "id": item.id,
                "item_type": item.item_type,
                "name": item.name,
                "description": item.description,
                "price": float(item.price),
                "is_completed": item.is_completed,
                "completed_at": item.completed_at,
                "note": item.note,
                "service": item.service.name if item.service else None,
                "addon": item.addon.name if item.addon else None,
                "completed_by": item.completed_by.email if item.completed_by else None,
            })

        # -------------------------
        # JOB IMAGES (BEFORE / AFTER GROUPED)
        # -------------------------
        images_qs = JobImage.objects.filter(job=job)

        before_images = []
        after_images = []

        for img in images_qs:
            img_data = {
                "id": img.id,
                "image_url": img.image.url if img.image else None,
                "caption": img.caption,
                "uploaded_by": img.uploaded_by.email if img.uploaded_by else None,
                "created_at": img.created_at,
            }

            if img.image_type == JobImage.ImageType.BEFORE:
                before_images.append(img_data)
            else:
                after_images.append(img_data)

        # -------------------------
        # PROGRESS CALCULATION
        # -------------------------
        total_items = job.total_items
        completed_items = job.completed_items

        progress_percentage = (
            round((completed_items / total_items) * 100, 2)
            if total_items > 0 else 0
        )

        # -------------------------
        # RESPONSE
        # -------------------------
        return Response({
            "id": job.id,

            "status": job.status,
            "payment_status": job.payment_status,
            "is_active": job.is_active,

            "scheduled_date": job.scheduled_date,
            "scheduled_time": job.scheduled_time,

            "total_price": float(job.total_price),

            "progress": {
                "total_items": total_items,
                "completed_items": completed_items,
                "percentage": progress_percentage,
            },

            "completed_at": job.completed_at,

            # CLIENT
            "client": client_data,

            # LANDSCAPER
            "landscaper": landscaper_data,

            # PROPERTY
            "property": property_data,

            # ITEMS
            "items": items_data,

            # IMAGES
            "images": {
                "before": before_images,
                "after": after_images,
            }
        })



class ClientUnpaidCompletedJobView(generics.RetrieveAPIView):

    serializer_class = ClientJobDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):

        print("========== DEBUG ==========")
        print("Logged in user ID:", self.request.user.id)
        print("Logged in email:", self.request.user.email)

        client = getattr(self.request.user, "clientprofile", None)
        print("Client Profile:", client)

        queryset = Job.objects.filter(
            client=client,
            is_active=True,
            status=Job.Status.COMPLETED,
            invoice__status=Invoice.Status.SENT,
        )

        print("Matching jobs:", queryset.count())
        print(list(queryset.values("id", "client_id")))

        job = queryset.select_related(
            "client",
            "landscaper",
            "landscaper__user",
            "invoice",
        ).prefetch_related(
            "items",
            "images"
        ).order_by("-completed_at").first()

        if not job:
            raise NotFound("No completed unpaid job found")

        return job

    
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def complete_job(request, job_id):

    user = request.user
    landscaper = getattr(user, "landscaper_profile", None)

    if not landscaper:
        return Response({"error": "Not allowed"}, status=403)

    try:
        job = Job.objects.get(id=job_id, landscaper=landscaper)
    except Job.DoesNotExist:
        return Response({"error": "Job not found"}, status=404)

    # optional note
    note = request.data.get("note")

    # =========================
    # VALIDATION (VERY IMPORTANT)
    # =========================
    if job.status in [
        Job.Status.CANCELLED,
        Job.Status.SKIPPED,
        Job.Status.MISSED,
    ]:
        return Response({
            "error": "Cannot complete this job"
        }, status=400)

    # OPTIONAL: enforce rules
    if job.items.exists() and job.items.filter(is_completed=False).exists():
        return Response({
            "error": "Please complete all items first"
        }, status=400)

    # =========================
    # COMPLETE JOB
    # =========================
    job.status = Job.Status.COMPLETED
    job.completed_at = timezone.now()

    if note:
        job.note = note

    job.save(update_fields=["status", "completed_at", "note", "updated_at"])

    return Response({
        "message": "Job completed successfully",
        "job_id": job.id,
        "status": job.status
    })