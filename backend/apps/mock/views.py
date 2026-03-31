from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .generators import containers, server, system


class MockContainerListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] 컨테이너 목록", description="가짜 컨테이너 20+개 목록 반환", tags=["Mock - Containers"])
    def get(self, request):
        return Response(containers.get_container_list())


class MockContainerDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] 컨테이너 상세", description="inspect + stats 데이터 반환", tags=["Mock - Containers"])
    def get(self, request, pk):
        inspect = containers.get_container_inspect(pk)
        if not inspect:
            return Response({"detail": "Container not found"}, status=status.HTTP_404_NOT_FOUND)
        stats = containers.get_container_stats(pk)
        return Response({"inspect": inspect, "stats": stats})


class MockContainerMetricsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] 컨테이너 메트릭", description="CPU, memory, network, disk 메트릭 (동적 변동)", tags=["Mock - Containers"])
    def get(self, request, pk):
        metrics = containers.get_container_metrics(pk)
        if not metrics:
            return Response({"detail": "Container not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(metrics)


class MockContainerLogsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] 컨테이너 로그", description="이미지 타입별 현실적 로그 생성 (nginx, postgres, redis 등)", tags=["Mock - Containers"])
    def get(self, request, pk):
        tail = int(request.query_params.get("tail", 100))
        logs = containers.get_container_logs(pk, tail=tail)
        if logs is None:
            return Response({"detail": "Container not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"logs": logs, "containerId": pk})


class MockContainerControlView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] 컨테이너 제어", description="start/stop/restart/pause/unpause/kill/remove. in-memory state 변경.", tags=["Mock - Containers"])
    def post(self, request, pk):
        action = request.data.get("action")
        if not action:
            return Response({"detail": "action is required"}, status=status.HTTP_400_BAD_REQUEST)

        result = containers.perform_container_action(pk, action)
        if result is None:
            return Response({"detail": "Container not found"}, status=status.HTTP_404_NOT_FOUND)
        if "error" in result:
            return Response({"detail": result["error"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class MockSystemOverviewView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] 시스템 개요", description="hostname, OS, CPU, memory, disk, network, docker 정보", tags=["Mock - System"])
    def get(self, request):
        return Response(system.get_system_overview())


class MockCpuDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] CPU 상세", description="per-core usage, load average (동적 변동)", tags=["Mock - System"])
    def get(self, request):
        return Response(system.get_cpu_detail())


class MockNetworkDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] 네트워크 상세", description="interfaces, rx/tx stats, connections", tags=["Mock - System"])
    def get(self, request):
        return Response(system.get_network_detail())


class MockProcessesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] 프로세스 목록", description="CPU 기준 top 20 프로세스, total/running/sleeping/zombie", tags=["Mock - System"])
    def get(self, request):
        return Response(system.get_processes())


class MockLoginsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(summary="[Mock] 로그인 사용자", description="현재 로그인 사용자, uptime, lastBoot", tags=["Mock - System"])
    def get(self, request):
        return Response(system.get_logins())


class MockServerIpView(APIView):
    """Frontend에서 envelope 없이 raw JSON을 기대하는 엔드포인트"""

    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]

    @extend_schema(summary="[Mock] 서버 IP", description="서버 IP 주소. envelope ({success, data}) 미사용.", tags=["Mock - Server"])
    def get(self, request):
        return Response(server.get_server_ip())
