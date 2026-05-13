from django.test import SimpleTestCase

from apps.containers.workspace_ws import (
    _build_upstream_ws_url,
    _cookie_value,
    _upstream_headers,
    _upstream_subprotocols,
)


class WorkspaceWebSocketProxyHelperTests(SimpleTestCase):
    def test_build_upstream_ws_url_removes_ticket_and_adds_jupyter_token(self):
        url = _build_upstream_ws_url(
            netloc="10.0.0.9:39021",
            path="/workspace/123/api/kernels/abc/channels",
            raw_query=b"session_id=s1&ticket=user-ticket",
            upstream_token="jupyter-secret",
        )

        self.assertEqual(
            url,
            "ws://10.0.0.9:39021/workspace/123/api/kernels/abc/channels"
            "?session_id=s1&token=jupyter-secret",
        )

    def test_upstream_subprotocols_strip_hypercube_auth_pair(self):
        protocols = _upstream_subprotocols([
            "v1.kernel.websocket.jupyter.org",
            "hypercube.jwt",
            "jwt-secret",
        ])

        self.assertEqual(protocols, ["v1.kernel.websocket.jupyter.org"])

    def test_upstream_headers_do_not_forward_browser_secrets_or_handshake(self):
        headers = _upstream_headers({
            "headers": [
                (b"host", b"public.example"),
                (b"cookie", b"hc_workspace_session=secret"),
                (b"authorization", b"Bearer secret"),
                (b"sec-websocket-key", b"key"),
                (b"x-request-id", b"req-1"),
            ]
        })

        self.assertEqual(headers, [("x-request-id", "req-1"), ("X-Forwarded-Proto", "ws")])

    def test_cookie_value_reads_workspace_session(self):
        value = _cookie_value({
            "headers": [
                (b"cookie", b"theme=dark; hc_workspace_session=session-value"),
            ]
        }, "hc_workspace_session")

        self.assertEqual(value, "session-value")
