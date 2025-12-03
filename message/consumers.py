

# from channels.generic.websocket import AsyncWebsocketConsumer
# import json
# from django.contrib.auth import get_user_model
# from channels.db import database_sync_to_async

# # ✅ Wrap synchronous ORM operations
# @database_sync_to_async
# def get_thread_count():
#     from .models import ChatThread
#     return ChatThread.objects.count()

# @database_sync_to_async
# def save_message(thread_id, user_id, message):
#     from .models import Message
#     return Message.objects.create(
#         thread_id=thread_id,
#         sender_id=user_id,
#         text=message
#     )

# class ChatConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         self.user = self.scope["user"]

#         # ❌ Reject anonymous users to prevent null sender_id
#         if self.user.is_anonymous:
#             await self.close()  # Close the WebSocket immediately
#             return

#         self.thread_id = self.scope['url_route']['kwargs']['thread_id']
#         self.room_group_name = f'chat_{self.thread_id}'

#         # Add to channel layer group
#         await self.channel_layer.group_add(self.room_group_name, self.channel_name)
#         await self.accept()


#         # ✅ Async call to count threads
#         thread_count = await get_thread_count()
#         print("Total threads:", thread_count)

#     async def disconnect(self, close_code):
#         if hasattr(self, "room_group_name"):
#             await self.channel_layer.group_discard(self.room_group_name, self.channel_name)


#     async def receive(self, text_data=None, bytes_data=None):
#         if not text_data:
#             return
        
#         data = json.loads(text_data)
#         message = data.get("message")
#         user_id = self.user.id
#         print(user_id)

#         # ✅ Async call to save message
#         await save_message(self.thread_id, user_id, message)

#         # Send message to group
#         await self.channel_layer.group_send(
#             self.room_group_name,
#             {"type": "chat_message", "message": message, "sender_id": user_id}
#         )

#     async def chat_message(self, event):
#         await self.send(text_data=json.dumps(event))
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async

# Async-safe ORM functions
@database_sync_to_async
def get_thread_count():
    from .models import ChatThread
    return ChatThread.objects.count()

@database_sync_to_async
def save_message(thread_id, user_id, message):
    from .models import Message
    return Message.objects.create(
        thread_id=thread_id,
        sender_id=user_id,
        text=message
    )

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Skip auth check for testing
        self.user = self.scope.get("user", None)

        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        self.room_group_name = f'chat_{self.thread_id}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        thread_count = await get_thread_count()
        print("Total threads:", thread_count)
        

    async def disconnect(self, close_code):
        # ⚡ Safe discard in case connect never completed
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        data = json.loads(text_data)
        message = data.get("message")
        if not message:
            return

        user_id = self.user.id
        await save_message(self.thread_id, user_id, message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": message, "sender_id": user_id}
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
