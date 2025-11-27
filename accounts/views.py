from django.shortcuts import render

# Create your views here.
from urllib.parse import urlencode, unquote
from .serializers import UserSerializer
import requests
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework import views

from .serializers import SignupSerializer, LoginSerializer, ResetPasswordSerializer
from .models import User, OTP
from django.utils import timezone
from .utils import generate_otp, send_otp_email 
from .serializers import (
    SendOTPSerializer, VerifyOTPSerializer, ResetPasswordSerializer
)



# class SignupView(generics.GenericAPIView):
#     serializer_class = SignupSerializer
#     permission_classes = [AllowAny]
#     parser_classes = (MultiPartParser, FormParser)

#     def post(self, request, *args, **kwargs):
#         """
#         Validate the signup data but DO NOT create the user yet.
#         Generate and send OTP to the provided email, and store OTP with the email.
#         """
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         email = serializer.validated_data.get("email")
#         name = serializer.validated_data.get("name", "")
#         # Save password and other fields in the serializer? We will require password when verifying OR
#         # you can optionally store hashed password temporarily in a secure table (not covered here)

#         # Prevent duplicate signup attempts if user already exists
#         if User.objects.filter(email__iexact=email).exists():
#             return Response({"detail": "User with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

#         # Delete previous OTPs for this email
#         OTP.objects.filter(email__iexact=email).delete()

#         otp_code = generate_otp()
#         OTP.objects.create(email=email, code=otp_code)

#         sent = send_otp_email(to_email=email, otp_code=otp_code, name=name)
#         if not sent:
#             # don't create user; let client retry later
#             return Response(
#                 {"detail": "Unable to send verification email right now. Please try again later."},
#                 status=status.HTTP_503_SERVICE_UNAVAILABLE
#             )

#         return Response({"detail": "Verification OTP sent to email."}, status=status.HTTP_200_OK)

class SignupView(generics.GenericAPIView):
    serializer_class = SignupSerializer
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        name = serializer.validated_data["name"]
        password = serializer.validated_data["password"]
        phone = serializer.validated_data.get("phone")
        address = serializer.validated_data.get("address")
        role = serializer.validated_data["role"]  

        # Check duplicate
        if User.objects.filter(email=email).exists():
            return Response({"detail": "User with this email already exists."}, status=400)

        # Save temporary user data in session
        request.session["pending_user"] = {
            "email": email,
            "name": name,
            "password": password,
            "phone": phone,
            "address": address,
            "role": role,   
        }

        # Delete previous OTPs
        OTP.objects.filter(email=email).delete()

        otp_code = generate_otp()
        OTP.objects.create(email=email, code=otp_code)

        sent = send_otp_email(email, otp_code, name)
        if not sent:
            return Response(
                {"detail": "Unable to send verification email right now."},
                status=503
            )

        return Response({"detail": "Verification OTP sent to email."}, status=200)



