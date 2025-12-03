# chat/serializers.py
from django.conf import settings
from rest_framework import serializers
from .models import Message, ChatThread
from django.core.files.uploadedfile import UploadedFile
import imghdr
import os

ALLOWED_EXTENSIONS = getattr(settings, "CHAT_ALLOWED_FILE_EXTENSIONS", ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.docx', '.xlsx'])
MAX_UPLOAD_SIZE = getattr(settings, "CHAT_MAX_UPLOAD_SIZE", 8 * 1024 * 1024)


def get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def is_image_file(uploaded_file: UploadedFile) -> bool:
    """
    Basic image check using imghdr — it's conservative but helps.
    For production you may want to use python-magic lib for better detection.
    """
    try:
        # imghdr.what() requires a file-like object with read() and seek()
        uploaded_file.seek(0)
        kind = imghdr.what(uploaded_file)
        uploaded_file.seek(0)
        return kind is not None
    except Exception:
        return False


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for Message model.
    - sender is read-only and taken from request.user in create()
    - message_type is read-only (computed)
    - file validation enforced here
    """
    sender = serializers.PrimaryKeyRelatedField(read_only=True)
    file_url = serializers.SerializerMethodField(read_only=True)
    message_type = serializers.ReadOnlyField()

    class Meta:
        model = Message
        # Explicit fields help avoid accidentally exposing internal fields.
        fields = [
            'id', 'thread', 'sender', 'text', 'file', 'file_url',
            'message_type', 'created_at' "is_deleted","updated_at",
        
            
        ]
        read_only_fields = ['id', 'sender', 'file_url', 'message_type', 'created_at'"updated_at",'is_deleted']

    def validate_thread(self, value):
        # Basic check: thread must exist (DRF will already validate PK -> object)
        if value is None:
            raise serializers.ValidationError("thread is required.")
        return value

    def validate_file(self, uploaded_file):
        """
        Validate uploaded file:
        - size
        - extension allowed
        - optional image detection
        """
        if uploaded_file is None:
            return None

        if not isinstance(uploaded_file, UploadedFile):
            # If frontend passes a URL or string, don't attempt file validation here.
            # We allow None or UploadedFile here. If you want to support remote URLs,
            # handle them separately.
            raise serializers.ValidationError("Invalid file object.")

        # size check
        if uploaded_file.size > MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(f"File too large. Max size is {MAX_UPLOAD_SIZE} bytes.")

        # extension check
        ext = get_extension(uploaded_file.name)
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(f"File extension '{ext}' is not allowed.")

        # If the extension looks like an image, verify content is an image.
        if ext in ('.jpg', '.jpeg', '.png', '.gif'):
            if not is_image_file(uploaded_file):
                raise serializers.ValidationError("Uploaded file's content does not match an image format.")

        return uploaded_file

    def validate(self, attrs):
        """
        Enforce at least text or file present for a message.
        """
        text = attrs.get('text', '') or ''
        file_obj = attrs.get('file', None)

        if not text.strip() and not file_obj:
            raise serializers.ValidationError("Either 'text' or 'file' must be provided.")

        return attrs

    def create(self, validated_data):
        """
        Create message:
        - set sender from request.user (do not trust client)
        - compute message_type automatically
        - ensure sender belongs to thread
        """
        request = self.context.get('request')
        if not request or not request.user or request.user.is_anonymous:
            raise serializers.ValidationError("Authentication required to send messages.")

        sender = request.user
        thread = validated_data.get('thread')

        # Check sender is participant in thread (adjust according to your ChatThread model)
        # Here we assume ChatThread has client and landscaper foreign keys.
        if not (thread.client_id == sender.id or thread.landscaper_id == sender.id):
            raise serializers.ValidationError("You are not a participant of this chat thread.")

        # Decide message_type
        file_obj = validated_data.get('file', None)
        text = validated_data.get('text', '') or ''

        if file_obj:
            ext = get_extension(file_obj.name)
            if ext in ('.jpg', '.jpeg', '.png', '.gif'):
                message_type = 'image'
            else:
                message_type = 'file'
        else:
            # option: if this is a special 'request' message triggered by flow,
            # the caller/view can set a flag or you can detect via thread state.
            message_type = 'text'

        # Save message
        message = Message.objects.create(
            thread=thread,
            sender=sender,
            text=text,
            file=file_obj,
        )
        # if your model has a message_type field, update it
        # (the example model used a property; if it's a DB field, set it here)
        if hasattr(message, 'message_type') and not getattr(message, 'message_type'):
            # If message_type is a real field on model, set it:
            try:
                message.message_type = message_type
                message.save(update_fields=['message_type'])
            except Exception:
                # If message_type is a read-only property, ignore
                pass

        return message

    def get_file_url(self, obj):
        request = self.context.get('request', None)
        if not obj.file:
            return None
        try:
            if request is not None:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        except Exception:
            return None


class ChatThreadSerializer(serializers.ModelSerializer):
    """
    Serializer for ChatThread model.
    - Provide creation validation so a duplicate thread between same users is not created.
    - Expose embedded last message optionally (read-only).
    """
    # If you want nested participant info you can expand these fields
    client = serializers.PrimaryKeyRelatedField(queryset=ChatThread._meta.get_field('client').related_model.objects.all())
    landscaper = serializers.PrimaryKeyRelatedField(queryset=ChatThread._meta.get_field('landscaper').related_model.objects.all())
    last_message = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ChatThread
        fields = ['id', 'client', 'landscaper', 'created_at', 'last_message']
        read_only_fields = ['id', 'created_at', 'last_message']

    def validate(self, attrs):
        client = attrs.get('client')
        landscaper = attrs.get('landscaper')

        if client == landscaper:
            raise serializers.ValidationError("client and landscaper must be different users.")

        # Optionally: enforce that both users exist and have correct roles (if you have role system)
        # e.g., if you have User.role and want landscaper.role == 'landscaper' enforce here.

        return attrs

    def create(self, validated_data):
        """
        Create a single thread between client & landscaper if not exists.
        """
        client = validated_data.get('client')
        landscaper = validated_data.get('landscaper')

        # Avoid duplicate threads — change the query according to your schema/indexes
        existing = ChatThread.objects.filter(client=client, landscaper=landscaper).first()
        if existing:
            return existing

        thread = ChatThread.objects.create(client=client, landscaper=landscaper)
        return thread

    def get_last_message(self, obj):
        last = obj.messages.order_by('-created_at').first()
        if not last:
            return None
        # use MessageSerializer to represent last message; must pass context
        return MessageSerializer(last, context=self.context).data
