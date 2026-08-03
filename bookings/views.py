


from decimal import Decimal
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import BookingRequest
from .serializers import BookingRequestSerializer
from jobs.models import Job, JobItem
from rest_framework.exceptions import PermissionDenied


# -----------------------------
# Client creates booking
# -----------------------------
class BookingRequestCreateView(generics.CreateAPIView):
    serializer_class = BookingRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        client = getattr(self.request.user, "clientprofile", None)

        if not client:
            raise PermissionDenied("Client profile not found.")

        serializer.save(
            client=client,
            status=BookingRequest.Status.PENDING,
            job_created=False,
            is_active=True
        )

# -----------------------------
# Client booking list
# -----------------------------
class ClientBookingListView(generics.ListAPIView):
    serializer_class = BookingRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        client = getattr(self.request.user, "clientprofile", None)
        if not client:
            return BookingRequest.objects.none()

        return BookingRequest.objects.filter(
            client=client,
            is_active=True
        ).order_by("-created_at")


# -----------------------------
# Client booking detail/delete
# -----------------------------
class BookingRequestRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    serializer_class = BookingRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        client = getattr(self.request.user, "clientprofile", None)
        if not client:
            return BookingRequest.objects.none()
        return BookingRequest.objects.filter(client=client)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != BookingRequest.Status.PENDING:
            return Response(
                {"error": "Only pending bookings can be deleted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.delete()
        return Response({"message": "Booking deleted successfully."}, status=status.HTTP_200_OK)



# -----------------------------
# Client confirm/decline booking
# -----------------------------
@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def client_confirm_booking(request, pk):
    action = request.data.get("action")
    if action not in ["confirm", "decline"]:
        return Response({"error": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)

    client = getattr(request.user, "clientprofile", None)
    if not client:
        return Response({"error": "Client profile not found."}, status=status.HTTP_403_FORBIDDEN)

    try:
        booking = BookingRequest.objects.get(pk=pk, client=client)
    except BookingRequest.DoesNotExist:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != BookingRequest.Status.ACCEPTED:
        return Response({"error": "Booking is not ready for confirmation."}, status=status.HTTP_400_BAD_REQUEST)

    booking.status = BookingRequest.Status.CONFIRMED if action == "confirm" else BookingRequest.Status.DECLINED
    booking.save(update_fields=["status", "updated_at"])

    return Response({
        "message": f"Booking {booking.status} successfully.",
        "status": booking.status
    }, status=status.HTTP_200_OK)


# -----------------------------
# Landscaper sees pending bookings
# -----------------------------
class LandscaperPendingBookingListView(generics.ListAPIView):
    serializer_class = BookingRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        business_profile = getattr(
            self.request.user,
            "landscaper_profile",
            None
        )

        if not business_profile:
            return BookingRequest.objects.none()

        return (
            BookingRequest.objects
            .filter(
                landscaper_id=business_profile.id,
                status=BookingRequest.Status.PENDING,
                is_active=True
            )
            .order_by("-created_at")
        )
    
# -----------------------------
# Landscaper accepts booking
# Creates Job + JobItems from BookingRequestItem
# -----------------------------
# @api_view(["PATCH"])
# @permission_classes([permissions.IsAuthenticated])
# def landscaper_accept_booking(request, pk):
#     landscaper = getattr(request.user, "landscaper_profile", None)

#     if not landscaper:
#         return Response({"error": "Landscaper profile not found."}, status=status.HTTP_403_FORBIDDEN)

#     with transaction.atomic():
#         try:
#             booking = BookingRequest.objects.select_for_update().get(
#                 pk=pk,
#                 landscaper=landscaper,
#                 status=BookingRequest.Status.PENDING,
#                 is_active=True
#             )
#         except BookingRequest.DoesNotExist:
#             return Response({"error": "Pending booking not found."}, status=status.HTTP_404_NOT_FOUND)

#         if booking.job_created:
#             return Response(
#                 {"error": "Job already created for this booking."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         job = Job.objects.create(
#             booking=booking,
#             client=booking.client,
#             landscaper=booking.landscaper,
#             job_property=booking.property,
#             scheduled_date=booking.scheduled_date,
#             scheduled_time=booking.scheduled_time,
#             total_price=Decimal("0.00"),
#             status=Job.Status.UPCOMING,
#             is_active=True
#         )

#         created_items = []
#         for idx, booking_item in enumerate(booking.items.all().order_by("sort_order", "id")):
#             item = JobItem.objects.create(
#                 job=job,
#                 item_type=booking_item.item_type,
#                 service=booking_item.service,
#                 addon=booking_item.addon,
#                 name=booking_item.name,
#                 description=booking_item.description,
#                 price=booking_item.price,
#                 sort_order=idx,
#             )
#             created_items.append(item)

#         job.recalculate_total_price()
#         job.update_status_from_items()

#         booking.status = BookingRequest.Status.ACCEPTED
#         booking.job_created = True
#         booking.save(update_fields=["status", "job_created", "updated_at"])

#     return Response({
#         "message": "Booking accepted and job created successfully.",
#         "booking_id": booking.id,
#         "job_id": job.id,
#         "booking_status": booking.status,
#         "created_items_count": len(created_items),
#         "items": [
#             {
#                 "id": item.id,
#                 "name": item.name,
#                 "price": str(item.price),
#                 "is_completed": item.is_completed,
#             }
#             for item in created_items
#         ]
#     }, status=status.HTTP_200_OK)

from decimal import Decimal
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status, permissions

from bookings.models import BookingRequest
from jobs.models import Job, JobItem


@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def landscaper_accept_booking(request, pk):
    landscaper = getattr(request.user, "landscaper_profile", None)

    if not landscaper:
        return Response(
            {"error": "Landscaper profile not found."},
            status=status.HTTP_403_FORBIDDEN
        )

    with transaction.atomic():
        try:
            booking = BookingRequest.objects.select_for_update().get(
                pk=pk,
                landscaper=landscaper,
                status=BookingRequest.Status.PENDING,
                is_active=True
            )
        except BookingRequest.DoesNotExist:
            return Response(
                {"error": "Pending booking not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if booking.job_created:
            return Response(
                {"error": "Job already created for this booking."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -----------------------------
        # CREATE JOB (DEFAULT UPCOMING)
        # -----------------------------
        job = Job.objects.create(
            booking=booking,
            client=booking.client,
            landscaper=booking.landscaper,
            job_property=booking.property,
            scheduled_date=booking.scheduled_date,
            scheduled_time=booking.scheduled_time,
            total_price=Decimal("0.00"),
            status=Job.Status.UPCOMING,
            is_active=True
        )

        # -----------------------------
        # CREATE JOB ITEMS
        # -----------------------------
        created_items = []
        for idx, booking_item in enumerate(
            booking.items.all().order_by("sort_order", "id")
        ):
            item = JobItem.objects.create(
                job=job,
                item_type=booking_item.item_type,
                service=booking_item.service,
                addon=booking_item.addon,
                name=booking_item.name,
                description=booking_item.description,
                price=booking_item.price,
                sort_order=idx,
            )
            created_items.append(item)

        # -----------------------------
        # INITIAL CALCULATIONS
        # -----------------------------
        job.recalculate_total_price()

        # IMPORTANT: use ONLY sync_status (no old method)
        job.sync_status()

        # -----------------------------
        # UPDATE BOOKING
        # -----------------------------
        booking.status = BookingRequest.Status.ACCEPTED
        booking.job_created = True
        booking.save(update_fields=["status", "job_created", "updated_at"])

    return Response({
        "message": "Booking accepted and job created successfully.",
        "booking_id": booking.id,
        "job_id": job.id,
        "booking_status": booking.status,
        "created_items_count": len(created_items),
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "price": str(item.price),
                "is_completed": item.is_completed,
            }
            for item in created_items
        ]
    }, status=status.HTTP_200_OK)