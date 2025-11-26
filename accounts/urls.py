from django.urls import path, include
from .views import (
    SignupView, 
    LoginView, 
    SendOTPView, 
    VerifyOTPView, 
    ResetPasswordView, 
    UserListView,
    AdminDeleteUserView
)

urlpatterns = [
    # Your custom authentication views
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    # path('admin/create/', AdminCreateView.as_view(), name='admin-create'),
    # path('check/token/', CheckTokenView.as_view(), name='check-token'),
    path('users-list/', UserListView.as_view(), name='user-list'),
    path("admin/delete-user/<int:id>/", AdminDeleteUserView.as_view(), name="admin-delete-user"),

]