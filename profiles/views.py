from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from .models import AdminProfile
from .serializers import AdminProfileSerializer

class AdminProfileView(RetrieveUpdateAPIView):
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self):
        # Get the AdminProfile for the logged-in user, create if missing
        profile, _ = AdminProfile.objects.get_or_create(user=self.request.user)
        return profile
