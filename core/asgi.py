# import os

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# from django.core.asgi import get_asgi_application
# from channels.routing import ProtocolTypeRouter, URLRouter
# from channels.auth import AuthMiddlewareStack
# import message.routing  # your websocket urls

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),
#     "websocket": AuthMiddlewareStack(
#         URLRouter(
#             message.routing.websocket_urlpatterns
#         )
#     ),
# })

import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import message.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Django ASGI application for HTTP requests
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,  # handles normal HTTP requests
    "websocket": AuthMiddlewareStack(
        URLRouter(
            message.routing.websocket_urlpatterns  # your websocket urls
        )
    ),
})

