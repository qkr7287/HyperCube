from django.test import TestCase

from apps.core.serializers import AuditLogSerializer, TemplateSerializer

from .factories import create_audit_log, create_template, create_user


class TemplateSerializerTest(TestCase):
    def test_contains_expected_fields(self):
        tpl = create_template()
        serializer = TemplateSerializer(tpl)
        expected = {
            "id",
            "name",
            "category",
            "config",
            "created_by",
            "created_by_username",
            "is_builtin",
            "created_at",
        }
        self.assertEqual(set(serializer.data.keys()), expected)


class AuditLogSerializerTest(TestCase):
    def test_all_fields_read_only(self):
        user = create_user(username="auditor")
        log = create_audit_log(user=user)
        serializer = AuditLogSerializer(log)
        expected = {"id", "user", "username", "action", "target", "timestamp"}
        self.assertEqual(set(serializer.data.keys()), expected)
