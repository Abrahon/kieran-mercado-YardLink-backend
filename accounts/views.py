from django.shortcuts import render

# Create your views here.
from urllib.parse import urlencode, unquote
from .serializers import UserSerializer
import requests
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


from .serializers import SignupSerializer, LoginSerializer, ResetPasswordSerializer
from .models import User, OTP


from .serializers import (
    SendOTPSerializer, VerifyOTPSerializer, ResetPasswordSerializer
)



class SignupView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # ---------------------------------------------------------
        # 🔥 CHANGE 1: Create user as INACTIVE until email verified
        # ---------------------------------------------------------
        user = serializer.save(is_active=False)  
        # user.is_active = False  # optional (if serializer doesn't handle)
        user.save()

        # ---------------------------------------------------------
        # 🔥 CHANGE 2: Generate OTP for this user
        # ---------------------------------------------------------
        otp_code = str(random.randint(100000, 999999))
        OTP.objects.create(user=user, code=otp_code)

        # ---------------------------------------------------------
        # 🔥 CHANGE 3: Send email containing OTP
        # ---------------------------------------------------------
        send_mail(
            subject="Verify Your Account",
            message=f"Your verification code is: {otp_code}",
            from_email="noreply@yourapp.com",
            recipient_list=[user.email],
            fail_silently=False,
        )

        # ---------------------------------------------------------
        # 🔥 CHANGE 4: Return response notifying OTP sent
        # ---------------------------------------------------------
        return Response({
            "message": "User created successfully. Verification OTP sent to email.",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
            }
        }, status=status.HTTP_201_CREATED)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['name'] = user.name 
    refresh['email'] = user.email 
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

#         # OTP verified → keep email in session for password reset
#         request.session['verified_email'] = serializer.validated_data["user"].email

#         return Response({"message": "OTP verified successfully."})


class VerifyOTPView(generics.GenericAPIView):
    serializer_class = VerifyOTPSerializer
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        # ---------------------------------------------------------
        # 🔥 CHANGE 5: Activate user after successful OTP
        # ---------------------------------------------------------
        user.is_active = True
        user.save()

        return Response({"message": "OTP verified successfully. Account activated."})



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


