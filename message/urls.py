from django.urls import path
from .views import (
    CreateOrGetThreadView,
    ThreadMessagesView,
    DeleteMessageView,
    UpdateMessageView
)

urlpatterns = [
    path("thread/create/", CreateOrGetThreadView.as_view(), name="create_or_get_thread"),
    path("thread/<int:thread_id>/messages/", ThreadMessagesView.as_view(), name="thread_messages"),
    path("message/<int:message_id>/delete/", DeleteMessageView.as_view(), name="delete_message"),
    path("message/<int:message_id>/update/", UpdateMessageView.as_view(), name="update_message"),
]
