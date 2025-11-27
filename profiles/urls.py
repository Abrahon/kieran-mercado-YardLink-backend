from django.urls import path
from .views import AdminProfileView

urlpatterns = [
    path("admin/profile/", AdminProfileView.as_view(), name="admin-profile"),
]
