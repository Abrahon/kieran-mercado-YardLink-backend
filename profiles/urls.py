from django.urls import path
from .views import AdminProfileView,ChangePasswordView

urlpatterns = [
    path("admin/profile/", AdminProfileView.as_view(), name="admin-profile"),
    path('admin/change-password/',ChangePasswordView.as_view(), name="change-password")
]
