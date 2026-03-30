from rest_framework import serializers

from .models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "role", "is_active", "date_joined"]
        read_only_fields = ["id", "date_joined"]
        extra_kwargs = {
            "email": {"required": True},
        }


class UserListSerializer(serializers.ModelSerializer):
    """목록 조회용 경량 시리얼라이저"""

    class Meta:
        model = CustomUser
        fields = ["id", "username", "role", "is_active"]
