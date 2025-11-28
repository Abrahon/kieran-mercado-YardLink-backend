
from rest_framework import serializers
from .models import ContactMessage

class ContactMessageSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField(read_only=True)  # Auto get email from user

    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'message', 'category', 'status', 'created_at', 'replied_at']
        read_only_fields = ['id', 'email', 'status', 'created_at', 'replied_at']

    def get_email(self, obj):
        return obj.user.email

    def create(self, validated_data):
        user = self.context['request'].user
        return ContactMessage.objects.create(user=user, **validated_data)
