# chat/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import ChatThread
from .serializers import ChatThreadSerializer

User = get_user_model()

class CreateOrGetThreadView(APIView):
    def post(self, request):
        client_id = request.data.get("client_id")
        landscaper_id = request.data.get("landscaper_id")

        if not client_id or not landscaper_id:
            return Response({"error": "client_id & landscaper_id required"}, status=400)

        try:
            client = User.objects.get(id=client_id)
            landscaper = User.objects.get(id=landscaper_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        thread, created = ChatThread.objects.get_or_create(
            client=client,
            landscaper=landscaper
        )

        serializer = ChatThreadSerializer(thread)
        return Response({"thread": serializer.data, "created": created})
    
class ThreadMessagesView(APIView):
    def get(self, request, thread_id):
        try:
            thread = ChatThread.objects.get(id=thread_id)
        except ChatThread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=404)

        messages = thread.messages.all().order_by("created_at")
        from .serializers import MessageSerializer
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

class DeleteMessageView(APIView):
    def delete(self, request, message_id):
        from .models import Message

        try:
            msg = Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            return Response({"error": "Message not found"}, status=404)

        msg.is_deleted = True
        msg.text = None
        msg.file = None
        msg.save()

        return Response({"message": "Deleted successfully"})

class UpdateMessageView(APIView):
    def patch(self, request, message_id):
        from .models import Message

        try:
            msg = Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            return Response({"error": "Message not found"}, status=404)

        new_text = request.data.get("text")
        if not new_text:
            return Response({"error": "Text is required"}, status=400)

        msg.text = new_text
        msg.save()

        return Response({"message": "Updated", "text": msg.text})
