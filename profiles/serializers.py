from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import AdminProfile
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext as _

User = get_user_model()

class AdminProfileSerializer(serializers.ModelSerializer):
    # Read-only fields from User model
    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)

    # Image field for upload (Cloudinary)
    image = serializers.ImageField(required=False)

    class Meta:
        model = AdminProfile
        fields = ["name", "email", "role", "phone", "image"]
        read_only_fields = ["name", "email", "role"]

    def get_image(self, obj):
        """Return Cloudinary URL"""
        if obj.image:
            return obj.image.url
        return None

    def update(self, instance, validated_data):
        # Update phone
        instance.phone = validated_data.get("phone", instance.phone)

        # Update image if provided
        image = validated_data.get("image")
        if image:
            instance.image = image  # Cloudinary handles upload automatically

        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True, required=True,
        style={'input_type': 'password'},
        error_messages={'required': _('Current password is required')}
    )
    new_password = serializers.CharField(
        write_only=True, required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
        error_messages={'required': _('New password is required')}
    )
    confirm_new_password = serializers.CharField(
        write_only=True, required=True,
        style={'input_type': 'password'},
        error_messages={'required': _('Please confirm your new password')}
    )

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_('Current password is incorrect'))
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({'confirm_new_password': _('New passwords do not match')})
        if attrs['current_password'] == attrs['new_password']:
            raise serializers.ValidationError({'new_password': _('New password cannot be the same as the current password')})
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user