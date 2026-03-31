from django.urls import path

from . import views

urlpatterns = [
    # Container endpoints
    path("containers/", views.MockContainerListView.as_view(), name="mock-container-list"),
    path("containers/<str:pk>/", views.MockContainerDetailView.as_view(), name="mock-container-detail"),
    path("containers/<str:pk>/metrics/", views.MockContainerMetricsView.as_view(), name="mock-container-metrics"),
    path("containers/<str:pk>/logs/", views.MockContainerLogsView.as_view(), name="mock-container-logs"),
    path("containers/<str:pk>/control/", views.MockContainerControlView.as_view(), name="mock-container-control"),
    # System endpoints
    path("system/", views.MockSystemOverviewView.as_view(), name="mock-system-overview"),
    path("system/cpu/", views.MockCpuDetailView.as_view(), name="mock-cpu-detail"),
    path("system/network/", views.MockNetworkDetailView.as_view(), name="mock-network-detail"),
    path("system/processes/", views.MockProcessesView.as_view(), name="mock-processes"),
    path("system/logins/", views.MockLoginsView.as_view(), name="mock-logins"),
    # Server endpoint
    path("server/ip/", views.MockServerIpView.as_view(), name="mock-server-ip"),
]
