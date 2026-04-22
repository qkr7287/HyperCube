from datetime import timedelta

from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet

from apps.common.permissions import IsViewer
from apps.containers.models import Container

from .models import ContainerMetricsHistory, SystemMetricsHistory
from .serializers import (
    ContainerMetricsHistoryDetailSerializer,
    ContainerMetricsHistorySerializer,
    SystemMetricsHistoryDetailSerializer,
    SystemMetricsHistorySerializer,
)

# Convenience shorthand → duration. Matches the frontend range tabs.
RANGE_SHORTHAND = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "10m": timedelta(minutes=10),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


class SystemMetricsFilter(filters.FilterSet):
    agent = filters.UUIDFilter(field_name="agent_id")
    from_time = filters.IsoDateTimeFilter(field_name="recorded_at", lookup_expr="gte")
    to_time = filters.IsoDateTimeFilter(field_name="recorded_at", lookup_expr="lte")

    class Meta:
        model = SystemMetricsHistory
        fields = ["agent", "from_time", "to_time"]


class ContainerMetricsFilter(filters.FilterSet):
    agent = filters.UUIDFilter(field_name="agent_id")
    container_id = filters.CharFilter(field_name="container_id")
    from_time = filters.IsoDateTimeFilter(field_name="recorded_at", lookup_expr="gte")
    to_time = filters.IsoDateTimeFilter(field_name="recorded_at", lookup_expr="lte")

    class Meta:
        model = ContainerMetricsHistory
        fields = ["agent", "container_id", "from_time", "to_time"]


@extend_schema_view(
    list=extend_schema(
        summary="시스템 메트릭 이력 조회",
        description="특정 Agent의 시스템 메트릭 시계열 데이터를 조회합니다. agent, from_time, to_time으로 필터링.",
    ),
    retrieve=extend_schema(
        summary="시스템 메트릭 상세 조회",
        description="단일 메트릭 레코드의 상세 정보 (raw_data 포함).",
    ),
)
class SystemMetricsViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    queryset = SystemMetricsHistory.objects.select_related("agent").all()
    filterset_class = SystemMetricsFilter
    ordering_fields = ["recorded_at"]
    ordering = ["-recorded_at"]
    permission_classes = [IsViewer]

    def get_queryset(self):
        qs = super().get_queryset()

        # `?range=1h` shorthand rolls into from_time/to_time; it overrides any
        # explicit from_time so the client never has to compute wall-clock.
        range_key = self.request.query_params.get("range")
        if range_key and range_key in RANGE_SHORTHAND:
            qs = qs.filter(recorded_at__gte=timezone.now() - RANGE_SHORTHAND[range_key])

        user = self.request.user
        if getattr(user, "role", None) == "admin":
            return qs

        owned_agent_ids = Container.objects.filter(
            requester=user
        ).values_list("agent_id", flat=True)
        return qs.filter(agent_id__in=owned_agent_ids)

    def list(self, request, *args, **kwargs):
        # `?limit=N` is a chart-friendly shortcut: return the N most-recent
        # samples ordered oldest→newest, skipping DRF pagination entirely.
        limit = request.query_params.get("limit")
        if limit:
            try:
                n = max(1, min(int(limit), 2000))
                qs = self.filter_queryset(self.get_queryset()).order_by("-recorded_at")[:n]
                rows = list(qs)[::-1]
                from rest_framework.response import Response
                return Response(self.get_serializer(rows, many=True).data)
            except (TypeError, ValueError):
                pass
        return super().list(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SystemMetricsHistoryDetailSerializer
        return SystemMetricsHistorySerializer


@extend_schema_view(
    list=extend_schema(
        summary="컨테이너 메트릭 이력 조회",
        description="특정 컨테이너의 메트릭 시계열 데이터를 조회합니다. agent, container_id, from_time, to_time으로 필터링.",
    ),
    retrieve=extend_schema(
        summary="컨테이너 메트릭 상세 조회",
        description="단일 메트릭 레코드의 상세 정보 (raw_data 포함).",
    ),
)
class ContainerMetricsViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    queryset = ContainerMetricsHistory.objects.select_related("agent").all()
    filterset_class = ContainerMetricsFilter
    ordering_fields = ["recorded_at"]
    ordering = ["-recorded_at"]
    permission_classes = [IsViewer]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, "role", None) == "admin":
            return qs

        owned_container_ids = Container.objects.filter(
            requester=user
        ).values_list("container_id", flat=True)
        return qs.filter(container_id__in=owned_container_ids)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ContainerMetricsHistoryDetailSerializer
        return ContainerMetricsHistorySerializer
