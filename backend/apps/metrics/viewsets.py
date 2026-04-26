from datetime import timedelta

from django.db.models import Avg, Count, IntegerField, Max
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
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
    "30d": timedelta(days=30),
}

# Bucket shorthand → seconds. Frontend can also pass a raw integer seconds value.
BUCKET_SHORTHAND = {
    "30s": 30,
    "1m": 60,
    "5m": 300,
    "10m": 600,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
    "1w": 604800,
}


def _parse_bucket_seconds(raw: str | None, default: int = 60) -> int:
    """Accept '1h' / '5m' / '86400' style values; clamp to a sane range."""
    if not raw:
        return default
    if raw in BUCKET_SHORTHAND:
        return BUCKET_SHORTHAND[raw]
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(10, min(n, 30 * 86400))


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

    @extend_schema(
        summary="시스템 메트릭 bucket 집계",
        description=(
            "Agent별로 지정한 bucket 단위로 평균/최대치를 집계해 반환합니다. "
            "?range=7d&bucket=1d → 7일 동안 하루 단위 집계. ?bucket은 단축어(1m/5m/1h/1d/1w 등) 또는 초 단위 정수."
        ),
    )
    @action(detail=False, methods=["get"], url_path="buckets")
    def buckets(self, request):
        bucket_sec = _parse_bucket_seconds(request.query_params.get("bucket"), default=60)
        qs = self.filter_queryset(self.get_queryset())
        # PostgreSQL: floor(epoch / N) * N → bucket start in epoch seconds.
        bucket_expr = RawSQL(
            "(floor(extract(epoch from recorded_at) / %s) * %s)::bigint",
            (bucket_sec, bucket_sec),
            output_field=IntegerField(),
        )
        rows = (
            qs.annotate(bucket_epoch=bucket_expr)
            .values("agent_id", "bucket_epoch")
            .annotate(
                cpu_avg=Avg("cpu_usage"),
                cpu_max=Max("cpu_usage"),
                memory_avg=Avg("memory_usage"),
                memory_max=Max("memory_usage"),
                memory_used_avg=Avg("memory_used"),
                memory_total_avg=Avg("memory_total"),
                disk_avg=Avg("disk_usage"),
                disk_max=Max("disk_usage"),
                network_rx_max=Max("network_rx"),
                network_tx_max=Max("network_tx"),
                sample_count=Count("id"),
            )
            .order_by("agent_id", "bucket_epoch")
        )
        results = [
            {
                "agent": str(r["agent_id"]),
                "bucket_epoch": int(r["bucket_epoch"]),
                "bucket_start": timezone.datetime.fromtimestamp(
                    int(r["bucket_epoch"]), tz=timezone.get_current_timezone()
                ).isoformat(),
                "cpu_avg": round(r["cpu_avg"] or 0, 2),
                "cpu_max": round(r["cpu_max"] or 0, 2),
                "memory_avg": round(r["memory_avg"] or 0, 2),
                "memory_max": round(r["memory_max"] or 0, 2),
                "memory_used_avg": int(r["memory_used_avg"] or 0),
                "memory_total_avg": int(r["memory_total_avg"] or 0),
                "disk_avg": round(r["disk_avg"] or 0, 2),
                "disk_max": round(r["disk_max"] or 0, 2),
                "network_rx_max": int(r["network_rx_max"] or 0),
                "network_tx_max": int(r["network_tx_max"] or 0),
                "sample_count": int(r["sample_count"] or 0),
            }
            for r in rows
        ]
        return Response({"bucket_seconds": bucket_sec, "results": results})


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

        range_key = self.request.query_params.get("range")
        if range_key and range_key in RANGE_SHORTHAND:
            qs = qs.filter(recorded_at__gte=timezone.now() - RANGE_SHORTHAND[range_key])

        user = self.request.user
        if getattr(user, "role", None) == "admin":
            return qs

        owned_container_ids = Container.objects.filter(
            requester=user
        ).values_list("container_id", flat=True)
        return qs.filter(container_id__in=owned_container_ids)

    def list(self, request, *args, **kwargs):
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
            return ContainerMetricsHistoryDetailSerializer
        return ContainerMetricsHistorySerializer

    @extend_schema(
        summary="컨테이너 메트릭 bucket 집계",
        description=(
            "컨테이너별로 지정한 bucket 단위로 평균/최대치를 집계해 반환합니다. "
            "?bucket은 단축어(1m/5m/1h/1d/1w 등) 또는 초 단위 정수."
        ),
    )
    @action(detail=False, methods=["get"], url_path="buckets")
    def buckets(self, request):
        bucket_sec = _parse_bucket_seconds(request.query_params.get("bucket"), default=60)
        qs = self.filter_queryset(self.get_queryset())
        bucket_expr = RawSQL(
            "(floor(extract(epoch from recorded_at) / %s) * %s)::bigint",
            (bucket_sec, bucket_sec),
            output_field=IntegerField(),
        )
        rows = (
            qs.annotate(bucket_epoch=bucket_expr)
            .values("agent_id", "container_id", "bucket_epoch")
            .annotate(
                cpu_avg=Avg("cpu_usage"),
                cpu_max=Max("cpu_usage"),
                memory_avg=Avg("memory_usage"),
                memory_max=Max("memory_usage"),
                memory_percent_avg=Avg("memory_percent"),
                network_rx_max=Max("network_rx"),
                network_tx_max=Max("network_tx"),
                disk_read_max=Max("disk_read"),
                disk_write_max=Max("disk_write"),
                sample_count=Count("id"),
            )
            .order_by("agent_id", "container_id", "bucket_epoch")
        )
        results = [
            {
                "agent": str(r["agent_id"]),
                "container_id": r["container_id"],
                "bucket_epoch": int(r["bucket_epoch"]),
                "bucket_start": timezone.datetime.fromtimestamp(
                    int(r["bucket_epoch"]), tz=timezone.get_current_timezone()
                ).isoformat(),
                "cpu_avg": round(r["cpu_avg"] or 0, 2),
                "cpu_max": round(r["cpu_max"] or 0, 2),
                "memory_avg": float(r["memory_avg"] or 0),
                "memory_max": float(r["memory_max"] or 0),
                "memory_percent_avg": round(r["memory_percent_avg"] or 0, 2),
                "network_rx_max": int(r["network_rx_max"] or 0),
                "network_tx_max": int(r["network_tx_max"] or 0),
                "disk_read_max": int(r["disk_read_max"] or 0),
                "disk_write_max": int(r["disk_write_max"] or 0),
                "sample_count": int(r["sample_count"] or 0),
            }
            for r in rows
        ]
        return Response({"bucket_seconds": bucket_sec, "results": results})
