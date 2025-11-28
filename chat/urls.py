from django.urls import path
from .views import (
    ContactMessageCreateAPIView,
    AdminContactMessageListAPIView,
    AdminReplyAPIView,
    AdminContactMessageDeleteAPIView,
    AdminUpdateContactMessageAPIView,

)

urlpatterns = [
    # ---------------------------
    # User endpoints
    # ---------------------------
    path('send/contact/', ContactMessageCreateAPIView.as_view(), name='contact-create'),
    # ---------------------------
    # Admin endpoints
    # ---------------------------
    path('admin/list/contact/', AdminContactMessageListAPIView.as_view(), name='admin-message-list'),
    path('admin/messages/<int:id>/reply/', AdminReplyAPIView.as_view(), name='admin-message-reply'),
    path('admin/messages/<int:id>/delete/', AdminContactMessageDeleteAPIView.as_view(), name='admin-message-delete'),
    path('admin/messages/<int:id>/update/', AdminUpdateContactMessageAPIView.as_view(), name='admin-message-update'),
]
