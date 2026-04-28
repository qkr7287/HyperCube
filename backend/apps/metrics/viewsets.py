from datetime import timedelta

import hashlib

from django.core.cache import cache
from django.db import connection
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

# Cache: which DB columns actually exist on container_metrics_history.
# 모델에 필드가 있어도 마이그레이션이 안 돌면 DB엔 컬럼이 없음.
# information_schema 직접 조회로 정확히 검사.
_DB_COLUMNS_CACHE: dict[str, set[str]] = {}


def _db_columns(table_name: str) -> set[str]:
    cached = _DB_COLUMNS_CACHE.get(table_name)
    if cached is not None:
        return cached
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                [table_name],
            )
            cols = {row[0] for row in cur.fetchall()}
    except Exception:
        cols = set()
    _DB_COLUMNS_CACHE[table_name] = cols
    return cols


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


# 24h/7d 집계는 수백만 row를 GROUP BY해야 해서 한 번 계산하면 60s 캐시.
# Cache key는 path + 정렬된 query params + user 단위로 분리해서 권한 누수 방지.
_BUCKET_CACHE_TTL = 60


def _make_cache_key(prefix: str, request, bucket_sec: int) -> str:
    params = sorted(request.query_params.items())
    user_id = getattr(request.user, "id", "anon")
    raw = f"{prefix}|{user_id}|{bucket_sec}|" + "&".join(f"{k}={v}" for k, v in params)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"metrics:buckets:{digest}"


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
        cache_key = _make_cache_key("system", request, bucket_sec)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = self.filter_queryset(self.get_queryset())
        # PostgreSQL: floor(epoch / N) * N → bucket start in epoch seconds.
        bucket_expr = RawSQL(
            "(floor(extract(epoch from recorded_at) / %s) * %s)::bigint",
            (bucket_sec, bucket_sec),
            output_field=IntegerField(),
        )
        # 신규 GPU / memory_available 컬럼은 migration 0005 적용된 환경만. 미적용
        # 환경에선 annotation 자체를 건너뛰어 OperationalError 회피.
        sys_cols = _db_columns(SystemMetricsHistory._meta.db_table)
        annotations = dict(
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
        if "memory_available" in sys_cols:
            annotations["memory_available_avg"] = Avg("memory_available")
        if "gpu_usage" in sys_cols:
            annotations["gpu_avg"] = Avg("gpu_usage")
            annotations["gpu_max"] = Max("gpu_usage")
        if "gpu_memory_used" in sys_cols:
            annotations["gpu_memory_used_avg"] = Avg("gpu_memory_used")
        if "gpu_memory_total" in sys_cols:
            annotations["gpu_memory_total_avg"] = Avg("gpu_memory_total")
        if "gpu_temperature_max" in sys_cols:
            annotations["gpu_temperature_max"] = Max("gpu_temperature_max")
        rows = (
            qs.annotate(bucket_epoch=bucket_expr)
            .values("agent_id", "bucket_epoch")
            .annotate(**annotations)
            .order_by("agent_id", "bucket_epoch")
        )
        results = []
        for r in rows:
            row = {
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
            # null 은 그대로 전달 — frontend 가 "데이터 없음" 으로 처리하도록.
            if "memory_available_avg" in r:
                row["memory_available_avg"] = (
                    int(r["memory_available_avg"]) if r["memory_available_avg"] is not None else None
                )
            if "gpu_avg" in r:
                row["gpu_avg"] = round(r["gpu_avg"], 2) if r["gpu_avg"] is not None else None
                row["gpu_max"] = round(r["gpu_max"], 2) if r["gpu_max"] is not None else None
            if "gpu_memory_used_avg" in r:
                row["gpu_memory_used_avg"] = (
                    int(r["gpu_memory_used_avg"]) if r["gpu_memory_used_avg"] is not None else None
                )
            if "gpu_memory_total_avg" in r:
                row["gpu_memory_total_avg"] = (
                    int(r["gpu_memory_total_avg"]) if r["gpu_memory_total_avg"] is not None else None
                )
            if "gpu_temperature_max" in r:
                row["gpu_temperature_max"] = (
                    round(r["gpu_temperature_max"], 1) if r["gpu_temperature_max"] is not None else None
                )
            results.append(row)
        payload = {"bucket_seconds": bucket_sec, "results": results}
        cache.set(cache_key, payload, _BUCKET_CACHE_TTL)
        return Response(payload)


class StackMetricsFilter(filters.FilterSet):
    agent = filters.UUIDFilter(field_name="agent_id")
    stack = filters.CharFilter(field_name="stack")
    from_time = filters.IsoDateTimeFilter(field_name="recorded_at", lookup_expr="gte")
    to_time = filters.IsoDateTimeFilter(field_name="recorded_at", lookup_expr="lte")

    class Meta:
        model = ContainerMetricsHistory
        fields = ["agent", "stack", "from_time", "to_time"]


@extend_schema_view(
    list=extend_schema(
        summary="스택 메트릭 bucket 집계",
        description=(
            "라벨로 묶인 스택(hypercube.stack / docker compose project) 단위로 "
            "메트릭을 시계열 bucket 집계해 반환합니다. ContainerMetricsHistory.stack "
            "컬럼을 직접 GROUP BY 하므로 멀티서버 환경에서도 단일 SQL 한 번으로 끝납니다. "
            "stack 컬럼은 metrics 적재 시점에 라벨 기준으로 미리 결정돼 저장됩니다."
        ),
    ),
)
class StackMetricsViewSet(GenericViewSet):
    """`/api/metrics/stacks/buckets/` 만 노출. list/retrieve 미구현 (의미 없음)."""

    queryset = ContainerMetricsHistory.objects.all()
    filterset_class = StackMetricsFilter
    permission_classes = [IsViewer]

    def get_queryset(self):
        qs = super().get_queryset()

        range_key = self.request.query_params.get("range")
        if range_key and range_key in RANGE_SHORTHAND:
            qs = qs.filter(recorded_at__gte=timezone.now() - RANGE_SHORTHAND[range_key])

        user = self.request.user
        if getattr(user, "role", None) == "admin":
            return qs

        # Non-admin: limit to stacks containing at least one of the user's containers.
        owned_container_ids = Container.objects.filter(
            requester=user
        ).values_list("container_id", flat=True)
        return qs.filter(container_id__in=owned_container_ids)

    @action(detail=False, methods=["get"], url_path="buckets")
    def buckets(self, request):
        bucket_sec = _parse_bucket_seconds(request.query_params.get("bucket"), default=60)
        cache_key = _make_cache_key("stacks", request, bucket_sec)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = self.filter_queryset(self.get_queryset())
        bucket_expr = RawSQL(
            "(floor(extract(epoch from recorded_at) / %s) * %s)::bigint",
            (bucket_sec, bucket_sec),
            output_field=IntegerField(),
        )

        db_cols = _db_columns(ContainerMetricsHistory._meta.db_table)
        has_gpu_cols = "gpu_usage" in db_cols

        annotations = dict(
            cpu_avg=Avg("cpu_usage"),
            cpu_max=Max("cpu_usage"),
            memory_percent_avg=Avg("memory_percent"),
            memory_percent_max=Max("memory_percent"),
            memory_bytes_avg=Avg("memory_usage"),
            network_rx_max=Max("network_rx"),
            network_tx_max=Max("network_tx"),
            disk_read_max=Max("disk_read"),
            disk_write_max=Max("disk_write"),
            container_count=Count("container_id", distinct=True),
            sample_count=Count("id"),
        )
        if has_gpu_cols:
            annotations.update(
                gpu_usage_avg=Avg("gpu_usage"),
                gpu_usage_max=Max("gpu_usage"),
                gpu_memory_used_max=Max("gpu_memory_used"),
                gpu_memory_total_max=Max("gpu_memory_total"),
            )

        rows = (
            qs.annotate(bucket_epoch=bucket_expr)
            .values("agent_id", "stack", "bucket_epoch")
            .annotate(**annotations)
            .order_by("agent_id", "stack", "bucket_epoch")
        )

        results = []
        for r in rows:
            row = {
                "agent": str(r["agent_id"]),
                "stack": r["stack"],
                "bucket_epoch": int(r["bucket_epoch"]),
                "bucket_start": timezone.datetime.fromtimestamp(
                    int(r["bucket_epoch"]), tz=timezone.get_current_timezone()
                ).isoformat(),
                "cpu_avg": round(r["cpu_avg"] or 0, 2),
                "cpu_max": round(r["cpu_max"] or 0, 2),
                "memory_percent_avg": round(r["memory_percent_avg"] or 0, 2),
                "memory_percent_max": round(r["memory_percent_max"] or 0, 2),
                "memory_bytes_avg": int(r["memory_bytes_avg"] or 0),
                "network_rx_max": int(r["network_rx_max"] or 0),
                "network_tx_max": int(r["network_tx_max"] or 0),
                "disk_read_max": int(r["disk_read_max"] or 0),
                "disk_write_max": int(r["disk_write_max"] or 0),
                "container_count": int(r["container_count"] or 0),
                "sample_count": int(r["sample_count"] or 0),
            }
            if has_gpu_cols:
                row["gpu_usage_avg"] = (
                    round(r["gpu_usage_avg"], 2) if r.get("gpu_usage_avg") is not None else None
                )
                row["gpu_usage_max"] = (
                    round(r["gpu_usage_max"], 2) if r.get("gpu_usage_max") is not None else None
                )
                row["gpu_memory_used_max"] = (
                    int(r["gpu_memory_used_max"]) if r.get("gpu_memory_used_max") is not None else None
                )
                row["gpu_memory_total_max"] = (
                    int(r["gpu_memory_total_max"]) if r.get("gpu_memory_total_max") is not None else None
                )
            results.append(row)

        payload = {"bucket_seconds": bucket_sec, "results": results}
        cache.set(cache_key, payload, _BUCKET_CACHE_TTL)
        return Response(payload)


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
        cache_key = _make_cache_key("container", request, bucket_sec)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        qs = self.filter_queryset(self.get_queryset())
        bucket_expr = RawSQL(
            "(floor(extract(epoch from recorded_at) / %s) * %s)::bigint",
            (bucket_sec, bucket_sec),
            output_field=IntegerField(),
        )
        # New columns (cpu_usage_raw / cpu_cores_quota) only exist after the
        # 0002 migration runs. Inspect actual DB columns so this endpoint
        # stays functional on environments that have not migrated yet.
        db_cols = _db_columns(ContainerMetricsHistory._meta.db_table)
        has_raw_cols = {"cpu_usage_raw", "cpu_cores_quota"}.issubset(db_cols)

        has_gpu_cols = "gpu_usage" in db_cols
        annotations = dict(
            # cpu_usage 컬럼은 0-100 정규화 값(usage_pct)을 저장하도록 의미가 정해져 있음.
            # Agent v2: cpu.usage_pct → cpu_usage. 구버전: usage / cores 로 fallback 계산.
            cpu_usage_pct_avg=Avg("cpu_usage"),
            cpu_usage_pct_max=Max("cpu_usage"),
            memory_avg=Avg("memory_usage"),
            memory_max=Max("memory_usage"),
            memory_percent_avg=Avg("memory_percent"),
            network_rx_max=Max("network_rx"),
            network_tx_max=Max("network_tx"),
            disk_read_max=Max("disk_read"),
            disk_write_max=Max("disk_write"),
            sample_count=Count("id"),
        )
        if has_raw_cols:
            annotations.update(
                cpu_usage_avg=Avg("cpu_usage_raw"),  # raw (코어 합산) 평균
                cpu_usage_max=Max("cpu_usage_raw"),
                cpu_cores_quota_avg=Avg("cpu_cores_quota"),
            )
        if has_gpu_cols:
            annotations.update(
                gpu_usage_avg=Avg("gpu_usage"),
                gpu_usage_max=Max("gpu_usage"),
                gpu_memory_used_max=Max("gpu_memory_used"),
                gpu_memory_total_max=Max("gpu_memory_total"),
            )

        rows = (
            qs.annotate(bucket_epoch=bucket_expr)
            .values("agent_id", "container_id", "bucket_epoch")
            .annotate(**annotations)
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
                # 0-100 정규화 평균 — null 은 그대로 null 로 (모든 샘플의
                # usage_pct 가 null 이면 frontend 가 "—"로 그릴 수 있게)
                "cpu_usage_pct_avg": round(r["cpu_usage_pct_avg"], 2) if r.get("cpu_usage_pct_avg") is not None else None,
                "cpu_usage_pct_max": round(r["cpu_usage_pct_max"], 2) if r.get("cpu_usage_pct_max") is not None else None,
                # raw 코어 합산 % 평균 — 분석/디버깅용
                "cpu_usage_avg": round(r["cpu_usage_avg"], 2) if r.get("cpu_usage_avg") is not None else None,
                "cpu_usage_max": round(r["cpu_usage_max"], 2) if r.get("cpu_usage_max") is not None else None,
                "cpu_cores_quota_avg": round(r["cpu_cores_quota_avg"], 2) if r.get("cpu_cores_quota_avg") is not None else None,
                # 호환용: 기존 cpu_avg/cpu_max 필드명도 유지 (정규화 값과 동일)
                "cpu_avg": round(r["cpu_usage_pct_avg"] or 0, 2),
                "cpu_max": round(r["cpu_usage_pct_max"] or 0, 2),
                "memory_avg": float(r["memory_avg"] or 0),
                "memory_max": float(r["memory_max"] or 0),
                "memory_percent_avg": round(r["memory_percent_avg"] or 0, 2),
                "network_rx_max": int(r["network_rx_max"] or 0),
                "network_tx_max": int(r["network_tx_max"] or 0),
                "disk_read_max": int(r["disk_read_max"] or 0),
                "disk_write_max": int(r["disk_write_max"] or 0),
                "gpu_usage_avg": (
                    round(r["gpu_usage_avg"], 2)
                    if has_gpu_cols and r.get("gpu_usage_avg") is not None
                    else None
                ),
                "gpu_usage_max": (
                    round(r["gpu_usage_max"], 2)
                    if has_gpu_cols and r.get("gpu_usage_max") is not None
                    else None
                ),
                "gpu_memory_used_max": (
                    int(r["gpu_memory_used_max"])
                    if has_gpu_cols and r.get("gpu_memory_used_max") is not None
                    else None
                ),
                "gpu_memory_total_max": (
                    int(r["gpu_memory_total_max"])
                    if has_gpu_cols and r.get("gpu_memory_total_max") is not None
                    else None
                ),
                "sample_count": int(r["sample_count"] or 0),
            }
            for r in rows
        ]
        payload = {"bucket_seconds": bucket_sec, "results": results}
        cache.set(cache_key, payload, _BUCKET_CACHE_TTL)
        return Response(payload)
