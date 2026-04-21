from django.test import TestCase

from apps.users.serializers import UserListSerializer, UserSerializer

from .factories import create_user


class UserSerializerTest(TestCase):
    def test_full_serializer_fields(self):
        user = create_user(username="testfull")
        serializer = UserSerializer(user)
        expected = {"id", "username", "email", "role", "is_active", "date_joined"}
        self.assertEqual(set(serializer.data.keys()), expected)

    def test_list_serializer_fields(self):
        user = create_user(username="testlist")
        serializer = UserListSerializer(user)
        expected = {"id", "username", "role", "is_active"}
        self.assertEqual(set(serializer.data.keys()), expected)

    def test_password_not_exposed(self):
        user = create_user(username="testpw")
        serializer = UserSerializer(user)
        self.assertNotIn("password", serializer.data)
