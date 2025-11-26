
from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from django.core.validators import RegexValidator
from .models import OTP
from .utils import generate_otp, send_otp_email

User = get_user_model() 


# ---------------------------
# SIGNUP SERIALIZER
# ---------------------------
from rest_framework import serializers
from django.core.validators import RegexValidator
from .models import User, RoleChoices  # make sure RoleChoices exists

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            "min_length": "Password must be at least 8 characters long.",
            "blank": "Password field cannot be empty.",
        },
    )
    confirm_password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            "min_length": "Confirm password must be at least 8 characters long.",
            "blank": "Confirm password field cannot be empty.",
        },
    )

    name = serializers.CharField(
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z\s]+$",
                message="Name can only contain letters and spaces.",
            )
        ],
        error_messages={
            "blank": "Name field is required.",
            "required": "Please provide your name.",
        },
    )

    role = serializers.ChoiceField(
        choices=RoleChoices.choices,  # ❗ user must send role; no default
        error_messages={"required": "Role field is required."},
    )

    class Meta:
        model = User
        fields = ["name", "email", "password", "confirm_password", "role"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("confirm_password"):
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs

    # ❌ REMOVE create() in OTP flow!
    # User creation happens in VerifyOTPView after OTP is verified


# ---------------------------
# LOGIN SERIALIZER
# ---------------------------
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        user = authenticate(email=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")
        attrs["user"] = user
        return attrs



class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value

    def create(self, validated_data):
        # 1️⃣ Get the user
        user = User.objects.get(email=validated_data["email"])

        # 2️⃣ Generate OTP
        code = generate_otp()
        OTP.objects.create(user=user, code=code)

        # 3️⃣ Send OTP via email
        send_otp_email(user.email, code, name=user.name)

        # 4️⃣ Return the user object (not a dict) so the view can access user.email
        return user


# ---------------------------
# VERIFY OTP SERIALIZER
# ---------------------------


from rest_framework import serializers
from .models import OTP

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, data):
        email = data.get('email')
        otp_code = data.get('otp')

        # check OTP exists
        try:
            otp = OTP.objects.filter(email=email).latest('created_at')
        except OTP.DoesNotExist:
            raise serializers.ValidationError("OTP not found for this email.")

        if otp.is_expired():
            raise serializers.ValidationError("OTP expired.")

        if otp.code != otp_code:
            raise serializers.ValidationError("Invalid OTP.")

        data['otp_instance'] = otp
        return data

# ---------------------------
# RESET PASSWORD SERIALIZER
# ---------------------------
class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField(min_length=8)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match.")

        user = self.context.get("user")
        if not user:
            raise serializers.ValidationError("OTP verification required.")
        self.user = user
        return attrs

    def save(self, **kwargs):
        self.user.set_password(self.validated_data["new_password"])
        self.user.save()
        OTP.objects.filter(user=self.user).delete()
        return self.user


# ---------------------------
# CHANGE PASSWORD SERIALIZER
# ---------------------------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField(min_length=8)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError("Old password is incorrect.")
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match.")
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'role', 'is_active', 'date_joined']