def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['name'] = user.name 
    refresh['email'] = user.email
    refresh['phone'] = user.phone
    refresh['address'] = user.address

     # optional
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token)
    }


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        print("user", user)

        # ---------------------------------------------------------
        # 🔥 CHANGE ADDED HERE → Check if user is NOT verified
        # ---------------------------------------------------------
        if not user.is_active:
            return Response(
                {"message": "Please verify your email first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------------------------------
        # 🔥 Login allowed only if email is verified
        # ---------------------------------------------------------
        tokens = get_tokens_for_user(user)
        print("tokens", tokens)

        return Response({
            "message": "Login successful",
            "token": tokens,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "phone": getattr(user, 'phone', None),      
                "address": getattr(user, 'address', None),  
            }
        }, status=status.HTTP_200_OK)




class SendOTPView(generics.CreateAPIView):
    serializer_class = SendOTPSerializer
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.save()  
        print("serializer.save() returned:", result)

        # ❌ ISSUE IS HERE:
        # serializer.save() is returning a User object, NOT a dict.
        # User object has NO .get() method — that's why error occurred:
        # AttributeError: 'User' object has no attribute 'get'

        email = serializer.validated_data.get("email")
        if email and hasattr(request, "session"):
            request.session['otp_user_email'] = email
            print("Stored in session:", email)

        return Response(
            {"message": "OTP sent successfully", "email": email},
            
            status=200
        )


# class VerifyOTPView(generics.GenericAPIView):
#     serializer_class = VerifyOTPSerializer
#     permission_classes = [AllowAny]
#     parser_classes = (MultiPartParser, FormParser)

#     def post(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data, context={"request": request})
#         serializer.is_valid(raise_exception=True)

#         user = serializer.validated_data["user"]

#         # ---------------------------------------------------------
#         # 🔥 CHANGE 5: Activate user after successful OTP
#         # ---------------------------------------------------------
#         user.is_active = True
#         user.save()

#         return Response({"message": "OTP verified successfully. Account activated."})



class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        otp_code = request.data.get("otp")

        if not email or not otp_code:
            return Response({"detail": "Email and OTP are required."}, status=400)

        # Get OTP
        try:
            otp_instance = OTP.objects.filter(email=email, code=otp_code).latest("created_at")
        except OTP.DoesNotExist:
            return Response({"detail": "OTP not found."}, status=400)

        # Check expired
        if otp_instance.is_expired():
            otp_instance.delete()
            return Response({"detail": "OTP expired."}, status=400)

        # Get pending user data from session
        pending = request.session.get("pending_user")
        if not pending or pending["email"] != email:
            return Response({"detail": "Signup data missing. Restart signup."}, status=400)

        # ✅ Create user with role
        user = User.objects.create_user(
            email=pending["email"],
            name=pending["name"],
            password=pending["password"],
            phone=pending['phone'],
            address=pending['address'],

            role=pending["role"],  
            is_active=True
        )

        # Cleanup
        otp_instance.delete()
        del request.session["pending_user"]

        return Response({"message": "Email verified and account created successfully."}, status=200)



# class VerifyOTPView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         email = request.data.get("email")
#         otp_code = request.data.get("otp")

#         if not email or not otp_code:
#             return Response({"detail": "Email and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

#         # Get OTP by email and code
#         try:
#             otp_instance = OTP.objects.filter(email=email, code=otp_code).latest("created_at")
#         except OTP.DoesNotExist:
#             return Response({"non_field_errors": ["OTP not found for this email."]}, status=status.HTTP_400_BAD_REQUEST)

#         # Check if OTP expired
#         if otp_instance.is_expired():
#             otp_instance.delete()
#             return Response({"non_field_errors": ["OTP expired."]}, status=status.HTTP_400_BAD_REQUEST)

#         # Create user if it doesn't exist
#         user, created = User.objects.get_or_create(
#             email=email,
#             defaults={"is_active": True}  # only set fields that exist
#         )

#         if not created:
#             # If user already exists, just activate
#             user.is_active = True
#             user.save()

#         # Associate OTP with user (optional)
#         otp_instance.user = user
#         otp_instance.delete()

#         return Response({"message": "OTP verified and user created successfully."}, status=status.HTTP_200_OK)

class ResetPasswordView(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        """
        Request body must include:
        {
            "email": "user@example.com",
            "otp": "123456",
            "new_password": "newStrongPassword123",
            "confirm_password": "newStrongPassword123"
        }
        """
        email = request.data.get("email")
        otp_code = request.data.get("otp")
        print("otp_code",otp_code)

        if not email or not otp_code:
            return Response(
                {"detail": "Email and OTP are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1️⃣ Verify user exists
        user = User.objects.filter(email=email).first()
        print("user", user)

        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        # 2️⃣ Verify OTP
        # otp = OTP.objects.filter(user=user, code=str(otp_code)).order_by("-created_at").first()
        otp = OTP.objects.filter(user=user, code=str(otp_code).strip()).order_by("-created_at").first()
        print("otp", otp)
        if not otp:
            return Response({"detail": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if otp.is_expired():
            return Response({"detail": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

        # 3️⃣ OTP valid → delete OTP to prevent reuse
        otp.delete()

        # 4️⃣ Reset password
        serializer = self.get_serializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)
    

# role wise filtering user client landscaper


class UserListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            role = request.query_params.get("role")

            users = User.objects.all()

            # 🔥 Filter by role if provided
            if role:
                users = users.filter(role=role)

            # 📌 Stats
            total_users = User.objects.count()
            total_clients = User.objects.filter(role="client").count()
            total_landscapers = User.objects.filter(role="landscaper").count()

            # 🔥 Daily active users (last 24 hours)
            last_24h = timezone.now() - timedelta(hours=24)
            daily_active_users = User.objects.filter(last_login__gte=last_24h).count()

            serializer = UserSerializer(users, many=True)

            return Response({
                "status": "success",
                "summary": {
                    "total_users": total_users,
                    "total_clients": total_clients,
                    "total_landscapers": total_landscapers,
                    "daily_active_users": daily_active_users,
                },
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



# delete user admin and own user

class AdminDeleteUserView(generics.DestroyAPIView):
    """
    Admin can delete any user by ID safely (avoiding django_admin_log FK issues)
    """
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    lookup_field = "id"

    def delete(self, request, *args, **kwargs):
        # Get the user to delete
        user = self.get_object()

        # Prevent deleting superuser accidentally
        if user.is_superuser:
            return Response(
                {"detail": "Cannot delete a superuser."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Temporarily set request.user to a superuser to avoid admin log FK issues
        if not request.user.is_superuser:
            superuser = User.objects.filter(is_superuser=True).first()
            if superuser:
                request.user = superuser

        # Delete the user
        user.delete()

        return Response(
            {"detail": f"User {user.email} deleted successfully."},
            status=status.HTTP_200_OK
        )



