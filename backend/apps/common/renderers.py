from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """
    Frontend 호환용 응답 래퍼.
    모든 응답을 {success, data, error} envelope로 감싼다.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response")
        # 204 No Content 는 RFC 7230 상 body 금지. envelope 으로 감싸면
        # content-length 가 0이 아니게 돼 Chrome 이 "Failed to fetch" 로
        # 거부함. DELETE 응답 같은 No Content 케이스는 그대로 빈 응답으로.
        if response is not None and response.status_code == 204:
            return b""
        if response is not None and response.status_code >= 400:
            envelope = {"success": False, "error": data}
        else:
            envelope = {"success": True, "data": data}
        return super().render(envelope, accepted_media_type, renderer_context)
