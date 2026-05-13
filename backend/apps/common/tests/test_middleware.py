from django.test import SimpleTestCase

from apps.common.middleware import _auth_from_subprotocols


class WebSocketAuthSubprotocolTests(SimpleTestCase):
    def test_extracts_jwt_auth_token_after_marker(self):
        protocol, token = _auth_from_subprotocols(["hypercube.jwt", "jwt-token"])

        self.assertEqual(protocol, "hypercube.jwt")
        self.assertEqual(token, "jwt-token")

    def test_extracts_agent_auth_token_after_marker(self):
        protocol, token = _auth_from_subprotocols(["hypercube.agent", "agent_token"])

        self.assertEqual(protocol, "hypercube.agent")
        self.assertEqual(token, "agent_token")

    def test_ignores_marker_without_following_token(self):
        protocol, token = _auth_from_subprotocols(["hypercube.jwt"])

        self.assertEqual(protocol, "")
        self.assertEqual(token, "")

    def test_ignores_unrelated_subprotocols(self):
        protocol, token = _auth_from_subprotocols(["chat", "jwt-token"])

        self.assertEqual(protocol, "")
        self.assertEqual(token, "")
