# apps/contact/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from .models import ContactMessage, MessageStatus
from .serializers import ContactMessageSerializer,AdminUpdateSerializer,AdminUpdateSerializer



# ---------------------------
# User sends message
# ---------------------------
class ContactMessageCreateAPIView(generics.CreateAPIView):
    serializer_class = ContactMessageSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        serializer.save()  # Don't pass user here



# ---------------------------
# Admin lists all messages
# ---------------------------
class AdminContactMessageListAPIView(generics.ListAPIView):
    serializer_class = ContactMessageSerializer
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        return ContactMessage.objects.all().order_by("-created_at")


# ---------------------------
# Admin replies to user email
# ---------------------------



class AdminReplyAPIView(generics.UpdateAPIView):
    serializer_class = AdminUpdateSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = ContactMessage.objects.all()
    lookup_field = 'id'

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Update status and replied timestamp
        instance.status = MessageStatus.REPLIED
        instance.replied_at = timezone.now()
        instance.save()

        # Send email via Gmail
        recipient = instance.user.email if instance.user else None
        if recipient and instance.admin_reply:
            send_mail(
                subject='Reply to your message',
                message=f"Hi {instance.name},\n\n{instance.admin_reply}\n\nBest regards,\nAdmin Team",
                from_email=None,  # will use DEFAULT_FROM_EMAIL
                recipient_list=[recipient],
                fail_silently=False,
            )

        return Response({
            'success': 'Reply sent successfully via email',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

# ---------------------------
# Admin deletes message
# ---------------------------
class AdminContactMessageDeleteAPIView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAdminUser]
    queryset = ContactMessage.objects.all()
    lookup_field = "id"

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(
                {"success": "Message deleted successfully"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to delete message: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
 
            )
        

# apps/contact/views.py
class AdminUpdateContactMessageAPIView(generics.UpdateAPIView):
    serializer_class = AdminUpdateSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = ContactMessage.objects.all()
    lookup_field = "id"

    def patch(self, request, *args, **kwargs):
        """
        Allow partial update (category, status, admin_reply)
        """
        return self.partial_update(request, *args, **kwargs)
