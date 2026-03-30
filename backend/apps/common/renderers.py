from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """
    Frontend 호환용 응답 래퍼.
    모든 응답을 {success, data, error} envelope로 감싼다.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response")
        if response is not None and response.status_code >= 400:
            envelope = {"success": False, "error": data}
        else:
            envelope = {"success": True, "data": data}
        return super().render(envelope, accepted_media_type, renderer_context)
