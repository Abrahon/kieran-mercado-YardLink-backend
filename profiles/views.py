from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from .models import AdminProfile
from .serializers import AdminProfileSerializer,ChangePasswordSerializer
from rest_framework import generics, permissions
from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import update_session_auth_hash

class AdminProfileView(RetrieveUpdateAPIView):
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        # Get the AdminProfile for the logged-in user, create if missing
        profile, _ = AdminProfile.objects.get_or_create(user=self.request.user)
        return profile


# ---------------------- Change Password ---------------------- #
class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    
    permission_classes = [permissions.IsAdminUser]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            instance=self.get_object(),
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        update_session_auth_hash(request, serializer.instance)
        return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)