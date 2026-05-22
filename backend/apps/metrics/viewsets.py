from datetime import timedelta

import hashlib

from django.core.cache import cache
from django.db import connection
from django.db.models import (
    Avg,
    Count,
    DurationField,
    ExpressionWrapper,
    F,
    IntegerField,
    Max,
    Q,
)
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

from .models import (
    ContainerMetricsHistory,
    ContainerMetricsRollup,
    ResourceEvent,
    StackMetricsRollup,
    SystemMetricsHistory,
    SystemMetricsRollup,
)
from .serializers import (
    ContainerMetricsHistoryDetailSerializer,
    ContainerMetricsHistorySerializer,
    ResourceEventSerializer,
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


# 캐시 TTL: bucket 크기에 비례. 7d range (bucket=1w) 는 한번 41s 걸려 계산한 결과를
# 1시간 재사용 — 그 사이 bucket boundary 가 바뀔 일이 없음. 짧은 range 는 짧은 TTL.
_BUCKET_CACHE_TTL_BASE = 60
_BUCKET_CACHE_TTL_CAP = 3600


def _bucket_cache_ttl(bucket_sec: int) -> int:
    # bucket_sec / 10 로 자연스럽게 비례. 10s bucket → 60s, 1w bucket → cap(3600).
    return max(_BUCKET_CACHE_TTL_BASE, min(bucket_sec // 10, _BUCKET_CACHE_TTL_CAP))


def _floor_iso_to_bucket(value: str, bucket_sec: int) -> str:
    """from_time/to_time 을 bucket 경계로 floor → 캐시 키 안정화.
    Date.now() 기반 ISO string 이 매 호출마다 달라져 cache miss 가 나는 문제 회피.
    """
    if not value or bucket_sec <= 0:
        return value or ""
    try:
        dt = timezone.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return value
    epoch = int(dt.timestamp())
    floored = epoch - (epoch % bucket_sec)
    return str(floored)


def _make_cache_key(prefix: str, request, bucket_sec: int) -> str:
    params = sorted(request.query_params.items())
    user_id = getattr(request.user, "id", "anon")
    # from_time/to_time 은 bucket 경계로 정규화 — Date.now() 차이로 인한 무한 miss 회피.
    normalized = [
        (k, _floor_iso_to_bucket(v, bucket_sec) if k in {"from_time", "to_time"} else v)
        for k, v in params
    ]
    raw = f"{prefix}|{user_id}|{bucket_sec}|" + "&".join(f"{k}={v}" for k, v in normalized)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"metrics:buckets:{digest}"


# Rollup 테이블에 사전 적재해둔 bucket_seconds. 그 외 값은 raw GROUP BY 경로로.
_ROLLUP_BUCKETS = {3600, 86400}
# 7d range. daily rollup 위에서 7개씩 다시 묶음 (28일이라도 28 row 만 다룸).
_WEEKLY_BUCKET = 604800


def _parse_iso(value: str | None):
    if not value:
        return None
    try:
        return timezone.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


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

        # Long-range (1h/24h/7d) 는 사전 적재된 rollup 테이블에서 직접 조회.
        # 10M+ raw rows GROUP BY 대신 (agent × bucket_seconds) 인덱스 range scan.
        if bucket_sec in _ROLLUP_BUCKETS or bucket_sec == _WEEKLY_BUCKET:
            payload = _serve_system_from_rollup(request, bucket_sec)
            cache.set(cache_key, payload, _bucket_cache_ttl(bucket_sec))
            return Response(payload)

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
        cache.set(cache_key, payload, _bucket_cache_ttl(bucket_sec))
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

        if bucket_sec in _ROLLUP_BUCKETS or bucket_sec == _WEEKLY_BUCKET:
            payload = _serve_stacks_from_rollup(request, bucket_sec)
            cache.set(cache_key, payload, _bucket_cache_ttl(bucket_sec))
            return Response(payload)

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
                gpu_memory_used_avg=Avg("gpu_memory_used"),
                gpu_memory_used_max=Max("gpu_memory_used"),
                gpu_memory_total_avg=Avg("gpu_memory_total"),
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
                row["gpu_memory_used_avg"] = (
                    int(r["gpu_memory_used_avg"]) if r.get("gpu_memory_used_avg") is not None else None
                )
                row["gpu_memory_used_max"] = (
                    int(r["gpu_memory_used_max"]) if r.get("gpu_memory_used_max") is not None else None
                )
                row["gpu_memory_total_avg"] = (
                    int(r["gpu_memory_total_avg"]) if r.get("gpu_memory_total_avg") is not None else None
                )
                row["gpu_memory_total_max"] = (
                    int(r["gpu_memory_total_max"]) if r.get("gpu_memory_total_max") is not None else None
                )
            results.append(row)

        payload = {"bucket_seconds": bucket_sec, "results": results}
        cache.set(cache_key, payload, _bucket_cache_ttl(bucket_sec))
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

    # Cross-server 호출 시 row 수가 [agents × containers × bucket-window] 로 폭발하므로,
    # raw row list 는 단일 컨테이너 또는 단일 agent 범위 안에서만 허용. 그 외는
    # /api/metrics/containers/buckets/ 또는 /api/metrics/stacks/buckets/ 사용 권장.
    LIST_MAX_LIMIT = 500
    LIST_DEFAULT_LIMIT = 240

    def list(self, request, *args, **kwargs):
        from rest_framework.exceptions import ValidationError

        if not request.query_params.get("agent") and not request.query_params.get("container_id"):
            raise ValidationError({
                "detail": (
                    "agent 또는 container_id 필터가 필요합니다. cross-server 집계는 "
                    "/api/metrics/containers/buckets/ 또는 /api/metrics/stacks/buckets/ 를 사용하세요."
                ),
            })

        raw_limit = request.query_params.get("limit")
        try:
            n = int(raw_limit) if raw_limit is not None else self.LIST_DEFAULT_LIMIT
        except (TypeError, ValueError):
            n = self.LIST_DEFAULT_LIMIT
        n = max(1, min(n, self.LIST_MAX_LIMIT))

        qs = self.filter_queryset(self.get_queryset()).order_by("-recorded_at")[:n]
        rows = list(qs)[::-1]
        return Response(self.get_serializer(rows, many=True).data)

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

        if bucket_sec in _ROLLUP_BUCKETS or bucket_sec == _WEEKLY_BUCKET:
            payload = _serve_containers_from_rollup(request, bucket_sec)
            cache.set(cache_key, payload, _bucket_cache_ttl(bucket_sec))
            return Response(payload)

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
                gpu_memory_used_avg=Avg("gpu_memory_used"),
                gpu_memory_used_max=Max("gpu_memory_used"),
                gpu_memory_total_avg=Avg("gpu_memory_total"),
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
                "gpu_memory_used_avg": (
                    int(r["gpu_memory_used_avg"])
                    if has_gpu_cols and r.get("gpu_memory_used_avg") is not None
                    else None
                ),
                "gpu_memory_used_max": (
                    int(r["gpu_memory_used_max"])
                    if has_gpu_cols and r.get("gpu_memory_used_max") is not None
                    else None
                ),
                "gpu_memory_total_avg": (
                    int(r["gpu_memory_total_avg"])
                    if has_gpu_cols and r.get("gpu_memory_total_avg") is not None
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
        cache.set(cache_key, payload, _bucket_cache_ttl(bucket_sec))
        return Response(payload)


# ----------------------------------------------------------------------
# Rollup-based serving — long-range (1h/24h/7d) 차트의 직접 소스.
# raw GROUP BY 와 응답 shape 100% 동일하게 유지 (frontend 변경 0).
# 7d (604800) 는 daily(86400) rollup 위에서 다시 weekly group by — 28 rows.
# ----------------------------------------------------------------------


def _rollup_window(request, bucket_sec: int):
    """from_time/to_time 을 bucket 경계로 정규화해 (start, end) datetime 반환.
    범위 없으면 default = 마지막 N개 bucket (N=10).
    """
    to_dt = _parse_iso(request.query_params.get("to_time")) or timezone.now()
    from_dt = _parse_iso(request.query_params.get("from_time"))
    if from_dt is None:
        from_dt = to_dt - timedelta(seconds=bucket_sec * 10)
    return from_dt, to_dt


def _agent_id_filter(request) -> str | None:
    return request.query_params.get("agent")


def _serve_system_from_rollup(request, bucket_sec: int) -> dict:
    storage_bucket = _storage_bucket_for(bucket_sec)
    from_dt, to_dt = _rollup_window(request, bucket_sec)
    qs = SystemMetricsRollup.objects.filter(
        bucket_seconds=storage_bucket,
        bucket_start__gte=from_dt,
        bucket_start__lte=to_dt,
    )
    agent_id = _agent_id_filter(request)
    if agent_id:
        qs = qs.filter(agent_id=agent_id)
    # 권한 — admin 외엔 자기 container 가 있는 agent 만.
    user = request.user
    if getattr(user, "role", None) != "admin":
        owned_agent_ids = list(
            Container.objects.filter(requester=user).values_list("agent_id", flat=True).distinct()
        )
        qs = qs.filter(agent_id__in=owned_agent_ids)

    rows = list(qs.order_by("agent_id", "bucket_start"))
    if bucket_sec == _WEEKLY_BUCKET:
        rows = _regroup_to_weekly_system(rows, from_dt)

    results = []
    for r in rows:
        bucket_epoch = int(r.bucket_start.timestamp())
        results.append({
            "agent": str(r.agent_id),
            "bucket_epoch": bucket_epoch,
            "bucket_start": r.bucket_start.isoformat(),
            "cpu_avg": round(r.cpu_avg or 0, 2),
            "cpu_max": round(r.cpu_max or 0, 2),
            "memory_avg": round(r.memory_usage_avg or 0, 2),
            "memory_max": round(r.memory_usage_max or 0, 2),
            "memory_used_avg": 0,
            "memory_total_avg": 0,
            "disk_avg": round(r.disk_usage_avg or 0, 2),
            "disk_max": round(r.disk_usage_max or 0, 2),
            "network_rx_max": int(r.network_rx_max or 0),
            "network_tx_max": int(r.network_tx_max or 0),
            "sample_count": int(r.sample_count or 0),
            "gpu_avg": round(r.gpu_usage_avg, 2) if r.gpu_usage_avg is not None else None,
            "gpu_max": round(r.gpu_usage_max, 2) if r.gpu_usage_max is not None else None,
            "gpu_memory_used_avg": int(r.gpu_memory_used_avg) if r.gpu_memory_used_avg is not None else None,
            "gpu_memory_total_avg": int(r.gpu_memory_total_avg) if r.gpu_memory_total_avg is not None else None,
        })
    return {"bucket_seconds": bucket_sec, "results": results}


def _serve_stacks_from_rollup(request, bucket_sec: int) -> dict:
    storage_bucket = _storage_bucket_for(bucket_sec)
    from_dt, to_dt = _rollup_window(request, bucket_sec)
    qs = StackMetricsRollup.objects.filter(
        bucket_seconds=storage_bucket,
        bucket_start__gte=from_dt,
        bucket_start__lte=to_dt,
    )
    agent_id = _agent_id_filter(request)
    if agent_id:
        qs = qs.filter(agent_id=agent_id)
    stack = request.query_params.get("stack")
    if stack:
        qs = qs.filter(stack=stack)
    user = request.user
    if getattr(user, "role", None) != "admin":
        owned_agent_ids = list(
            Container.objects.filter(requester=user).values_list("agent_id", flat=True).distinct()
        )
        qs = qs.filter(agent_id__in=owned_agent_ids)

    rows = list(qs.order_by("agent_id", "stack", "bucket_start"))
    if bucket_sec == _WEEKLY_BUCKET:
        rows = _regroup_to_weekly_stack(rows, from_dt)

    results = []
    for r in rows:
        bucket_epoch = int(r.bucket_start.timestamp())
        results.append({
            "agent": str(r.agent_id),
            "stack": r.stack,
            "bucket_epoch": bucket_epoch,
            "bucket_start": r.bucket_start.isoformat(),
            "cpu_avg": round(r.cpu_avg or 0, 2),
            "cpu_max": round(r.cpu_max or 0, 2),
            "memory_percent_avg": round(r.memory_percent_avg or 0, 2),
            "memory_percent_max": round(r.memory_percent_max or 0, 2),
            "memory_bytes_avg": int(r.memory_bytes_avg or 0),
            "network_rx_max": int(r.network_rx_max or 0),
            "network_tx_max": int(r.network_tx_max or 0),
            "disk_read_max": int(r.disk_read_max or 0),
            "disk_write_max": int(r.disk_write_max or 0),
            "container_count": int(r.container_count or 0),
            "sample_count": int(r.sample_count or 0),
            "gpu_usage_avg": round(r.gpu_usage_avg, 2) if r.gpu_usage_avg is not None else None,
            "gpu_usage_max": round(r.gpu_usage_max, 2) if r.gpu_usage_max is not None else None,
            "gpu_memory_used_avg": int(r.gpu_memory_used_avg) if r.gpu_memory_used_avg is not None else None,
            "gpu_memory_used_max": int(r.gpu_memory_used_max) if r.gpu_memory_used_max is not None else None,
            "gpu_memory_total_avg": int(r.gpu_memory_total_avg) if r.gpu_memory_total_avg is not None else None,
        })
    return {"bucket_seconds": bucket_sec, "results": results}


def _serve_containers_from_rollup(request, bucket_sec: int) -> dict:
    storage_bucket = _storage_bucket_for(bucket_sec)
    from_dt, to_dt = _rollup_window(request, bucket_sec)
    qs = ContainerMetricsRollup.objects.filter(
        bucket_seconds=storage_bucket,
        bucket_start__gte=from_dt,
        bucket_start__lte=to_dt,
    )
    agent_id = _agent_id_filter(request)
    if agent_id:
        qs = qs.filter(agent_id=agent_id)
    container_id = request.query_params.get("container_id")
    if container_id:
        qs = qs.filter(container_id=container_id)
    user = request.user
    if getattr(user, "role", None) != "admin":
        owned_container_ids = list(
            Container.objects.filter(requester=user).values_list("container_id", flat=True)
        )
        qs = qs.filter(container_id__in=owned_container_ids)

    rows = list(qs.order_by("agent_id", "container_id", "bucket_start"))
    if bucket_sec == _WEEKLY_BUCKET:
        rows = _regroup_to_weekly_container(rows, from_dt)

    results = []
    for r in rows:
        bucket_epoch = int(r.bucket_start.timestamp())
        cpu_pct_avg = r.cpu_usage_pct_avg
        cpu_pct_max = r.cpu_usage_pct_max
        results.append({
            "agent": str(r.agent_id),
            "container_id": r.container_id,
            "bucket_epoch": bucket_epoch,
            "bucket_start": r.bucket_start.isoformat(),
            "cpu_usage_pct_avg": round(cpu_pct_avg, 2) if cpu_pct_avg is not None else None,
            "cpu_usage_pct_max": round(cpu_pct_max, 2) if cpu_pct_max is not None else None,
            "cpu_usage_avg": round(r.cpu_usage_raw_avg, 2) if r.cpu_usage_raw_avg is not None else None,
            "cpu_usage_max": round(r.cpu_usage_raw_max, 2) if r.cpu_usage_raw_max is not None else None,
            "cpu_cores_quota_avg": round(r.cpu_cores_quota_avg, 2) if r.cpu_cores_quota_avg is not None else None,
            "cpu_avg": round(cpu_pct_avg or 0, 2),
            "cpu_max": round(cpu_pct_max or 0, 2),
            "memory_avg": float(r.memory_avg or 0),
            "memory_max": float(r.memory_max or 0),
            "memory_percent_avg": round(r.memory_percent_avg or 0, 2),
            "network_rx_max": int(r.network_rx_max or 0),
            "network_tx_max": int(r.network_tx_max or 0),
            "disk_read_max": int(r.disk_read_max or 0),
            "disk_write_max": int(r.disk_write_max or 0),
            "gpu_usage_avg": round(r.gpu_usage_avg, 2) if r.gpu_usage_avg is not None else None,
            "gpu_usage_max": round(r.gpu_usage_max, 2) if r.gpu_usage_max is not None else None,
            "gpu_memory_used_avg": int(r.gpu_memory_used_avg) if r.gpu_memory_used_avg is not None else None,
            "gpu_memory_used_max": int(r.gpu_memory_used_max) if r.gpu_memory_used_max is not None else None,
            "gpu_memory_total_avg": int(r.gpu_memory_total_avg) if r.gpu_memory_total_avg is not None else None,
            "gpu_memory_total_max": None,
            "sample_count": int(r.sample_count or 0),
        })
    return {"bucket_seconds": bucket_sec, "results": results}


# resolved 로 종료된 이벤트 중 이보다 짧게 지속한 단발은 history 에서 숨김.
MIN_RESOLVED_DURATION = timedelta(minutes=2)


@extend_schema_view(
    list=extend_schema(
        summary="자원 이벤트 history 조회",
        description=(
            "서버 자원 임계 초과/급증 이벤트의 이력. 종료된 이벤트 포함 전체. "
            "?agent, ?metric, ?from_time/to_time, ?active=true/false, ?limit 으로 필터. "
            "resolved 로 2분 미만 지속한 단발 노이즈는 자동 제외."
        ),
    ),
)
class ResourceEventViewSet(ListModelMixin, GenericViewSet):
    """서버 자원 이벤트 — 실시간 카드(active)와 history 의 단일 출처.

    (agent, metric) 단위 라이프사이클: 초과 시작 시 생성, 지속 중 갱신,
    자원 정상화 시 자동 종료(resolved), 관리자 확인 시 수동 종료(acknowledged).
    """

    queryset = ResourceEvent.objects.select_related("agent").all()
    permission_classes = [IsViewer]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, "role", None) == "admin":
            return qs
        owned_agent_ids = Container.objects.filter(
            requester=user
        ).values_list("agent_id", flat=True)
        return qs.filter(agent_id__in=owned_agent_ids)

    def _apply_filters(self, qs):
        params = self.request.query_params
        agent_id = params.get("agent")
        if agent_id:
            qs = qs.filter(agent_id=agent_id)
        metric = params.get("metric")
        if metric:
            qs = qs.filter(metric=metric)
        from_dt = _parse_iso(params.get("from_time"))
        if from_dt:
            qs = qs.filter(started_at__gte=from_dt)
        to_dt = _parse_iso(params.get("to_time"))
        if to_dt:
            qs = qs.filter(started_at__lte=to_dt)
        return qs

    def list(self, request, *args, **kwargs):
        """history — 종료 포함 전체. 최소 지속시간 필터 적용."""
        qs = self._apply_filters(self.get_queryset())
        # resolved 로 종료됐고 2분 미만 지속한 단발 노이즈는 history 에서 숨김.
        # active(ended_at=null)는 duration 이 null 이라 exclude 에 안 걸려 유지된다.
        qs = qs.annotate(
            duration=ExpressionWrapper(
                F("ended_at") - F("started_at"), output_field=DurationField()
            )
        ).exclude(
            Q(ended_reason=ResourceEvent.EndedReason.RESOLVED)
            & Q(duration__lt=MIN_RESOLVED_DURATION)
        )
        active_param = request.query_params.get("active")
        if active_param == "true":
            qs = qs.filter(ended_at__isnull=True)
        elif active_param == "false":
            qs = qs.filter(ended_at__isnull=False)
        try:
            limit = max(1, min(int(request.query_params.get("limit", 100)), 500))
        except (TypeError, ValueError):
            limit = 100
        rows = list(qs.order_by("-started_at")[:limit])
        return Response(ResourceEventSerializer(rows, many=True).data)

    @extend_schema(summary="진행 중 자원 이벤트 (카드용)")
    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        """실시간 카드용 — 진행 중 이벤트, agent 당 가장 심각한 1건."""
        sev_rank = {"critical": 1, "warning": 0}
        by_agent: dict = {}
        for ev in self.get_queryset().filter(ended_at__isnull=True):
            current = by_agent.get(ev.agent_id)
            if current is None or (
                sev_rank.get(ev.severity, 0), ev.last_value
            ) > (sev_rank.get(current.severity, 0), current.last_value):
                by_agent[ev.agent_id] = ev
        events = sorted(
            by_agent.values(),
            key=lambda e: (sev_rank.get(e.severity, 0), e.last_value),
            reverse=True,
        )
        return Response(ResourceEventSerializer(events, many=True).data)

    @extend_schema(summary="자원 이벤트 확인 처리 (수동 종료)")
    @action(detail=True, methods=["post"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        """진행 중 이벤트를 관리자가 확인 → 즉시 수동 종료."""
        event = self.get_object()
        if event.ended_at is None:
            event.ended_at = timezone.now()
            event.ended_reason = ResourceEvent.EndedReason.ACKNOWLEDGED
            event.acknowledged_by = request.user
            event.save(
                update_fields=[
                    "ended_at", "ended_reason", "acknowledged_by", "updated_at",
                ]
            )
        return Response(ResourceEventSerializer(event).data)


def _storage_bucket_for(bucket_sec: int) -> int:
    # 7d range 는 daily rollup 에서 다시 묶음.
    if bucket_sec == _WEEKLY_BUCKET:
        return 86400
    return bucket_sec


def _week_start_epoch(dt) -> int:
    epoch = int(dt.timestamp())
    return epoch - (epoch % _WEEKLY_BUCKET)


def _epoch_to_utc(epoch_sec: int):
    from datetime import datetime as _dt, timezone as _tz
    return _dt.fromtimestamp(int(epoch_sec), tz=_tz.utc)


def _regroup_to_weekly_system(rows, from_dt):
    """daily SystemMetricsRollup 리스트를 weekly 로 합침."""
    from collections import defaultdict
    bucket_map: dict[tuple, dict] = defaultdict(lambda: {"cpu_avgs": [], "cpu_maxs": [], "mem_avgs": [], "mem_maxs": [], "disk_avgs": [], "disk_maxs": [], "rx_maxs": [], "tx_maxs": [], "gpu_avgs": [], "gpu_maxs": [], "gpu_mu_avgs": [], "gpu_mt_avgs": [], "sample_count": 0, "agent_id": None})
    for r in rows:
        wk = _week_start_epoch(r.bucket_start)
        key = (r.agent_id, wk)
        b = bucket_map[key]
        b["agent_id"] = r.agent_id
        if r.cpu_avg is not None: b["cpu_avgs"].append(r.cpu_avg)
        if r.cpu_max is not None: b["cpu_maxs"].append(r.cpu_max)
        if r.memory_usage_avg is not None: b["mem_avgs"].append(r.memory_usage_avg)
        if r.memory_usage_max is not None: b["mem_maxs"].append(r.memory_usage_max)
        if r.disk_usage_avg is not None: b["disk_avgs"].append(r.disk_usage_avg)
        if r.disk_usage_max is not None: b["disk_maxs"].append(r.disk_usage_max)
        if r.network_rx_max is not None: b["rx_maxs"].append(r.network_rx_max)
        if r.network_tx_max is not None: b["tx_maxs"].append(r.network_tx_max)
        if r.gpu_usage_avg is not None: b["gpu_avgs"].append(r.gpu_usage_avg)
        if r.gpu_usage_max is not None: b["gpu_maxs"].append(r.gpu_usage_max)
        if r.gpu_memory_used_avg is not None: b["gpu_mu_avgs"].append(r.gpu_memory_used_avg)
        if r.gpu_memory_total_avg is not None: b["gpu_mt_avgs"].append(r.gpu_memory_total_avg)
        b["sample_count"] += int(r.sample_count or 0)
    avg = lambda xs: (sum(xs) / len(xs)) if xs else None
    mx = lambda xs: max(xs) if xs else None
    out = []
    for (agent_id, wk), b in sorted(bucket_map.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        out.append(SystemMetricsRollup(
            agent_id=agent_id,
            bucket_seconds=_WEEKLY_BUCKET,
            bucket_start=_epoch_to_utc(wk),
            cpu_avg=avg(b["cpu_avgs"]), cpu_max=mx(b["cpu_maxs"]),
            memory_usage_avg=avg(b["mem_avgs"]), memory_usage_max=mx(b["mem_maxs"]),
            disk_usage_avg=avg(b["disk_avgs"]), disk_usage_max=mx(b["disk_maxs"]),
            network_rx_max=mx(b["rx_maxs"]), network_tx_max=mx(b["tx_maxs"]),
            gpu_usage_avg=avg(b["gpu_avgs"]), gpu_usage_max=mx(b["gpu_maxs"]),
            gpu_memory_used_avg=int(avg(b["gpu_mu_avgs"])) if b["gpu_mu_avgs"] else None,
            gpu_memory_total_avg=int(avg(b["gpu_mt_avgs"])) if b["gpu_mt_avgs"] else None,
            sample_count=b["sample_count"],
        ))
    return out


def _regroup_to_weekly_stack(rows, from_dt):
    from collections import defaultdict
    bucket_map: dict[tuple, dict] = defaultdict(lambda: {"cpu_avgs": [], "cpu_maxs": [], "mp_avgs": [], "mp_maxs": [], "mb_avgs": [], "rx": [], "tx": [], "dr": [], "dw": [], "gpu_avgs": [], "gpu_maxs": [], "gpu_mu_avgs": [], "gpu_mu_maxs": [], "gpu_mt_avgs": [], "container_count_max": 0, "sample_count": 0, "agent_id": None, "stack": ""})
    for r in rows:
        wk = _week_start_epoch(r.bucket_start)
        key = (r.agent_id, r.stack, wk)
        b = bucket_map[key]
        b["agent_id"] = r.agent_id
        b["stack"] = r.stack
        if r.cpu_avg is not None: b["cpu_avgs"].append(r.cpu_avg)
        if r.cpu_max is not None: b["cpu_maxs"].append(r.cpu_max)
        if r.memory_percent_avg is not None: b["mp_avgs"].append(r.memory_percent_avg)
        if r.memory_percent_max is not None: b["mp_maxs"].append(r.memory_percent_max)
        if r.memory_bytes_avg is not None: b["mb_avgs"].append(r.memory_bytes_avg)
        if r.network_rx_max is not None: b["rx"].append(r.network_rx_max)
        if r.network_tx_max is not None: b["tx"].append(r.network_tx_max)
        if r.disk_read_max is not None: b["dr"].append(r.disk_read_max)
        if r.disk_write_max is not None: b["dw"].append(r.disk_write_max)
        if r.gpu_usage_avg is not None: b["gpu_avgs"].append(r.gpu_usage_avg)
        if r.gpu_usage_max is not None: b["gpu_maxs"].append(r.gpu_usage_max)
        if r.gpu_memory_used_avg is not None: b["gpu_mu_avgs"].append(r.gpu_memory_used_avg)
        if r.gpu_memory_used_max is not None: b["gpu_mu_maxs"].append(r.gpu_memory_used_max)
        if r.gpu_memory_total_avg is not None: b["gpu_mt_avgs"].append(r.gpu_memory_total_avg)
        b["container_count_max"] = max(b["container_count_max"], int(r.container_count or 0))
        b["sample_count"] += int(r.sample_count or 0)
    avg = lambda xs: (sum(xs) / len(xs)) if xs else None
    mx = lambda xs: max(xs) if xs else None
    out = []
    for (agent_id, stack, wk), b in sorted(bucket_map.items(), key=lambda kv: (str(kv[0][0]), kv[0][1], kv[0][2])):
        out.append(StackMetricsRollup(
            agent_id=agent_id, stack=stack,
            bucket_seconds=_WEEKLY_BUCKET,
            bucket_start=_epoch_to_utc(wk),
            cpu_avg=avg(b["cpu_avgs"]), cpu_max=mx(b["cpu_maxs"]),
            memory_percent_avg=avg(b["mp_avgs"]), memory_percent_max=mx(b["mp_maxs"]),
            memory_bytes_avg=int(avg(b["mb_avgs"])) if b["mb_avgs"] else None,
            network_rx_max=mx(b["rx"]), network_tx_max=mx(b["tx"]),
            disk_read_max=mx(b["dr"]), disk_write_max=mx(b["dw"]),
            gpu_usage_avg=avg(b["gpu_avgs"]), gpu_usage_max=mx(b["gpu_maxs"]),
            gpu_memory_used_avg=int(avg(b["gpu_mu_avgs"])) if b["gpu_mu_avgs"] else None,
            gpu_memory_used_max=mx(b["gpu_mu_maxs"]),
            gpu_memory_total_avg=int(avg(b["gpu_mt_avgs"])) if b["gpu_mt_avgs"] else None,
            container_count=b["container_count_max"],
            sample_count=b["sample_count"],
        ))
    return out


def _regroup_to_weekly_container(rows, from_dt):
    from collections import defaultdict
    bucket_map: dict[tuple, dict] = defaultdict(lambda: {"cp_avgs": [], "cp_maxs": [], "cr_avgs": [], "cr_maxs": [], "cq_avgs": [], "m_avgs": [], "m_maxs": [], "mp_avgs": [], "rx": [], "tx": [], "dr": [], "dw": [], "gpu_avgs": [], "gpu_maxs": [], "gpu_mu_avgs": [], "gpu_mu_maxs": [], "gpu_mt_avgs": [], "sample_count": 0, "agent_id": None, "container_id": "", "stack": ""})
    for r in rows:
        wk = _week_start_epoch(r.bucket_start)
        key = (r.agent_id, r.container_id, wk)
        b = bucket_map[key]
        b["agent_id"] = r.agent_id
        b["container_id"] = r.container_id
        b["stack"] = r.stack
        if r.cpu_usage_pct_avg is not None: b["cp_avgs"].append(r.cpu_usage_pct_avg)
        if r.cpu_usage_pct_max is not None: b["cp_maxs"].append(r.cpu_usage_pct_max)
        if r.cpu_usage_raw_avg is not None: b["cr_avgs"].append(r.cpu_usage_raw_avg)
        if r.cpu_usage_raw_max is not None: b["cr_maxs"].append(r.cpu_usage_raw_max)
        if r.cpu_cores_quota_avg is not None: b["cq_avgs"].append(r.cpu_cores_quota_avg)
        if r.memory_avg is not None: b["m_avgs"].append(r.memory_avg)
        if r.memory_max is not None: b["m_maxs"].append(r.memory_max)
        if r.memory_percent_avg is not None: b["mp_avgs"].append(r.memory_percent_avg)
        if r.network_rx_max is not None: b["rx"].append(r.network_rx_max)
        if r.network_tx_max is not None: b["tx"].append(r.network_tx_max)
        if r.disk_read_max is not None: b["dr"].append(r.disk_read_max)
        if r.disk_write_max is not None: b["dw"].append(r.disk_write_max)
        if r.gpu_usage_avg is not None: b["gpu_avgs"].append(r.gpu_usage_avg)
        if r.gpu_usage_max is not None: b["gpu_maxs"].append(r.gpu_usage_max)
        if r.gpu_memory_used_avg is not None: b["gpu_mu_avgs"].append(r.gpu_memory_used_avg)
        if r.gpu_memory_used_max is not None: b["gpu_mu_maxs"].append(r.gpu_memory_used_max)
        if r.gpu_memory_total_avg is not None: b["gpu_mt_avgs"].append(r.gpu_memory_total_avg)
        b["sample_count"] += int(r.sample_count or 0)
    avg = lambda xs: (sum(xs) / len(xs)) if xs else None
    mx = lambda xs: max(xs) if xs else None
    out = []
    for (agent_id, container_id, wk), b in sorted(bucket_map.items(), key=lambda kv: (str(kv[0][0]), kv[0][1], kv[0][2])):
        out.append(ContainerMetricsRollup(
            agent_id=agent_id, container_id=container_id, stack=b["stack"],
            bucket_seconds=_WEEKLY_BUCKET,
            bucket_start=_epoch_to_utc(wk),
            cpu_usage_pct_avg=avg(b["cp_avgs"]), cpu_usage_pct_max=mx(b["cp_maxs"]),
            cpu_usage_raw_avg=avg(b["cr_avgs"]), cpu_usage_raw_max=mx(b["cr_maxs"]),
            cpu_cores_quota_avg=avg(b["cq_avgs"]),
            memory_avg=avg(b["m_avgs"]), memory_max=mx(b["m_maxs"]),
            memory_percent_avg=avg(b["mp_avgs"]),
            network_rx_max=mx(b["rx"]), network_tx_max=mx(b["tx"]),
            disk_read_max=mx(b["dr"]), disk_write_max=mx(b["dw"]),
            gpu_usage_avg=avg(b["gpu_avgs"]), gpu_usage_max=mx(b["gpu_maxs"]),
            gpu_memory_used_avg=int(avg(b["gpu_mu_avgs"])) if b["gpu_mu_avgs"] else None,
            gpu_memory_used_max=mx(b["gpu_mu_maxs"]),
            gpu_memory_total_avg=int(avg(b["gpu_mt_avgs"])) if b["gpu_mt_avgs"] else None,
            sample_count=b["sample_count"],
        ))
    return out
