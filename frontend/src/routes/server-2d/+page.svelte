<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import {
		systemStore,
		containersStore,
		containerMetricsStore,
		wsConnected,
		connect,
		disconnect,
	} from '$lib/stores/ws-store';
	import {
		connectGlobal,
		disconnectGlobal,
		seedActiveAgents,
		seedStatusEventsFromBackend,
		statusEvents,
	} from '$lib/stores/global-events';
	import AdminHeader from '$lib/components/AdminHeader.svelte';
	import ContainerDetailModal from '$lib/components/ContainerDetailModal.svelte';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import TimeRangeSelector from '$lib/components/fleet/TimeRangeSelector.svelte';
	import FleetLineChart from '$lib/components/fleet/FleetLineChart.svelte';
	import ResourceGaugeBar from '$lib/components/server2d/ResourceGaugeBar.svelte';
	import KpiTileRow from '$lib/components/server2d/KpiTileRow.svelte';
	import HotContainersList from '$lib/components/server2d/HotContainersList.svelte';
	import StackSidebar from '$lib/components/server2d/StackSidebar.svelte';
	import LoadingOverlay from '$lib/components/LoadingOverlay.svelte';
	import ContainersGridPanel from '$lib/components/server2d/ContainersGridPanel.svelte';
	import StackLegendChips from '$lib/components/server2d/StackLegendChips.svelte';
	import HealthRadialGauge from '$lib/components/server2d/HealthRadialGauge.svelte';
	import PowerTempGauge from '$lib/components/server2d/PowerTempGauge.svelte';
	import EventLogStrip from '$lib/components/server2d/EventLogStrip.svelte';
	import { view, resetViewForServerChange } from '$lib/stores/server2d-view.svelte';
	import { resolveGroup, groupContainersByStack } from '$lib/utils/container-grouping';
	import {
		MONITORING_RANGE_CONFIG,
		buildRangeBuckets,
		bucketEpoch,
		clampPercent,
		formatRangeTick,
		type MonitoringRange,
	} from '$lib/utils/monitoring-range';
	import logoHypercube from '$lib/assets/logo_hypercube.png';

	type Agent = { id: string; hostname: string; ip_address: string; container_count?: number; is_active?: boolean };
	type DemoState = { systemInfo: any; containers: any[]; metrics: Map<string, any> };
	type SystemHistoryRow = {
		recorded_at: string;
		cpu_usage: number;
		memory_usage: number;
		disk_usage: number;
		network_rx: number;
		network_tx: number;
		processes_total?: number | null;
		processes_running?: number | null;
		logins_total?: number | null;
		gpu?: any[];
	};
	type ContainerHistoryRow = {
		recorded_at: string;
		container_id: string;
		cpu_usage: number;
		memory_usage: number;
		memory_limit: number;
		memory_percent: number;
		network_rx: number;
		network_tx: number;
		disk_read: number;
		disk_write: number;
		gpu_usage?: number | null;
		gpu_memory_used?: number | null;
		gpu_memory_total?: number | null;
		gpu_source?: string | null;
	};
	type Row = {
		container: any;
		id: string;
		name: string;
		stack: string;
		state: string;
		image: string;
		status: string;
		cpu: number;
		memory: number;
		network: number;
		gpu: number | null;
		gpuMemoryUsed: number | null;
		gpuMemoryTotal: number | null;
		gpuSource: string | null;
	};
	type ContainerTrend = {
		cpu: number[];
		memory: number[];
		network: number[];
		gpu: number[];
		cpuAvg: number;
		memoryAvg: number;
		networkAvg: number;
		gpuAvg: number | null;
		samples: number;
	};
	type StackTrend = {
		cpu: number[];
		memory: number[];
		network: number[];
		disk: number[];
		gpu: number[];
		gpuMeasured: boolean;
		count: number;
		running: number;
	};
	type HistoryModel = {
		containerMap: Map<string, ContainerTrend>;
		stackMap: Map<string, StackTrend>;
		buckets: number[];
	};

	const stackColors = ['#30d5c8', '#60a5fa', '#a78bfa', '#fbbf24', '#fb7185', '#34d399', '#f97316', '#38bdf8', '#c084fc', '#eab308'];
	const DEMO_SERVER_ID = '__demo_dense__';
	const DEMO_STACKS = [
		'gateway', 'api', 'worker', 'database', 'cache', 'observability',
		'queue', 'ai-pipeline', 'auth', 'billing', 'search', 'storage',
		'notifications', 'analytics', 'cdn', 'scheduler', 'logging', 'tracing',
		'ml-train', 'media-encode',
	];
	const DEMO_IMAGES = ['nginx:1.25', 'node:20-alpine', 'python:3.12', 'postgres:16', 'redis:7', 'prometheus:latest', 'rabbitmq:3', 'cuda-worker:12', 'go:1.22', 'elasticsearch:8'];
	const DEMO_STATES = ['running', 'running', 'running', 'running', 'running', 'running', 'paused', 'restarting', 'exited'];
	const DEMO_CONTAINER_COUNT = 280;
	const DEMO_AGENT: Agent = {
		id: DEMO_SERVER_ID,
		hostname: 'DEMO-DENSE-SERVER',
		ip_address: 'demo.local',
		container_count: DEMO_CONTAINER_COUNT,
	};
	const DEMO_TEMPLATES = Array.from({ length: DEMO_CONTAINER_COUNT }, (_, index) => {
		const stack = DEMO_STACKS[index % DEMO_STACKS.length];
		return {
			id: `demo-${index.toString().padStart(3, '0')}-${stack}`,
			shortId: `demo${index.toString().padStart(4, '0')}`,
			names: [`/${stack}-${index + 1}`],
			image: DEMO_IMAGES[index % DEMO_IMAGES.length],
			labels: {
				'hypercube.stack': stack,
				'com.docker.compose.project': stack,
			},
			networks: [`${stack}_net`, index % 4 === 0 ? 'shared_ingress' : 'backend_net'].filter(Boolean),
			mounts: [
				{ name: `${stack}_data`, type: 'volume' },
				index % 5 === 0 ? { name: 'shared_config', type: 'volume' } : null,
			].filter(Boolean) as { name: string; type: string }[],
		};
	});

	let accessToken = $state('');
	let isLoggedIn = $state(false);
	let redirecting = $state(false);
	let currentUsername = $state('');
	let loginUsername = $state('');
	let loginPassword = $state('');
	let loginError = $state('');
	let agents = $state<Agent[]>([]);
	let agentsLoading = $state(false);
	let selectedServerId = $state('');
	let selectedContainer = $state<any | null>(null);
	let selectedRange = $state<MonitoringRange>('5m');
	let lastLiveUpdate = $state<Date | null>(null);
	let historyPolledAt = $state<Date | null>(null);
	let historyLoading = $state(false);
	let historyError = $state('');
	let systemHistoryRows = $state<SystemHistoryRow[]>([]);
	let containerHistoryRows = $state<ContainerHistoryRow[]>([]);
	let stackHistoryRows = $state<StackBucket[]>([]);
	let demoState = $state<DemoState>(buildDemoState(Date.now()));
	let demoTimer: ReturnType<typeof setInterval> | null = null;
	let historyTimer: ReturnType<typeof setInterval> | null = null;
	let historyLoadSeq = 0;

	let isDemoServer = $derived(selectedServerId === DEMO_SERVER_ID);
	let rangeConfig = $derived(MONITORING_RANGE_CONFIG[selectedRange]);
	let systemInfo = $derived(isDemoServer ? demoState.systemInfo : $systemStore);
	let containers = $derived(isDemoServer ? demoState.containers : $containersStore);
	let containerMetrics = $derived(isDemoServer ? demoState.metrics : $containerMetricsStore);
	let selectedAgent = $derived(agents.find((agent) => agent.id === selectedServerId) ?? null);
	// 첫 메트릭 프레임 도착 전엔 차트가 모두 0/디폴트로 깜빡거림 → 데이터 도달 후 dashboard 렌더
	let dataReady = $derived(Boolean(systemInfo) && (isDemoServer || $wsConnected));

	let rows = $derived<Row[]>(
		containers.map((container: any) => {
			const metric = metricFor(container);
			return {
				container,
				id: container.id,
				name: displayName(container),
				stack: resolveGroup(container).name,
				state: container.state,
				image: container.image ?? '',
				status: container.status ?? '',
				cpu: metricCpu(metric),
				memory: metricMemory(metric),
				network: metricNetwork(metric),
				gpu: metricGpu(metric),
				gpuMemoryUsed: metricGpuMemoryUsed(metric),
				gpuMemoryTotal: metricGpuMemoryTotal(metric),
				gpuSource: metricGpuSource(metric),
			};
		}),
	);
	let stacks = $derived(groupContainersByStack(containers as any[], stackColors));
	let running = $derived(rows.filter((row) => row.state === 'running').length);
	let stopped = $derived(rows.filter((row) => row.state === 'exited' || row.state === 'stopped').length);
	let paused = $derived(rows.filter((row) => row.state === 'paused').length);
	let problem = $derived(rows.filter((row) => row.state === 'dead' || row.state === 'restarting').length);
	let total = $derived(rows.length);
	let totalNetwork = $derived(rows.reduce((sum, row) => sum + row.network, 0));
	let gpuAverage = $derived(avg((systemInfo?.gpu ?? []).map((gpu: any) => Number(gpu.usage ?? 0))));

	// PowerTempGauge 가 GPU 합산값 (전력) / 최대값 (온도) 으로 단일화해서 받음.
	// 멀티 GPU 호스트도 한 게이지로 표시. measured value 가 하나도 없으면 null → "—" 로 표시.
	function gpuAggregate(gpus: any, field: string): number | null {
		if (!Array.isArray(gpus) || gpus.length === 0) return null;
		const vals: number[] = [];
		for (const g of gpus) {
			const raw = g?.[field];
			if (raw == null) continue;
			const num = Number(raw);
			if (Number.isFinite(num)) vals.push(num);
		}
		if (vals.length === 0) return null;
		// 전력은 합산 (다중 GPU 총 W), 온도는 최대 (가장 뜨거운 GPU 기준).
		return field === 'powerDrawW' ? vals.reduce((a, b) => a + b, 0) : Math.max(...vals);
	}
	let health = $derived(resolveHealth(systemInfo?.cpu?.usage ?? 0, systemInfo?.memory?.usage ?? 0, systemInfo?.disk?.usage ?? 0, gpuAverage, problem, isDemoServer || $wsConnected));
	let healthScore = $derived.by(() => {
		const cpu = Number(systemInfo?.cpu?.usage ?? 0);
		const memory = Number(systemInfo?.memory?.usage ?? 0);
		const disk = Number(systemInfo?.disk?.usage ?? 0);
		const gpu = gpuAverage || 0;
		const problemPenalty = total ? (problem / total) * 40 : 0;
		const resourcePenalty = (cpu + memory + disk + gpu) / 4;
		return Math.max(0, Math.min(100, 100 - resourcePenalty * 0.6 - problemPenalty));
	});
	let hottest = $derived(
		[...rows].sort((a, b) => hotScore(b) - hotScore(a)).slice(0, 8),
	);
	let historyAnchorMs = $derived(historyPolledAt?.getTime() ?? Date.now());
	let historyModel = $derived(buildHistoryModel(containerHistoryRows, stackHistoryRows, rows, selectedRange, historyAnchorMs));
	let trendLabels = $derived(historyModel.buckets.map((bucket) => formatRangeTick(bucket, selectedRange)));
	// historyModel.buckets 은 epoch seconds. ECharts time axis 는 ms 라 ×1000.
	// 안 하면 [1779065880, …] 같은 값이 ms 로 해석돼 1970-01-21 부근에 점이 몰리고
	// 라벨이 1개만 보이며 streaming 도 안 됨.
	let trendTimestampsMs = $derived(historyModel.buckets.map((bucket) => bucket * 1000));
	let systemTrend = $derived(buildSystemTrend(systemHistoryRows, selectedRange, historyAnchorMs));

	let stackCpuSeries = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stackKey(stack.name));
			return {
				label: stack.name,
				values: trend?.cpu ?? Array.from({ length: historyModel.buckets.length }, () => 0),
				color: stack.color,
			};
		}),
	);
	let stackMemorySeries = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stackKey(stack.name));
			return {
				label: stack.name,
				values: trend?.memory ?? Array.from({ length: historyModel.buckets.length }, () => 0),
				color: stack.color,
			};
		}),
	);
	let stackNetworkSeries = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stackKey(stack.name));
			return {
				label: stack.name,
				values: trend?.network ?? Array.from({ length: historyModel.buckets.length }, () => 0),
				color: stack.color,
			};
		}),
	);
	let stackDiskSeries = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stackKey(stack.name));
			return {
				label: stack.name,
				values: trend?.disk ?? Array.from({ length: historyModel.buckets.length }, () => 0),
				color: stack.color,
			};
		}),
	);
	let stackGpuSeries = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stackKey(stack.name));
			return {
				label: stack.name,
				values: trend?.gpu ?? Array.from({ length: historyModel.buckets.length }, () => 0),
				color: stack.color,
				hidden: trend ? !trend.gpuMeasured : true,
			};
		}),
	);
	let hasAnyGpu = $derived(stackGpuSeries.some((series: any) => !series.hidden));
	let cpuTopNames = $derived(topNamesBySeries(stackCpuSeries));
	let memoryTopNames = $derived(topNamesBySeries(stackMemorySeries));
	let networkTopNames = $derived(topNamesBySeries(stackNetworkSeries));
	let diskTopNames = $derived(topNamesBySeries(stackDiskSeries));
	let gpuTopNames = $derived(topNamesBySeries(stackGpuSeries.filter((s: any) => !s.hidden)));
	let cpuLegend = $derived(legendFromSeries(stackCpuSeries));
	let memoryLegend = $derived(legendFromSeries(stackMemorySeries));
	let networkLegend = $derived(legendFromSeries(stackNetworkSeries));
	let diskLegend = $derived(legendFromSeries(stackDiskSeries));
	let gpuLegend = $derived(legendFromSeries(stackGpuSeries.filter((s: any) => !s.hidden)));

	let sidebarStacks = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stackKey(stack.name));
			const stackRows = rows.filter((row) => row.stack === stack.name);
			const cpuAvg = trend
				? latestNonZero(trend.cpu, avg(stackRows.map((row) => row.cpu)))
				: avg(stackRows.map((row) => row.cpu));
			const memoryAvg = trend
				? latestNonZero(trend.memory, avg(stackRows.map((row) => row.memory)))
				: avg(stackRows.map((row) => row.memory));
			const networkAvg = trend
				? latestNonZero(trend.network, avg(stackRows.map((row) => row.network)))
				: avg(stackRows.map((row) => row.network));
			const gpuRows = stackRows.filter((row) => typeof row.gpu === 'number');
			const liveGpu = gpuRows.length > 0 ? avg(gpuRows.map((row) => row.gpu as number)) : 0;
			const gpuAvg = trend?.gpuMeasured
				? latestNonZero(trend.gpu, liveGpu)
				: gpuRows.length > 0
					? liveGpu
					: null;
			return {
				name: stack.name,
				color: stack.color,
				running: stack.stats.running,
				total: stack.stats.total,
				problem: stackRows.filter((row) => row.state === 'dead' || row.state === 'restarting').length,
				cpuAvg,
				memoryAvg,
				networkAvg,
				gpuAvg,
			};
		}),
	);

	let containersGrouped = $derived(
		(stacks as any[]).map((stack: any) => {
			const stackRows = rows.filter((row) => row.stack === stack.name);
			return {
				name: stack.name,
				color: stack.color,
				running: stack.stats.running,
				total: stack.stats.total,
				containers: stackRows.map((row) => {
					const trend = historyModel.containerMap.get(row.id);
					const gpuTrend = trend?.gpuAvg;
					return {
						id: row.id,
						name: row.name,
						state: row.state,
						cpu: trend?.cpuAvg ?? row.cpu,
						memory: trend?.memoryAvg ?? row.memory,
						network: trend?.networkAvg ?? row.network,
						gpu: typeof gpuTrend === 'number' ? gpuTrend : row.gpu,
						gpuMemoryUsed: row.gpuMemoryUsed,
						gpuMemoryTotal: row.gpuMemoryTotal,
						container: row.container,
					};
				}),
			};
		}),
	);

	let stateSegments = $derived([
		{ label: '실행', value: running, color: '#34d399' },
		{ label: '일시정지', value: paused, color: '#fbbf24' },
		{ label: '문제', value: problem, color: '#f87171' },
		{ label: '중지', value: stopped, color: '#94a3b8' },
	]);

	let radarAxes = $derived([
		{ label: 'CPU', value: Number(systemInfo?.cpu?.usage ?? 0), reference: systemTrend.cpuAvg },
		{ label: '메모리', value: Number(systemInfo?.memory?.usage ?? 0), reference: systemTrend.memoryAvg },
		{ label: '디스크', value: Number(systemInfo?.disk?.usage ?? 0), reference: systemTrend.diskAvg },
		{ label: 'GPU', value: gpuAverage, reference: systemTrend.gpuAvg },
		{
			label: '네트워크',
			value:
				systemTrend.networkMax > 0
					? Math.min(100, (systemTrend.networkAvg / systemTrend.networkMax) * 100)
					: 0,
			reference: 50,
		},
		{
			label: '컨테이너',
			value: total > 0 ? Math.min(100, (running / total) * 100) : 0,
			reference: total > 0 ? 95 : 0,
		},
	]);

	let bubbleStacks = $derived(
		sidebarStacks.map((stack) => ({
			name: stack.name,
			color: stack.color,
			cpu: stack.cpuAvg,
			memory: stack.memoryAvg,
			network: stack.networkAvg,
			containers: stack.total,
			problem: stack.problem,
		})),
	);

	let healthTone: 'ok' | 'warn' | 'hot' | 'dim' = $derived.by(() => {
		if (!(isDemoServer || $wsConnected)) return 'dim';
		if (health === 'critical') return 'hot';
		if (health === 'warning') return 'warn';
		return 'ok';
	});

	let eventRows = $derived.by(() => {
		const now = historyPolledAt ?? lastLiveUpdate ?? new Date();
		const events: {
			id: string;
			severity: 'warn' | 'critical' | 'info';
			at: Date;
			stack: string;
			target: string;
			message: string;
			container?: any;
			action?: string;
		}[] = [];
		for (const row of rows) {
			if (row.state === 'dead' || row.state === 'restarting') {
				events.push({
					id: `state-${row.id}`,
					severity: 'critical',
					at: now,
					stack: row.stack,
					target: row.name,
					message: row.state === 'dead' ? '컨테이너 비정상 종료(dead)' : '재시작 루프 감지',
					container: row.container,
					action: '상세 확인',
				});
			} else if (row.state === 'paused') {
				events.push({
					id: `state-${row.id}`,
					severity: 'warn',
					at: now,
					stack: row.stack,
					target: row.name,
					message: '일시정지 상태',
					container: row.container,
					action: '재개 검토',
				});
			}
			if (row.cpu >= 90) {
				events.push({
					id: `cpu-${row.id}`,
					severity: row.cpu >= 98 ? 'critical' : 'warn',
					at: now,
					stack: row.stack,
					target: row.name,
					message: `CPU ${row.cpu.toFixed(1)}% 초과 사용`,
					container: row.container,
					action: '부하 분석',
				});
			}
			if (row.memory >= 90) {
				events.push({
					id: `mem-${row.id}`,
					severity: row.memory >= 98 ? 'critical' : 'warn',
					at: now,
					stack: row.stack,
					target: row.name,
					message: `메모리 ${row.memory.toFixed(1)}% 점유`,
					container: row.container,
					action: '리소스 검토',
				});
			}
		}
		const cpu = Number(systemInfo?.cpu?.usage ?? 0);
		const memory = Number(systemInfo?.memory?.usage ?? 0);
		const disk = Number(systemInfo?.disk?.usage ?? 0);
		if (cpu >= 90) {
			events.push({
				id: 'sys-cpu',
				severity: 'critical',
				at: now,
				stack: '시스템',
				target: 'CPU',
				message: `서버 CPU 사용률 ${cpu.toFixed(1)}%`,
				action: '호스트 검토',
			});
		}
		if (memory >= 90) {
			events.push({
				id: 'sys-mem',
				severity: 'critical',
				at: now,
				stack: '시스템',
				target: '메모리',
				message: `서버 메모리 사용률 ${memory.toFixed(1)}%`,
				action: '호스트 검토',
			});
		}
		if (disk >= 85) {
			events.push({
				id: 'sys-disk',
				severity: 'warn',
				at: now,
				stack: '시스템',
				target: '디스크',
				message: `디스크 ${disk.toFixed(1)}% 사용`,
				action: '용량 확보',
			});
		}
		// Agent online/offline transitions — pulled from the global store
		// so 1/N-down outages and reconnections appear in the dashboard's
		// 실시간 이벤트 panel even if no toast was shown at the moment of
		// transition. NOT filtered by selectedServerId on purpose: when
		// only one of two agents is down, the operator is necessarily
		// viewing the surviving one and still needs to see that the other
		// one dropped.
		for (const evt of $statusEvents) {
			const at = evt.last_seen_at ? new Date(evt.last_seen_at) : new Date(evt.receivedAt);
			if (evt.status === 'offline') {
				events.push({
					id: `agent-offline-${evt.server_id}-${evt.receivedAt}`,
					severity: 'critical',
					at,
					stack: '시스템',
					target: evt.hostname || 'Agent',
					message: 'Agent 연결 끊김',
					action: '점검 필요',
				});
			} else {
				const reconnectedAfter = formatOfflineDuration(evt.previous_offline_seconds);
				events.push({
					id: `agent-online-${evt.server_id}-${evt.receivedAt}`,
					severity: 'info',
					at,
					stack: '시스템',
					target: evt.hostname || 'Agent',
					message: reconnectedAfter
						? `Agent 재연결 (${reconnectedAfter} 끊김)`
						: 'Agent 재연결',
				});
			}
		}

		return events
			.sort((a, b) => {
				const weight = (sev: string) => (sev === 'critical' ? 0 : sev === 'warn' ? 1 : 2);
				const w = weight(a.severity) - weight(b.severity);
				if (w !== 0) return w;
				return b.at.getTime() - a.at.getTime();
			})
			.slice(0, 50);
	});

	function formatOfflineDuration(secs: number | null | undefined): string {
		if (secs == null || secs < 0) return '';
		if (secs < 60) return `${secs}초`;
		if (secs < 3600) return `${Math.round(secs / 60)}분`;
		if (secs < 86400) {
			const h = Math.floor(secs / 3600);
			const m = Math.round((secs % 3600) / 60);
			return m > 0 ? `${h}시간 ${m}분` : `${h}시간`;
		}
		const d = Math.floor(secs / 86400);
		const h = Math.round((secs % 86400) / 3600);
		return h > 0 ? `${d}일 ${h}시간` : `${d}일`;
	}

	function topNamesBySeries(series: { label: string; values: number[] }[]): string[] {
		return [...series]
			.map((item) => ({
				label: item.label,
				last: item.values.length ? Number(item.values[item.values.length - 1] ?? 0) : 0,
			}))
			.sort((a, b) => b.last - a.last)
			.slice(0, 5)
			.map((item) => item.label);
	}

	function legendFromSeries(series: { label: string; values: number[]; color: string }[]) {
		return series.map((item) => ({
			label: item.label,
			color: item.color,
			value: item.values.length ? Number(item.values[item.values.length - 1] ?? 0) : 0,
		}));
	}

	function decodeUsername(token: string): string {
		try {
			return JSON.parse(atob(token.split('.')[1])).username ?? '';
		} catch {
			return '';
		}
	}

	function decodeRole(token: string): string {
		try {
			return JSON.parse(atob(token.split('.')[1])).role ?? '';
		} catch {
			return '';
		}
	}

	function authHeaders(): HeadersInit {
		return { Authorization: `Bearer ${accessToken}` };
	}

	async function doLogin() {
		loginError = '';
		try {
			const response = await fetch(`${base}/api/auth/token/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username: loginUsername, password: loginPassword }),
			});
			const json = await response.json().catch(() => ({}));
			if (!response.ok) {
				loginError = json.error?.detail || json.detail || '로그인에 실패했습니다.';
				return;
			}
			accessToken = json.data?.access || json.access;
			if (decodeRole(accessToken) === 'user') {
				goto(`${base}/user`);
				return;
			}
			if (browser) localStorage.setItem('hc_access_token', accessToken);
			isLoggedIn = true;
			currentUsername = decodeUsername(accessToken);
			connectGlobal(accessToken);
			goto(`${base}/`);
		} catch {
			loginError = '서버에 연결할 수 없습니다.';
		}
	}

	function clearHistoryState() {
		systemHistoryRows = [];
		containerHistoryRows = [];
		historyPolledAt = null;
		historyError = '';
	}

	function stopHistoryPolling() {
		if (historyTimer) {
			clearInterval(historyTimer);
			historyTimer = null;
		}
	}

	function startHistoryPolling() {
		stopHistoryPolling();
		if (!selectedServerId) return;
		historyTimer = setInterval(() => {
			void loadHistoricalData();
		}, rangeConfig.pollMs);
	}

	function goToServerPicker() {
		stopHistoryPolling();
		disconnect();
		selectedServerId = '';
		selectedContainer = null;
		resetViewForServerChange();
		clearHistoryState();
	}

	function doLogout() {
		stopHistoryPolling();
		disconnect();
		disconnectGlobal();
		accessToken = '';
		isLoggedIn = false;
		currentUsername = '';
		selectedServerId = '';
		selectedContainer = null;
		agents = [];
		resetViewForServerChange();
		clearHistoryState();
		if (browser) {
			localStorage.removeItem('hc_access_token');
			localStorage.removeItem('hc_selected_server');
		}
		// 어느 페이지에서 로그아웃하든 항상 / 의 로그인 화면으로 복귀.
		goto(`${base}/`);
	}

	async function loadAgents() {
		agentsLoading = true;
		try {
			let liveAgents: Agent[] = [];
			try {
				// `active=true` 를 빼고 approved 전체를 가져온다 — fleet badge 분모(totalKnown)
				// 가 root 페이지(/) 와 일치하도록. is_active 분기는 seedActiveAgents 에서 한다.
				const response = await fetch(`${base}/api/agents/?status=approved&page_size=200&ordering=hostname`, {
					headers: authHeaders(),
				});
				if (response.status === 401) {
					doLogout();
					return;
				}
				const json = await response.json().catch(() => ({}));
				const data = json.data;
				liveAgents = data?.results ?? data ?? [];
			} catch {
				liveAgents = [];
			}
			agents = liveAgents;
			seedActiveAgents(
				liveAgents.filter((agent: Agent) => agent.is_active).map((agent: Agent) => agent.id),
			);
			// Seed the persisted transition log so the 실시간 이벤트 panel shows
			// agent online/offline events the user might have missed (browser
			// closed, backend restarted, ...). Live WS events will then prepend
			// on top of this baseline.
			try {
				const eventsRes = await fetch(`${base}/api/agents/status-events/?limit=20`, {
					headers: authHeaders(),
				});
				if (eventsRes.ok) {
					const ej = await eventsRes.json();
					const events = ej.data ?? ej.results ?? ej ?? [];
					if (Array.isArray(events) && events.length > 0) {
						seedStatusEventsFromBackend(events);
					}
				}
			} catch {
				/* ignore */
			}
			const saved = browser ? localStorage.getItem('hc_selected_server') : '';
			// 처음 진입 시엔 살아있는 agent 부터 보여주는 게 직관적. offline 만 남으면 그대로.
			const onlineAgents = agents.filter((agent) => agent.is_active);
			const fallbackAgent = onlineAgents[0] ?? agents[0];
			const preferred = selectedServerId && agents.some((agent) => agent.id === selectedServerId)
				? selectedServerId
				: saved && agents.some((agent) => agent.id === saved)
					? saved
					: fallbackAgent?.id;
			if (preferred) {
				selectServer(preferred);
			}
		} finally {
			agentsLoading = false;
		}
	}

	function selectServer(serverId: string) {
		if (!serverId || serverId === selectedServerId) return;
		disconnect();
		selectedServerId = serverId;
		selectedContainer = null;
		resetViewForServerChange();
		clearHistoryState();
		if (browser) localStorage.setItem('hc_selected_server', serverId);
		if (serverId === DEMO_SERVER_ID) {
			demoState = buildDemoState(Date.now());
			lastLiveUpdate = new Date();
		} else {
			connect(serverId, accessToken);
		}
		void loadHistoricalData();
		startHistoryPolling();
	}

	function refreshConnection() {
		if (!selectedServerId) return;
		if (selectedServerId === DEMO_SERVER_ID) {
			demoState = buildDemoState(Date.now());
		} else if (accessToken) {
			disconnect();
			connect(selectedServerId, accessToken);
		}
		clearHistoryState();
		void loadHistoricalData();
		startHistoryPolling();
	}

	function changeRange(range: MonitoringRange) {
		selectedRange = range;
		clearHistoryState();
		void loadHistoricalData();
		startHistoryPolling();
	}

	function open3d() {
		if (browser && selectedServerId) localStorage.setItem('hc_selected_server', selectedServerId);
		goto(`${base}/server-3d`);
	}

	type SystemBucket = {
		agent: string;
		bucket_start: string;
		bucket_epoch: number;
		cpu_avg: number;
		cpu_max: number;
		memory_avg: number;
		memory_max: number;
		memory_used_avg?: number;
		memory_total_avg?: number;
		disk_avg: number;
		disk_max: number;
		network_rx_max: number;
		network_tx_max: number;
		sample_count: number;
	};
	type ContainerBucket = {
		agent: string;
		container_id: string;
		bucket_start: string;
		bucket_epoch: number;
		// 정규화된 0-100 CPU% (preferred). Agent v2가 채움. cores_quota 결정
		// 실패한 bucket은 null.
		cpu_usage_pct_avg?: number | null;
		cpu_usage_pct_max?: number | null;
		// raw 코어 합산 % (분석용, optional)
		cpu_usage_avg?: number | null;
		cpu_usage_max?: number | null;
		cpu_cores_quota_avg?: number | null;
		// 호환용 (구버전 backend가 이 필드만 보낼 수 있음)
		cpu_avg: number;
		cpu_max: number;
		memory_avg: number;
		memory_max: number;
		memory_percent_avg: number;
		network_rx_max: number;
		network_tx_max: number;
		disk_read_max: number;
		disk_write_max: number;
		sample_count: number;
	};
	type StackBucket = {
		agent: string;
		stack: string;
		bucket_start: string;
		bucket_epoch: number;
		cpu_avg: number;
		cpu_max: number;
		memory_percent_avg: number;
		memory_percent_max: number;
		memory_bytes_avg: number;
		network_rx_max: number;
		network_tx_max: number;
		disk_read_max: number;
		disk_write_max: number;
		gpu_usage_avg?: number | null;
		gpu_usage_max?: number | null;
		gpu_memory_used_max?: number | null;
		gpu_memory_total_max?: number | null;
		container_count: number;
		sample_count: number;
	};

	// Stack 키는 case-insensitive 비교로 통일. backend 가 normalize 한 결과와
	// frontend resolveGroup 결과의 case 가 어긋나는 케이스가 있어서 (예: 한쪽만
	// lowercase 라벨) 양쪽 모두 lowercase 로 비교해 매칭 누락을 막는다.
	function stackKey(name: string | null | undefined): string {
		return (name ?? 'Unmanaged').toLowerCase();
	}

	async function fetchBuckets<T>(endpoint: string, params: URLSearchParams): Promise<T[]> {
		const response = await fetch(`${base}${endpoint}?${params.toString()}`, {
			headers: authHeaders(),
		});
		if (response.status === 401) {
			doLogout();
			return [];
		}
		const json = await response.json().catch(() => ({}));
		if (!response.ok) {
			throw new Error(json.error?.detail || json.detail || `HTTP ${response.status}`);
		}
		const payload = json.data ?? json;
		return (payload?.results ?? []) as T[];
	}

	function clampPct(v: number): number {
		if (!Number.isFinite(v)) return 0;
		return Math.max(0, Math.min(100, v));
	}

	function bucketsToSystemRows(buckets: SystemBucket[]): SystemHistoryRow[] {
		return buckets.map((b) => ({
			recorded_at: b.bucket_start,
			cpu_usage: clampPct(b.cpu_avg),
			memory_usage: clampPct(b.memory_avg),
			disk_usage: clampPct(b.disk_avg),
			network_rx: b.network_rx_max,
			network_tx: b.network_tx_max,
			processes_total: null,
			processes_running: null,
			logins_total: null,
			gpu: [],
		}));
	}

	function bucketsToContainerRows(buckets: ContainerBucket[]): ContainerHistoryRow[] {
		// Agent v2는 이미 정규화된 0-100 값을 cpu_usage_pct_avg 로 보냄. 그대로 사용.
		// 구버전 backend 응답엔 그 필드가 없으므로 cpu_avg 로 fallback (이미 정규화돼 있음).
		return buckets.map((b) => {
			const cpuPct = b.cpu_usage_pct_avg ?? b.cpu_avg ?? 0;
			return {
				recorded_at: b.bucket_start,
				container_id: b.container_id,
				cpu_usage: typeof cpuPct === 'number' ? cpuPct : 0,
				memory_usage: b.memory_avg,
				memory_limit: 0,
				memory_percent: clampPct(b.memory_percent_avg),
				network_rx: b.network_rx_max,
				network_tx: b.network_tx_max,
				disk_read: b.disk_read_max,
				disk_write: b.disk_write_max,
			};
		});
	}

	async function loadHistoricalData() {
		if (!selectedServerId) return;
		const currentSeq = ++historyLoadSeq;
		historyLoading = true;
		historyError = '';
		const anchor = Date.now();

		try {
			if (isDemoServer) {
				const demoHistory = buildDemoHistory(anchor, selectedRange);
				if (currentSeq !== historyLoadSeq) return;
				systemHistoryRows = demoHistory.system;
				containerHistoryRows = demoHistory.containers;
				historyPolledAt = new Date(anchor);
				return;
			}
			if (!accessToken) return;

			// backend가 bucket 단위로 미리 집계. frontend가 표시할 점 개수만큼의
			// 시간 윈도우(bucket × points)를 from_time/to_time으로 명시.
			// ?range=1m 만 보내면 backend가 최근 1분치만 필터해 점이 1개만 반환됨.
			const windowMs = rangeConfig.bucketSeconds * rangeConfig.points * 1000;
			const fromTime = new Date(anchor - windowMs).toISOString();
			const toTime = new Date(anchor).toISOString();
			const systemParams = new URLSearchParams({
				agent: selectedServerId,
				from_time: fromTime,
				to_time: toTime,
				bucket: String(rangeConfig.bucketSeconds),
			});
			const containerParams = new URLSearchParams({
				agent: selectedServerId,
				from_time: fromTime,
				to_time: toTime,
				bucket: String(rangeConfig.bucketSeconds),
			});

			const stackParams = new URLSearchParams({
				agent: selectedServerId,
				from_time: fromTime,
				to_time: toTime,
				bucket: String(rangeConfig.bucketSeconds),
			});

			const [systemBuckets, containerBuckets, stackBuckets] = await Promise.all([
				fetchBuckets<SystemBucket>('/api/metrics/system/buckets/', systemParams),
				fetchBuckets<ContainerBucket>('/api/metrics/containers/buckets/', containerParams),
				fetchBuckets<StackBucket>('/api/metrics/stacks/buckets/', stackParams),
			]);

			if (currentSeq !== historyLoadSeq) return;
			systemHistoryRows = bucketsToSystemRows(systemBuckets);
			containerHistoryRows = bucketsToContainerRows(containerBuckets);
			stackHistoryRows = stackBuckets;
			historyPolledAt = new Date(anchor);
		} catch (error) {
			if (currentSeq !== historyLoadSeq) return;
			historyError = error instanceof Error ? error.message : '추이 데이터를 불러오지 못했습니다.';
		} finally {
			if (currentSeq === historyLoadSeq) historyLoading = false;
		}
	}

	function metricFor(container: any): any {
		return containerMetrics.get(container.id) ?? containerMetrics.get(container.shortId) ?? {};
	}

	function metricCpu(metric: any): number {
		// Agent v2 이상: cpu.usage_pct가 이미 0-100 정규화 값. 그대로 사용.
		const pct = metric?.cpu?.usage_pct ?? metric?.cpu_usage_pct;
		if (pct !== null && pct !== undefined && Number.isFinite(Number(pct))) {
			return Math.max(0, Math.min(100, Number(pct)));
		}
		// Legacy: raw 코어 합산 % → cores_quota 또는 cores로 나눠 정규화.
		const raw = Number(metric?.cpu?.usage ?? metric?.cpu_usage ?? metric?.cpu ?? 0);
		if (!Number.isFinite(raw)) return 0;
		const quota = Number(metric?.cpu?.cores_quota ?? metric?.cpu?.cores ?? 0);
		const value = quota >= 1 ? raw / quota : raw;
		return Math.max(0, Math.min(100, value));
	}

	function metricMemory(metric: any): number {
		const raw = Number(metric?.memory?.percent ?? metric?.memory_percent ?? metric?.memory?.usage_percent ?? 0);
		if (!Number.isFinite(raw)) return 0;
		// Some containers without limits report >100% relative to limit fallback; pin to 0-100.
		return Math.max(0, Math.min(100, raw));
	}

	function metricNetwork(metric: any): number {
		const stats = Array.isArray(metric?.network_stats) ? metric.network_stats : [];
		const sum = stats.length
			? stats.reduce((acc: number, stat: any) => acc + Number(stat.rx_rate_bps ?? 0) + Number(stat.tx_rate_bps ?? 0), 0)
			: Number(metric?.network?.rx_rate_bps ?? 0) + Number(metric?.network?.tx_rate_bps ?? 0);
		// rx/tx counters can briefly read negative across resets; floor at 0.
		return Number.isFinite(sum) ? Math.max(0, sum) : 0;
	}

	function metricGpu(metric: any): number | null {
		const raw = metric?.gpu?.usage ?? metric?.gpu_usage;
		if (raw === null || raw === undefined) return null;
		const value = Number(raw);
		if (!Number.isFinite(value)) return null;
		// Agent contract guarantees 0-100; clamp defensively against transport glitches.
		return Math.max(0, Math.min(100, value));
	}

	// Agent v3 contract: memoryUsed/memoryTotal (camelCase, bytes).
	// Prod (Agent v2): memory_used/memory_total (snake_case, MiB) — fallback 시 bytes 로 환산.
	function metricGpuMemoryUsed(metric: any): number | null {
		const camel = metric?.gpu?.memoryUsed;
		if (camel !== null && camel !== undefined) {
			const v = Number(camel);
			return Number.isFinite(v) ? v : null;
		}
		const snake = metric?.gpu?.memory_used;
		if (snake === null || snake === undefined) return null;
		const v = Number(snake);
		return Number.isFinite(v) ? v * 1024 * 1024 : null;  // MiB → bytes
	}

	function metricGpuMemoryTotal(metric: any): number | null {
		const camel = metric?.gpu?.memoryTotal;
		if (camel !== null && camel !== undefined) {
			const v = Number(camel);
			return Number.isFinite(v) ? v : null;
		}
		const snake = metric?.gpu?.memory_total;
		if (snake === null || snake === undefined) return null;
		const v = Number(snake);
		return Number.isFinite(v) ? v * 1024 * 1024 : null;  // MiB → bytes
	}

	function metricGpuSource(metric: any): string | null {
		const raw = metric?.gpu?.source;
		return typeof raw === 'string' ? raw : null;
	}

	function displayName(container: any): string {
		return container.names?.[0]?.replace('/', '') || container.name || container.shortId || container.id?.slice(0, 12) || '-';
	}

	function avg(values: number[]): number {
		const valid = values.filter((value) => Number.isFinite(value));
		return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : 0;
	}

	function max(values: number[]): number {
		const valid = values.filter((value) => Number.isFinite(value));
		return valid.length ? Math.max(...valid) : 0;
	}

	function latestNonZero(values: number[], fallback: number): number {
		for (let index = values.length - 1; index >= 0; index -= 1) {
			if (Number.isFinite(values[index]) && values[index] > 0) return values[index];
		}
		return fallback;
	}

	function formatClock(value: Date | null): string {
		return value ? value.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-';
	}

	function formatUptime(seconds?: number): string {
		const value = Number(seconds ?? 0);
		if (!value) return '-';
		const days = Math.floor(value / 86400);
		const hours = Math.floor((value % 86400) / 3600);
		const minutes = Math.floor((value % 3600) / 60);
		if (days > 0) return `${days}일 ${hours}시간`;
		if (hours > 0) return `${hours}시간 ${minutes}분`;
		return `${minutes}분`;
	}

	function hotScore(row: Row): number {
		return row.cpu * 1.1 + row.memory + row.network / 1024 / 1024;
	}

	function resolveHealth(cpu: number, memory: number, disk: number, gpu: number, problems: number, connected: boolean): 'healthy' | 'warning' | 'critical' | 'offline' {
		if (!connected) return 'offline';
		if (cpu >= 90 || memory >= 90 || disk >= 90 || gpu >= 95 || problems > 0) return 'critical';
		if (cpu >= 70 || memory >= 75 || disk >= 80 || gpu >= 80) return 'warning';
		return 'healthy';
	}

	function healthLabel(value: typeof health): string {
		return value === 'healthy' ? '정상' : value === 'warning' ? '주의' : value === 'critical' ? '위험' : '연결 대기';
	}

	function stateLabel(state: string): string {
		return state === 'running' ? '실행'
			: state === 'exited' || state === 'stopped' ? '중지'
			: state === 'restarting' ? '재시작'
			: state === 'dead' ? '장애'
			: state === 'paused' ? '일시정지'
			: state || '생성';
	}

	function formatRate(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let index = 0;
		while (next >= 1024 && index < units.length - 1) {
			next /= 1024;
			index += 1;
		}
		return `${next.toFixed(next >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
	}

	function formatRateCompact(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0';
		const units = ['B', 'K', 'M', 'G'];
		let next = value;
		let index = 0;
		while (next >= 1024 && index < units.length - 1) {
			next /= 1024;
			index += 1;
		}
		return `${next.toFixed(next >= 10 || index === 0 ? 0 : 1)}${units[index]}`;
	}

	function buildHistoryModel(historyRows: ContainerHistoryRow[], stackBuckets: StackBucket[], currentRows: Row[], range: MonitoringRange, anchorMs: number): HistoryModel {
		const config = MONITORING_RANGE_CONFIG[range];
		const buckets = buildRangeBuckets(range, anchorMs);
		const bucketIndex = new Map(buckets.map((bucket, index) => [bucket, index]));
		const rowByHistoryId = new Map<string, Row>();

		for (const row of currentRows) {
			rowByHistoryId.set(row.id, row);
			rowByHistoryId.set(row.id.slice(0, 12), row);
			if (row.container.shortId) rowByHistoryId.set(row.container.shortId, row);
		}

		const perContainer = new Map<string, { row: Row; cpuBuckets: number[][]; memoryBuckets: number[][]; networkBuckets: number[][]; diskBuckets: number[][]; gpuBuckets: number[][]; gpuMeasured: boolean; samples: number }>();
		for (const row of currentRows) {
			perContainer.set(row.id, {
				row,
				cpuBuckets: Array.from({ length: buckets.length }, () => []),
				memoryBuckets: Array.from({ length: buckets.length }, () => []),
				networkBuckets: Array.from({ length: buckets.length }, () => []),
				diskBuckets: Array.from({ length: buckets.length }, () => []),
				gpuBuckets: Array.from({ length: buckets.length }, () => []),
				gpuMeasured: false,
				samples: 0,
			});
		}

		const previousByContainer = new Map<string, { rx: number; tx: number; dr: number; dw: number; at: number }>();
		const sorted = [...historyRows].sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());

		for (const item of sorted) {
			const matched = rowByHistoryId.get(item.container_id) ?? rowByHistoryId.get(item.container_id.slice(0, 12));
			if (!matched) continue;
			const ts = new Date(item.recorded_at).getTime();
			const bucket = bucketEpoch(ts, config.bucketSeconds);
			const index = bucketIndex.get(bucket);
			if (index === undefined) continue;
			const entry = perContainer.get(matched.id);
			if (!entry) continue;

			const previous = previousByContainer.get(item.container_id);
			const seconds = previous ? Math.max(1, (ts - previous.at) / 1000) : config.bucketSeconds;
			const rx = Number(item.network_rx ?? 0);
			const tx = Number(item.network_tx ?? 0);
			const dr = Number(item.disk_read ?? 0);
			const dw = Number(item.disk_write ?? 0);
			const networkRate = previous ? Math.max(0, (rx - previous.rx) + (tx - previous.tx)) / seconds : 0;
			const diskRate = previous ? Math.max(0, (dr - previous.dr) + (dw - previous.dw)) / seconds : 0;

			entry.cpuBuckets[index].push(Number(item.cpu_usage ?? 0));
			entry.memoryBuckets[index].push(Number(item.memory_percent ?? 0));
			entry.networkBuckets[index].push(networkRate);
			entry.diskBuckets[index].push(diskRate);
			if (item.gpu_usage !== null && item.gpu_usage !== undefined) {
				const gpuValue = Number(item.gpu_usage);
				if (Number.isFinite(gpuValue)) {
					entry.gpuBuckets[index].push(gpuValue);
					entry.gpuMeasured = true;
				}
			}
			entry.samples += 1;
			previousByContainer.set(item.container_id, { rx, tx, dr, dw, at: ts });
		}

		const containerMap = new Map<string, ContainerTrend>();

		for (const row of currentRows) {
			const entry = perContainer.get(row.id);
			const cpuSeries = fillBuckets(entry?.cpuBuckets ?? [], row.cpu);
			const memorySeries = fillBuckets(entry?.memoryBuckets ?? [], row.memory);
			const networkSeries = fillBuckets(entry?.networkBuckets ?? [], row.network);
			const liveGpu = typeof row.gpu === 'number' ? row.gpu : 0;
			const hasLiveGpu = typeof row.gpu === 'number';
			const gpuMeasured = (entry?.gpuMeasured ?? false) || hasLiveGpu;
			const gpuSeries = gpuMeasured ? fillBuckets(entry?.gpuBuckets ?? [], liveGpu) : Array.from({ length: buckets.length }, () => 0);
			const cpuAvg = avg(nonZero(cpuSeries, row.cpu));
			const memoryAvg = avg(nonZero(memorySeries, row.memory));
			const networkAvg = avg(nonZero(networkSeries, row.network));
			const gpuAvg = gpuMeasured ? (avg(nonZero(gpuSeries, liveGpu)) || liveGpu) : null;

			containerMap.set(row.id, {
				cpu: cpuSeries,
				memory: memorySeries,
				network: networkSeries,
				gpu: gpuSeries,
				cpuAvg: cpuAvg || row.cpu,
				memoryAvg: memoryAvg || row.memory,
				networkAvg: networkAvg || row.network,
				gpuAvg,
				samples: entry?.samples ?? 0,
			});
		}

		// Stack 시계열은 backend `/api/metrics/stacks/buckets/` 응답을 그대로 사용.
		// 기존엔 frontend 가 컨테이너 단위 응답을 매번 reduce 했는데, 멀티서버 +
		// 컨테이너 수 폭증 시 비싸진다 (네트워크 + CPU 둘 다). backend SQL 한 번으로
		// 끝내고 frontend 는 bucket index 정렬만 한다.
		const stackMap = buildStackTrendMap(stackBuckets, buckets, config.bucketSeconds, currentRows);

		return { containerMap, stackMap, buckets };
	}

	function buildStackTrendMap(
		stackBuckets: StackBucket[],
		buckets: number[],
		bucketSeconds: number,
		currentRows: Row[],
	): Map<string, StackTrend> {
		const bucketIndex = new Map(buckets.map((bucket, index) => [bucket, index]));

		// 스택별 시계열 누적 슬롯. lowercase 키로 통일해서 currentRows 의 stack
		// 케이스와 backend 의 stack 케이스가 어긋나도 매칭되도록 한다.
		type StackAccumulator = {
			cpu: number[];
			memory: number[];
			network: (number | null)[];
			disk: (number | null)[];
			gpu: number[];
			gpuMeasured: boolean;
			netCum: (number | null)[];
			diskCum: (number | null)[];
		};
		const empty = (): StackAccumulator => ({
			cpu: Array.from({ length: buckets.length }, () => 0),
			memory: Array.from({ length: buckets.length }, () => 0),
			network: Array.from({ length: buckets.length }, () => null),
			disk: Array.from({ length: buckets.length }, () => null),
			gpu: Array.from({ length: buckets.length }, () => 0),
			gpuMeasured: false,
			netCum: Array.from({ length: buckets.length }, () => null),
			diskCum: Array.from({ length: buckets.length }, () => null),
		});
		const acc = new Map<string, StackAccumulator>();

		for (const b of stackBuckets) {
			const ts = new Date(b.bucket_start).getTime();
			const bucket = bucketEpoch(ts, bucketSeconds);
			const index = bucketIndex.get(bucket);
			if (index === undefined) continue;
			const key = stackKey(b.stack);
			let entry = acc.get(key);
			if (!entry) {
				entry = empty();
				acc.set(key, entry);
			}
			entry.cpu[index] = clampPercent(b.cpu_avg ?? 0);
			entry.memory[index] = clampPercent(b.memory_percent_avg ?? 0);
			entry.netCum[index] = (b.network_rx_max ?? 0) + (b.network_tx_max ?? 0);
			entry.diskCum[index] = (b.disk_read_max ?? 0) + (b.disk_write_max ?? 0);
			if (b.gpu_usage_avg !== null && b.gpu_usage_avg !== undefined) {
				entry.gpu[index] = clampPercent(Number(b.gpu_usage_avg));
				entry.gpuMeasured = true;
			}
		}

		// 누적 byte 시계열 → bucket 간 차분 ÷ bucket 길이로 rate(B/s) 환산.
		// 첫 bucket 은 직전 값이 없어 0 으로 남기고, prev 가 null 이면 그 다음 bucket 도 0.
		for (const entry of acc.values()) {
			for (let i = 0; i < buckets.length; i += 1) {
				const cur = entry.netCum[i];
				const prev = i > 0 ? entry.netCum[i - 1] : null;
				entry.network[i] = cur !== null && prev !== null
					? Math.max(0, (cur - prev) / bucketSeconds)
					: 0;
				const dCur = entry.diskCum[i];
				const dPrev = i > 0 ? entry.diskCum[i - 1] : null;
				entry.disk[i] = dCur !== null && dPrev !== null
					? Math.max(0, (dCur - dPrev) / bucketSeconds)
					: 0;
			}
		}

		// stackMap 구성. count/running 은 시계열에 들어있지 않아 currentRows 에서
		// 직접 카운트 (가벼운 O(N) 한 번).
		const stackMap = new Map<string, StackTrend>();
		const countByKey = new Map<string, { count: number; running: number }>();
		for (const row of currentRows) {
			const key = stackKey(row.stack);
			const c = countByKey.get(key) ?? { count: 0, running: 0 };
			c.count += 1;
			if (row.state === 'running') c.running += 1;
			countByKey.set(key, c);
		}
		// stackMap 키 집합 = backend 응답 + currentRows 합집합.
		const keys = new Set<string>([...acc.keys(), ...countByKey.keys()]);
		for (const key of keys) {
			const entry = acc.get(key);
			const counts = countByKey.get(key) ?? { count: 0, running: 0 };
			stackMap.set(key, {
				cpu: entry?.cpu ?? Array.from({ length: buckets.length }, () => 0),
				memory: entry?.memory ?? Array.from({ length: buckets.length }, () => 0),
				network: (entry?.network ?? Array.from({ length: buckets.length }, () => 0)) as number[],
				disk: (entry?.disk ?? Array.from({ length: buckets.length }, () => 0)) as number[],
				gpu: entry?.gpu ?? Array.from({ length: buckets.length }, () => 0),
				gpuMeasured: entry?.gpuMeasured ?? false,
				count: counts.count,
				running: counts.running,
			});
		}
		return stackMap;
	}

	function fillBuckets(buckets: number[][], fallback: number): number[] {
		const values = buckets.map((bucket) => avg(bucket));
		const firstNonZero = values.findIndex((value) => value > 0);
		if (firstNonZero === -1) {
			return values.map((value, index) => (index === values.length - 1 ? fallback : value));
		}
		const firstValue = values[firstNonZero];
		let last = firstValue;
		return values.map((value, index) => {
			if (index < firstNonZero) return firstValue;
			if (value > 0) last = value;
			return value > 0 ? value : last;
		});
	}

	function nonZero(values: number[], fallback: number): number[] {
		const filtered = values.filter((value) => value > 0);
		return filtered.length ? filtered : [fallback];
	}

	function buildSystemTrend(rows: SystemHistoryRow[], range: MonitoringRange, anchorMs: number) {
		const config = MONITORING_RANGE_CONFIG[range];
		const buckets = buildRangeBuckets(range, anchorMs);
		const bucketIndex = new Map(buckets.map((bucket, index) => [bucket, index]));
		const cpuBuckets: number[][] = Array.from({ length: buckets.length }, () => []);
		const memBuckets: number[][] = Array.from({ length: buckets.length }, () => []);
		const diskBuckets: number[][] = Array.from({ length: buckets.length }, () => []);
		const gpuBuckets: number[][] = Array.from({ length: buckets.length }, () => []);
		const netBuckets: number[][] = Array.from({ length: buckets.length }, () => []);
		const procBuckets: number[][] = Array.from({ length: buckets.length }, () => []);
		const sorted = [...rows].sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());
		let prevRow: SystemHistoryRow | null = null;

		for (const row of sorted) {
			const ts = new Date(row.recorded_at).getTime();
			const bucket = bucketEpoch(ts, config.bucketSeconds);
			const index = bucketIndex.get(bucket);
			if (index === undefined) {
				prevRow = row;
				continue;
			}
			cpuBuckets[index].push(Number(row.cpu_usage ?? 0));
			memBuckets[index].push(Number(row.memory_usage ?? 0));
			diskBuckets[index].push(Number(row.disk_usage ?? 0));
			const procTotal = Number(row.processes_total ?? 0);
			if (procTotal > 0) procBuckets[index].push(procTotal);
			const gpuAvg = avg((row.gpu ?? []).map((item: any) => Number(item.usage ?? 0)));
			if (gpuAvg > 0) gpuBuckets[index].push(gpuAvg);
			if (prevRow) {
				const previousTs = new Date(prevRow.recorded_at).getTime();
				const seconds = Math.max(1, (ts - previousTs) / 1000);
				const rx = Math.max(0, Number(row.network_rx ?? 0) - Number(prevRow.network_rx ?? 0));
				const tx = Math.max(0, Number(row.network_tx ?? 0) - Number(prevRow.network_tx ?? 0));
				netBuckets[index].push((rx + tx) / seconds);
			}
			prevRow = row;
		}

		const cpuSeries = fillBuckets(cpuBuckets, Number(systemInfo?.cpu?.usage ?? 0));
		const memSeries = fillBuckets(memBuckets, Number(systemInfo?.memory?.usage ?? 0));
		const diskSeries = fillBuckets(diskBuckets, Number(systemInfo?.disk?.usage ?? 0));
		const gpuSeries = fillBuckets(gpuBuckets, gpuAverage);
		const netSeries = fillBuckets(netBuckets, 0);
		const procFallback = Number(systemInfo?.processes?.total ?? 0);
		const procSeries = fillBuckets(procBuckets, procFallback);

		return {
			cpu: cpuSeries,
			memory: memSeries,
			disk: diskSeries,
			gpu: gpuSeries,
			network: netSeries,
			processes: procSeries,
			cpuAvg: avg(nonZero(cpuSeries, 0)),
			cpuMax: max(cpuSeries),
			memoryAvg: avg(nonZero(memSeries, 0)),
			memoryMax: max(memSeries),
			diskAvg: avg(nonZero(diskSeries, 0)),
			diskMax: max(diskSeries),
			gpuAvg: avg(nonZero(gpuSeries, 0)),
			gpuMax: max(gpuSeries),
			networkAvg: avg(nonZero(netSeries, 0)),
			networkMax: max(netSeries),
			processesAvg: avg(nonZero(procSeries, procFallback)),
			processesMax: max(procSeries),
			hasGpu:
				(Array.isArray(systemInfo?.gpu) && systemInfo.gpu.length > 0) ||
				gpuSeries.some((value) => value > 0),
		};
	}

	function buildDemoState(seed: number): DemoState {
		const containers = DEMO_TEMPLATES.map((template, index) => {
			const state = DEMO_STATES[(index + Math.floor(seed / 9_000)) % DEMO_STATES.length];
			return {
				...template,
				state,
				status:
					state === 'running'
						? `Up ${2 + (index % 18)} hours`
						: state === 'restarting'
							? 'Restarting (1) 18s ago'
							: state === 'paused'
								? 'Paused'
								: `Exited (${index % 3})`,
			};
		});

		const metrics = new Map<string, any>();
		for (const [index, container] of containers.entries()) {
			const wave = Math.sin(seed / 8_000 + index * 0.55);
			const cpu = clampPercent(16 + (index % 10) * 6 + wave * 18);
			const memory = clampPercent(28 + (index % 8) * 7 + Math.cos(seed / 10_500 + index) * 11);
			const rx = (90_000 + index * 36_000 + Math.abs(wave) * 180_000) * (index % 6 === 0 ? 4 : 1);
			const tx = (50_000 + index * 28_000 + Math.abs(Math.cos(wave)) * 130_000) * (index % 7 === 0 ? 3 : 1);
			const usesGpu = ['ai-pipeline', 'ml-train', 'media-encode', 'analytics'].includes(
				DEMO_STACKS[index % DEMO_STACKS.length],
			);
			const gpuUsage = usesGpu ? clampPercent(35 + (index % 7) * 9 + wave * 14) : 0;
			metrics.set(container.id, {
				containerId: container.id,
				cpu: { usage: cpu },
				cpu_usage: cpu,
				memory: { percent: memory },
				memory_percent: memory,
				network: { rx_rate_bps: rx, tx_rate_bps: tx },
				network_stats: [{ network_name: container.networks[0], rx_rate_bps: rx, tx_rate_bps: tx }],
				gpu: usesGpu
					? { usage: gpuUsage, memory_used: 1024 + (index % 8) * 800, memory_total: 24_576, indices: [index % 2] }
					: undefined,
			});
		}

		return {
			systemInfo: {
				hostname: 'DEMO-DENSE-SERVER',
				os: 'Ubuntu 24.04 LTS / Docker dense workload',
				uptime: 86400 * 22 + 3600 * 11,
				cpu: { model: 'AMD EPYC Demo 32 Thread', cores: 16, threads: 32, usage: clampPercent(54 + Math.sin(seed / 6_500) * 19) },
				memory: { total: '128 GB', used: '78 GB', free: '50 GB', usage: clampPercent(61 + Math.cos(seed / 7_500) * 10) },
				disk: { total: '4 TB', used: '2.8 TB', free: '1.2 TB', usage: clampPercent(69 + Math.sin(seed / 12_000) * 6) },
				network: { connections: 440 + Math.round(Math.sin(seed / 9_000) * 75), interfaces: ['eth0', 'docker0', 'br-demo', 'veth-demo'] },
				logins: { total: 8, active: 3 },
				processes: { total: 522, running: 19 },
				docker: { version: '27.3.1', containers: containers.length, images: 94, driver: 'overlay2' },
				gpu: [
					{ index: 0, vendor: 'NVIDIA', model: 'RTX Demo A6000', memoryTotal: 48 * 1024 ** 3, memoryUsed: 24 * 1024 ** 3, usage: clampPercent(48 + Math.cos(seed / 9_000) * 18), temperature: 62 },
					{ index: 1, vendor: 'NVIDIA', model: 'RTX Demo A6000', memoryTotal: 48 * 1024 ** 3, memoryUsed: 32 * 1024 ** 3, usage: clampPercent(64 + Math.sin(seed / 8_800) * 16), temperature: 69 },
				],
			},
			containers,
			metrics,
		};
	}

	function buildDemoHistory(anchorMs: number, range: MonitoringRange): { system: SystemHistoryRow[]; containers: ContainerHistoryRow[] } {
		const buckets = buildRangeBuckets(range, anchorMs);
		const config = MONITORING_RANGE_CONFIG[range];
		const system: SystemHistoryRow[] = [];
		const containers: ContainerHistoryRow[] = [];
		const totals = new Map<string, { rx: number; tx: number; read: number; write: number }>();

		for (const epoch of buckets) {
			const state = buildDemoState(epoch * 1000);
			system.push({
				recorded_at: new Date(epoch * 1000).toISOString(),
				cpu_usage: Number(state.systemInfo.cpu.usage ?? 0),
				memory_usage: Number(state.systemInfo.memory.usage ?? 0),
				disk_usage: Number(state.systemInfo.disk.usage ?? 0),
				network_rx: 1_200_000_000 + epoch * 1400,
				network_tx: 860_000_000 + epoch * 1100,
				processes_total: Number(state.systemInfo.processes.total ?? 0),
				processes_running: Number(state.systemInfo.processes.running ?? 0),
				logins_total: Number(state.systemInfo.logins.total ?? 0),
				gpu: state.systemInfo.gpu,
			});

			for (const container of state.containers) {
				const metric = state.metrics.get(container.id);
				const previous = totals.get(container.id) ?? { rx: 0, tx: 0, read: 0, write: 0 };
				const rxRate = Number(metric?.network?.rx_rate_bps ?? 0);
				const txRate = Number(metric?.network?.tx_rate_bps ?? 0);
				const next = {
					rx: previous.rx + rxRate * config.bucketSeconds,
					tx: previous.tx + txRate * config.bucketSeconds,
					read: previous.read + (2000 + rxRate * 0.05),
					write: previous.write + (1500 + txRate * 0.03),
				};
				totals.set(container.id, next);
				containers.push({
					recorded_at: new Date(epoch * 1000).toISOString(),
					container_id: container.id,
					cpu_usage: Number(metric?.cpu_usage ?? 0),
					memory_usage: Number(metric?.memory_percent ?? 0),
					memory_limit: 8 * 1024 ** 3,
					memory_percent: Number(metric?.memory_percent ?? 0),
					network_rx: next.rx,
					network_tx: next.tx,
					disk_read: next.read,
					disk_write: next.write,
				});
			}
		}

		return { system, containers };
	}

	$effect(() => {
		rows;
		systemInfo;
		if (selectedServerId && (rows.length || systemInfo)) {
			lastLiveUpdate = new Date();
		}
	});

	onMount(async () => {
		if (!browser) return;
		demoTimer = setInterval(() => {
			if (selectedServerId === DEMO_SERVER_ID) {
				demoState = buildDemoState(Date.now());
			}
		}, 1800);

		const savedToken = localStorage.getItem('hc_access_token');
		if (!savedToken) return;
		if (decodeRole(savedToken) === 'user') {
			redirecting = true;
			goto(`${base}/user`);
			return;
		}
		accessToken = savedToken;
		isLoggedIn = true;
		currentUsername = decodeUsername(savedToken);
		connectGlobal(savedToken);
		await loadAgents();
	});

	onDestroy(() => {
		if (demoTimer) clearInterval(demoTimer);
		stopHistoryPolling();
		disconnect();
	});
</script>

<svelte:head>
	<title>서버 2D 관제 - HyperCube</title>
</svelte:head>

{#if redirecting}
	<LoadingOverlay text="이동 중" />
{:else if !isLoggedIn}
	<div class="auth-page">
		<form class="auth-card" onsubmit={(event) => { event.preventDefault(); doLogin(); }}>
			<img src={logoHypercube} alt="HyperCube" />
			<h1>서버 2D 관제</h1>
			<p>한 화면에서 서버 자원, 스택 상태, 전체 컨테이너 상태를 동시에 확인하는 단일 서버 모니터링 화면입니다.</p>
			<label><span>아이디</span><input bind:value={loginUsername} autocomplete="username" placeholder="admin" /></label>
			<label><span>비밀번호</span><input bind:value={loginPassword} autocomplete="current-password" type="password" /></label>
			{#if loginError}<div class="auth-error">{loginError}</div>{/if}
			<button type="submit">로그인</button>
		</form>
	</div>
{:else if !selectedServerId && agentsLoading}
	<LoadingOverlay text="서버 정보 불러오는 중" />
{:else if !selectedServerId}
	<div class="shell">
		<AdminHeader totalAgents={agents.length} username={currentUsername} onLogout={doLogout} />
		<main class="server-picker">
			<h1>서버 없음</h1>
			<p>아직 등록·승인된 서버가 없습니다. Agent를 실행하면 자동으로 등록됩니다.</p>
			<button type="button" class="empty-state" onclick={() => goto(`${base}/`)}>전체 서버 모니터링으로 이동</button>
		</main>
	</div>
{:else if !dataReady}
	<LoadingOverlay text="실시간 메트릭 수신 중" />
{:else}
	<div class="shell">
		<AdminHeader totalAgents={agents.length} username={currentUsername} onLogout={doLogout} />

		<section class="sub-topbar">
			<div class="server-id">
				<span class={`health-dot ${health}`}></span>
				<select class="server-select" value={selectedServerId} onchange={(event) => selectServer(event.currentTarget.value)} aria-label="서버 선택">
					{#each agents as agent (agent.id)}
						<option value={agent.id}>{agent.hostname}</option>
					{/each}
				</select>
				<span class={`status-pill ${health}`}>{healthLabel(health)}</span>
				<div class="server-meta">
					<small class="meta-item">{selectedAgent?.ip_address ?? '-'}</small>
					<i class="meta-sep" aria-hidden="true"></i>
					<small class="meta-item conn">{isDemoServer ? '데모' : $wsConnected ? 'LIVE' : 'OFFLINE'}</small>
					<i class="meta-sep" aria-hidden="true"></i>
					<small class="meta-item os" title={systemInfo?.os || '-'}>{systemInfo?.os || '-'}</small>
					<i class="meta-sep" aria-hidden="true"></i>
					<small class="meta-item">가동 {formatUptime(systemInfo?.uptime)}</small>
				</div>
			</div>
			<div class="topbar-ctrls">
				<div class="range-inline">
					<span class="range-label">조회 단위</span>
					<TimeRangeSelector value={selectedRange} onChange={changeRange} />
					<small class="poll-label">{rangeConfig.pollLabel}</small>
				</div>
				<i class="ctrl-sep" aria-hidden="true"></i>
				<span class={`status-chip ${historyLoading ? 'loading' : historyError ? 'error' : 'ok'}`}>
					{historyLoading ? '갱신 중' : historyError ? '실패' : formatClock(historyPolledAt)}
				</span>
				<button type="button" class="ctrl-btn" onclick={refreshConnection} title="데이터 새로고침" aria-label="새로고침">
					<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" aria-hidden="true"><path d="M17.65 6.35A7.96 7.96 0 0 0 12 4a8 8 0 1 0 7.74 10h-2.08A6 6 0 1 1 12 6a5.96 5.96 0 0 1 4.22 1.78L13 11h7V4z"/></svg>
					<span>새로고침</span>
				</button>
			</div>
		</section>

		<section class="kpi-gauge-row">
			<div class="kpi-wrap">
				<KpiTileRow
					{total}
					{running}
					{paused}
					{problem}
					{stopped}
					networkRate={totalNetwork}
					imageCount={systemInfo?.docker?.images ?? 0}
					dockerVersion={systemInfo?.docker?.version || '-'}
				/>
			</div>
			<div class="gauge-wrap">
				<ResourceGaugeBar
					{systemInfo}
					systemTrend={systemTrend}
					agentId={isDemoServer ? '' : selectedServerId}
					{accessToken}
					processCount={Number(systemInfo?.processes?.total ?? 0)}
					runningProcesses={Number(systemInfo?.processes?.running ?? 0)}
					loading={historyLoading}
				/>
			</div>
		</section>

		<main class="dashboard">
			<aside class="panel left-rail">
				<StackSidebar stacks={sidebarStacks} />
			</aside>

			<section class="center">
				<div class="panel snapshot">
					<div class="panel-head">
						<div class="panel-title">서버 스냅샷 <InfoTooltip text={`서버 한 대를 3개 카드로 한눈에.\n\n• 통합: 건강 점수 + 컨테이너 상태 + 자원 사용률 + 핫 스택\n• 전력: CPU package · GPU 전력 (W)\n• 온도: CPU package · GPU 온도 (°C)`} placement="bottom-start" /></div>
						<div class="hot-inline" title="CPU + 메모리 + 트래픽을 합산한 부하 상위 3개 컨테이너. 클릭하면 상세가 열립니다.">
							<span class="hot-label"><span class="flame">🔥</span> 부하 TOP 3</span>
							{#each hottest.slice(0, 3) as row (row.id)}
								<button type="button" class={`hot-chip ${row.state === 'dead' || row.state === 'restarting' ? 'problem' : row.state === 'paused' ? 'paused' : row.state === 'running' ? 'running' : 'stopped'}`} onclick={() => { selectedContainer = row.container; }} title={`${row.name}\n스택: ${row.stack}\nCPU ${row.cpu.toFixed(1)}% · MEM ${row.memory.toFixed(1)}%`}>
									<strong>{row.name}</strong>
									<em>CPU {row.cpu.toFixed(0)}·MEM {row.memory.toFixed(0)}</em>
								</button>
							{/each}
						</div>
					</div>
					<div class="snapshot-grid">
						<div class="snap-cell unified">
							<div class="snap-title">서버 통합</div>
							<div class="snap-body unified-body">
								<div class="health-col">
									<HealthRadialGauge score={healthScore} label={healthLabel(health)} tone={healthTone} />
								</div>
								<div class="info-col">
									<div class="ctr-strip">
										{#each stateSegments as seg}
											<span class="ctr-chip" data-tone={seg.label}>
												<span class="ctr-dot" style:background={seg.color}></span>
												<strong>{seg.value}</strong>
												<span class="ctr-label">{seg.label}</span>
											</span>
										{/each}
									</div>
									<div class="res-bars">
										{#each [
											{ label: 'CPU', value: Number(systemInfo?.cpu?.usage ?? 0), color: '#30d5c8' },
											{ label: 'MEM', value: Number(systemInfo?.memory?.usage ?? 0), color: '#60a5fa' },
											{ label: 'DSK', value: Number(systemInfo?.disk?.usage ?? 0), color: '#a78bfa' },
											{ label: 'GPU', value: gpuAverage, color: '#f472b6' },
										] as bar}
											<div class="res-row" title={`${bar.label} ${bar.value.toFixed(1)}%`}>
												<span class="res-label">{bar.label}</span>
												<div class="res-track">
													<div class="res-fill" style:width={`${Math.max(0, Math.min(100, bar.value))}%`} style:background={bar.color}></div>
												</div>
												<span class="res-val">{bar.value.toFixed(0)}%</span>
											</div>
										{/each}
									</div>
								</div>
							</div>
						</div>
						<div class="snap-cell">
							<div class="snap-title">전력</div>
							<div class="snap-body">
								<PowerTempGauge
									title=""
									unit="W"
									cpu={{ label: 'CPU', value: systemInfo?.cpu?.packagePowerW ?? null, max: 150, warn: 95, crit: 130 }}
									gpu={{ label: 'GPU', value: gpuAggregate(systemInfo?.gpu, 'powerDrawW'), max: 350, warn: 220, crit: 300 }}
								/>
							</div>
						</div>
						<div class="snap-cell">
							<div class="snap-title">온도</div>
							<div class="snap-body">
								<PowerTempGauge
									title=""
									unit="°C"
									cpu={{ label: 'CPU', value: systemInfo?.cpu?.tempC ?? null, max: 100, warn: 80, crit: 95 }}
									gpu={{ label: 'GPU', value: gpuAggregate(systemInfo?.gpu, 'temperatureC'), max: 100, warn: 75, crit: 85 }}
								/>
							</div>
						</div>
					</div>
				</div>

				<div class="trend-events-row">
				<div class="panel trend">
					<div class="panel-head">
						<div class="panel-title">스택 평균 추이 <InfoTooltip text={`스택별 평균값을 4개 차트로 비교합니다.\n\n• 차트당 모든 스택의 평균선\n• 상위 5개만 컬러 + 오른쪽 라벨 강조\n• 칩 클릭 = 해당 스택만 표시 (Solo)\n• 스택 사이드바 클릭과 연동`} placement="bottom-start" /></div>
						<small>{(stacks as any[]).length}개 스택 · {rangeConfig.label}</small>
					</div>
					<div class="trend-grid">
						<div class="trend-chart">
							<div class="chart-head">
								<strong>CPU</strong>
								<StackLegendChips entries={cpuLegend} maxChips={0} />
							</div>
							<FleetLineChart
								title={`CPU 평균 / ${rangeConfig.label}`}
								help="모든 스택 CPU 평균."
								labels={trendLabels}
								timestamps={trendTimestampsMs}
								tickInterval={rangeConfig.bucketSeconds * 1000}
								unit="percent"
								series={stackCpuSeries}
								topNames={cpuTopNames}
								soloLabel={view.soloStack}
								rightPadding={0}
								loading={historyLoading}
							/>
						</div>
						<div class="trend-chart">
							<div class="chart-head">
								<strong>메모리</strong>
								<StackLegendChips entries={memoryLegend} maxChips={0} />
							</div>
							<FleetLineChart
								title={`메모리 평균 / ${rangeConfig.label}`}
								help="모든 스택 메모리 평균."
								labels={trendLabels}
								timestamps={trendTimestampsMs}
								tickInterval={rangeConfig.bucketSeconds * 1000}
								unit="percent"
								series={stackMemorySeries}
								topNames={memoryTopNames}
								soloLabel={view.soloStack}
								rightPadding={0}
								loading={historyLoading}
							/>
						</div>
						<div class="trend-chart">
							<div class="chart-head">
								<strong>트래픽</strong>
								<StackLegendChips entries={networkLegend} format={formatRateCompact} maxChips={0} />
							</div>
							<FleetLineChart
								title={`트래픽 평균 / ${rangeConfig.label}`}
								help="모든 스택 네트워크 트래픽."
								labels={trendLabels}
								timestamps={trendTimestampsMs}
								tickInterval={rangeConfig.bucketSeconds * 1000}
								unit="rate"
								series={stackNetworkSeries}
								topNames={networkTopNames}
								soloLabel={view.soloStack}
								rightPadding={0}
								loading={historyLoading}
							/>
						</div>
						<div class="trend-chart">
							<div class="chart-head">
								<strong>GPU</strong>
								{#if hasAnyGpu}
									<StackLegendChips entries={gpuLegend} maxChips={0} />
								{:else}
									<small class="muted gpu-empty">GPU 데이터 없음</small>
								{/if}
							</div>
							{#if hasAnyGpu}
								<FleetLineChart
									title={`GPU 평균 / ${rangeConfig.label}`}
									help="GPU usage 보고가 있는 컨테이너의 스택별 평균. usage=null(측정 불가)은 평균에서 제외."
									labels={trendLabels}
								timestamps={trendTimestampsMs}
								tickInterval={rangeConfig.bucketSeconds * 1000}
									unit="percent"
									series={stackGpuSeries}
									topNames={gpuTopNames}
									soloLabel={view.soloStack}
									rightPadding={0}
									loading={historyLoading}
								/>
							{:else}
								<div class="gpu-empty-body">
									<span>GPU usage 보고가 없습니다.</span>
									<small>GPU 미장착 호스트이거나 컨테이너에서 GPU를 사용하지 않습니다.</small>
								</div>
							{/if}
						</div>
					</div>
				</div>

					<div class="panel events events-side">
						<div class="events-split">
							<section class="load-top-panel">
								<HotContainersList
									rows={hottest}
									limit={3}
									variant="vertical"
									title="부하 TOP 3"
									subtitle="CPU · 메모리 · 트래픽 기준으로 지금 가장 뜨거운 컨테이너"
									badge={`${Math.min(3, hottest.length)} / ${hottest.length || 0}`}
									helperText="CPU, 메모리, 네트워크 사용량을 합산해 가장 바쁜 컨테이너 순으로 보여줍니다. 클릭하면 상세 모달이 열립니다."
									panelClass="load-top-hero"
									showRank={true}
									compactMetrics={true}
									onSelect={(container) => { selectedContainer = container; }}
								/>
							</section>

							<section class="events-log-panel">
								<EventLogStrip
									events={eventRows}
									onSelect={(container) => { selectedContainer = container; }}
								/>
							</section>
						</div>
					</div>
				</div>
			</section>

			<aside class="panel right-rail">
				<ContainersGridPanel
					stacks={containersGrouped}
					onSelectContainer={(container) => { selectedContainer = container; }}
				/>
			</aside>
		</main>
	</div>
{/if}

<ContainerDetailModal
	container={selectedContainer}
	agentId={selectedServerId}
	{accessToken}
	onClose={() => { selectedContainer = null; }}
	onStateChange={refreshConnection}
/>

<style>
	:global(html),
	:global(body) {
		overflow: hidden;
		height: 100vh;
		max-height: 100vh;
	}

	.auth-page {
		min-height: 100vh;
		background: var(--bg-base);
		color: var(--text-primary);
	}

	.shell {
		height: 100vh;
		max-height: 100vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		background: var(--bg-base);
		color: var(--text-primary);
	}

	.auth-page {
		display: grid;
		place-items: center;
		padding: 24px;
	}

	.auth-card {
		width: min(430px, 100%);
		padding: 34px;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--bg-card);
		display: grid;
		gap: 14px;
	}

	.auth-card img { height: 36px; width: fit-content; }
	.auth-card h1 { margin: 0; }
	.auth-card p {
		margin: 0;
		color: var(--text-muted);
		font-size: 13px;
		line-height: 1.45;
	}

	label {
		display: grid;
		gap: 6px;
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 700;
	}

	input, select {
		height: 34px;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
		color: var(--text-primary);
		padding: 0 10px;
		font: inherit;
	}

	button { font: inherit; }

	.auth-card button,
	.topbar-ctrls button,
	.server-card {
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-card);
		color: var(--text-primary);
		cursor: pointer;
	}

	.auth-card button {
		height: 40px;
		background: var(--accent);
		color: var(--bg-base);
		font-weight: 800;
	}

	.auth-error {
		color: #fca5a5;
		font-size: 12px;
	}

	.server-picker {
		max-width: 980px;
		margin: 0 auto;
		padding: 48px 20px;
	}

	.server-picker h1 { margin: 0; }
	.server-picker p {
		margin: 0;
		color: var(--text-muted);
		font-size: 13px;
		line-height: 1.45;
	}

	.server-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 10px;
		margin-top: 18px;
	}

	.server-card {
		display: grid;
		gap: 4px;
		padding: 16px;
		text-align: left;
	}

	.server-card span, .server-card small {
		color: var(--text-muted);
	}

	.empty-state {
		margin-top: 20px;
		padding: 18px;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--bg-card);
		color: var(--text-muted);
	}

	.sub-topbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		padding: 8px 16px;
		border-bottom: 1px solid var(--border);
		background: var(--bg-card);
		flex: 0 0 auto;
		flex-wrap: wrap;
		min-height: 46px;
	}

	.server-id {
		display: flex;
		align-items: center;
		gap: 10px;
		min-width: 0;
		flex-wrap: wrap;
	}

	.server-meta {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		flex-wrap: nowrap;
		overflow: hidden;
	}

	.meta-item {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
		white-space: nowrap;
		max-width: 280px;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.meta-item.os {
		max-width: 320px;
	}

	.meta-item.conn {
		color: #34d399;
		letter-spacing: 0.04em;
	}

	.meta-sep {
		display: inline-block;
		width: 1px;
		height: 12px;
		background: rgba(100, 116, 139, 0.4);
		flex: 0 0 auto;
	}

	.hostname {
		color: var(--text-primary);
		font-size: 15px;
		font-weight: 900;
		max-width: 300px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		letter-spacing: 0.02em;
	}

	.server-select {
		appearance: none;
		-webkit-appearance: none;
		background: rgba(15, 23, 42, 0.6) url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%2330d5c8'><path d='M7 10l5 5 5-5z'/></svg>") no-repeat right 8px center;
		background-size: 16px;
		border: 1px solid rgba(48, 213, 200, 0.4);
		border-radius: 8px;
		color: var(--text-primary);
		font-size: 15px;
		font-weight: 900;
		letter-spacing: 0.02em;
		padding: 4px 30px 4px 12px;
		height: 30px;
		max-width: 300px;
		cursor: pointer;
		transition: border-color 0.15s ease, background-color 0.15s ease;
	}

	.server-select:hover {
		border-color: rgba(48, 213, 200, 0.7);
		background-color: rgba(48, 213, 200, 0.08);
	}

	.server-select:focus {
		outline: none;
		border-color: rgba(48, 213, 200, 0.8);
		box-shadow: 0 0 0 2px rgba(48, 213, 200, 0.18);
	}

	.server-id small {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
	}

	.health-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: #64748b;
	}
	.health-dot.healthy { background: #34d399; box-shadow: 0 0 10px rgba(52, 211, 153, 0.65); }
	.health-dot.warning { background: #fbbf24; box-shadow: 0 0 10px rgba(251, 191, 36, 0.65); }
	.health-dot.critical { background: #f87171; box-shadow: 0 0 10px rgba(248, 113, 113, 0.65); }
	.health-dot.offline { background: #64748b; }

	.status-pill {
		display: inline-flex;
		padding: 2px 8px;
		border-radius: 999px;
		font-size: 10px;
		font-weight: 800;
	}
	.status-pill.healthy {
		background: rgba(52, 211, 153, 0.16);
		color: #34d399;
		border: 1px solid rgba(52, 211, 153, 0.32);
	}
	.status-pill.warning {
		background: rgba(251, 191, 36, 0.16);
		color: #fbbf24;
		border: 1px solid rgba(251, 191, 36, 0.32);
	}
	.status-pill.critical {
		background: rgba(248, 113, 113, 0.16);
		color: #f87171;
		border: 1px solid rgba(248, 113, 113, 0.4);
	}
	.status-pill.offline {
		background: rgba(100, 116, 139, 0.16);
		color: #94a3b8;
		border: 1px solid rgba(100, 116, 139, 0.32);
	}

	.topbar-ctrls {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	.topbar-ctrls select {
		min-width: 180px;
		height: 30px;
	}

	.range-inline {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		color: var(--text-secondary);
		font-size: 11px;
		font-weight: 700;
	}

	.range-label {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.poll-label {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 24px;
		min-width: 110px;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		line-height: 1;
		padding: 0 10px;
		border: 1px dashed rgba(100, 116, 139, 0.32);
		border-radius: 999px;
		white-space: nowrap;
		flex: 0 0 auto;
	}

	.ctrl-sep {
		display: inline-block;
		width: 1px;
		height: 18px;
		background: rgba(100, 116, 139, 0.32);
		flex: 0 0 auto;
	}

	.status-chip {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 24px;
		min-width: 90px;
		padding: 0 10px;
		border-radius: 999px;
		background: rgba(52, 211, 153, 0.16);
		color: #34d399;
		font-weight: 800;
		font-size: 10px;
		line-height: 1;
		letter-spacing: 0.04em;
		border: 1px solid rgba(52, 211, 153, 0.25);
		white-space: nowrap;
		flex: 0 0 auto;
	}

	.status-chip.loading { background: rgba(96, 165, 250, 0.16); color: #60a5fa; border-color: rgba(96, 165, 250, 0.3); }
	.status-chip.error { background: rgba(248, 113, 113, 0.18); color: #f87171; border-color: rgba(248, 113, 113, 0.35); }

	.ctrl-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		height: 30px;
		padding: 0 12px;
		border: 1px solid rgba(100, 116, 139, 0.35);
		border-radius: 8px;
		background: rgba(15, 23, 42, 0.6);
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 800;
		letter-spacing: 0.02em;
		line-height: 1;
		cursor: pointer;
		white-space: nowrap;
		transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
	}

	.ctrl-btn:hover {
		border-color: rgba(48, 213, 200, 0.5);
		background: rgba(48, 213, 200, 0.1);
	}

	.ctrl-btn.primary {
		border-color: rgba(48, 213, 200, 0.45);
		background: rgba(48, 213, 200, 0.16);
		color: #30d5c8;
	}

	.ctrl-btn.primary:hover {
		background: rgba(48, 213, 200, 0.26);
		border-color: rgba(48, 213, 200, 0.7);
	}

	.ctrl-btn svg {
		flex: 0 0 auto;
		display: block;
		transform: translateY(1px);
	}

	.ctrl-btn span {
		line-height: 1;
		display: inline-block;
	}

	.kpi-gauge-row {
		display: flex;
		flex-direction: column;
		gap: 7px;
		padding: 8px 14px 0;
		flex: 0 0 auto;
	}

	.kpi-wrap,
	.gauge-wrap {
		min-width: 0;
	}

	.dashboard {
		flex: 1 1 auto;
		min-height: 0;
		display: grid;
		grid-template-columns: minmax(280px, 320px) minmax(0, 1fr) minmax(400px, 500px);
		gap: 10px;
		padding: 10px 14px 12px;
		align-items: stretch;
		overflow: hidden;
		/* 전체 페이지 글자/요소 가독성 살짝 키움. Chromium 의 zoom 은 layout 도
		   같이 확대돼 click 좌표나 grid 비율이 그대로 유지된다. */
		zoom: 1.06;
	}

	.panel {
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--bg-card);
		padding: 12px 14px;
		min-width: 0;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: 10px;
		overflow: hidden;
	}

	.panel-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		min-height: 22px;
		flex-wrap: nowrap;
		overflow: hidden;
	}

	.panel-head > * {
		min-width: 0;
	}

	.panel-head .panel-title {
		flex: 0 0 auto;
		max-width: 50%;
	}

	.panel-title {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 900;
		letter-spacing: 0.01em;
	}

	.panel-head small,
	.panel-title + small {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
	}

	.sub-title {
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 800;
	}

	.left-rail,
	.right-rail {
		min-height: 0;
		max-height: 100%;
		overflow: hidden;
	}

	.center {
		display: grid;
		/* snapshot 은 max-height:200px 에 자체 cap. 나머지는 trend-events 가 모두 차지. */
		grid-template-rows: auto minmax(0, 1fr);
		gap: 8px;
		min-width: 0;
		min-height: 0;
		overflow: hidden;
	}

	.trend-events-row {
		display: grid;
		grid-template-columns: 3fr minmax(220px, 1fr);
		gap: 8px;
		min-height: 0;
		min-width: 0;
		overflow: hidden;
	}

	.events-side {
		padding: 8px 11px;
		min-height: 0;
		min-width: 0;
		overflow: hidden;
	}

	.events-split {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 8px;
		min-height: 0;
		height: 100%;
	}

	.load-top-panel,
	.events-log-panel {
		min-height: 0;
		min-width: 0;
		overflow: hidden;
		display: flex;
	}

	.load-top-panel :global(.hot-panel) {
		width: 100%;
	}

	.events-log-panel :global(.events) {
		width: 100%;
	}

	.panel {
		padding: 8px 11px;
	}

	.snapshot {
		gap: 6px;
		min-height: 0;
		max-height: 200px;
		overflow: hidden;
	}

	.snapshot > .panel-head {
		min-height: 30px;
	}

	.hot-inline {
		display: flex;
		align-items: center;
		gap: 5px;
		flex-wrap: nowrap;
		min-width: 0;
		max-width: 100%;
		min-height: 26px;
		overflow: hidden;
	}

	.hot-label {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 3px 8px;
		border-radius: 999px;
		background: rgba(248, 113, 113, 0.14);
		border: 1px solid rgba(248, 113, 113, 0.3);
		color: #f87171;
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.03em;
		flex: 0 0 auto;
	}

	.flame {
		font-size: 12px;
		line-height: 1;
	}

	.hot-chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 9px 2px 7px;
		border-radius: 999px;
		border: 1px solid rgba(100, 116, 139, 0.28);
		background: rgba(15, 23, 42, 0.55);
		color: var(--text-primary);
		font-size: 10px;
		font-weight: 800;
		cursor: pointer;
		min-width: 0;
		flex: 1 1 0;
		max-width: 150px;
		overflow: hidden;
		white-space: nowrap;
	}

	.hot-chip:hover {
		border-color: rgba(48, 213, 200, 0.5);
	}

	.hot-chip.running { border-left: 3px solid #34d399; }
	.hot-chip.paused { border-left: 3px solid #fbbf24; }
	.hot-chip.problem { border-left: 3px solid #f87171; }
	.hot-chip.stopped { border-left: 3px solid #94a3b8; }

	.hot-chip strong {
		font-size: 10px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 90px;
	}

	.hot-chip em {
		font-style: normal;
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 800;
	}

	.snapshot-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr) minmax(0, 1fr);
		grid-template-rows: minmax(0, 1fr);
		gap: 8px;
		min-height: 0;
		flex: 1;
	}

	.snap-cell.unified .unified-body {
		display: grid;
		grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
		gap: 10px;
		min-height: 0;
		height: 100%;
	}
	.health-col {
		display: flex;
		align-items: center;
		justify-content: center;
		min-width: 0;
	}
	.info-col {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 8px;
		min-width: 0;
		min-height: 0;
	}
	.ctr-strip {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.ctr-chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 6px;
		background: rgba(15, 23, 42, 0.6);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: 4px;
		font-size: 10px;
		font-weight: 700;
		color: var(--text-secondary);
	}
	.ctr-chip strong {
		color: var(--text-primary);
		font-size: 11px;
		font-variant-numeric: tabular-nums;
	}
	.ctr-dot {
		display: inline-block;
		width: 6px;
		height: 6px;
		border-radius: 50%;
	}
	.ctr-label {
		font-size: 9.5px;
		letter-spacing: 0.2px;
	}
	.res-bars {
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.res-row {
		display: grid;
		grid-template-columns: 26px minmax(0, 1fr) 32px;
		align-items: center;
		gap: 6px;
		font-size: 10px;
		font-weight: 800;
		color: var(--text-muted);
	}
	.res-label {
		letter-spacing: 0.3px;
	}
	.res-track {
		height: 6px;
		background: rgba(100, 116, 139, 0.18);
		border-radius: 3px;
		overflow: hidden;
	}
	.res-fill {
		height: 100%;
		border-radius: 3px;
		transition: width 0.4s ease;
	}
	.res-val {
		text-align: right;
		font-variant-numeric: tabular-nums;
		color: var(--text-primary);
	}
	.snap-cell {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 4px;
		padding: 7px 9px 9px;
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-radius: 8px;
		background: rgba(15, 23, 42, 0.55);
		min-width: 0;
		min-height: 0;
		overflow: hidden;
	}

	.snap-title {
		color: var(--text-primary);
		font-size: 11px;
		font-weight: 850;
		letter-spacing: 0.02em;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.snap-body {
		position: relative;
		width: 100%;
		height: 100%;
		min-height: 0;
		min-width: 0;
	}

	.trend {
		gap: 8px;
		min-height: 0;
		min-width: 0;
		overflow: hidden;
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
	}

	.trend-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		grid-template-rows: repeat(2, minmax(0, 1fr));
		gap: 8px;
		min-height: 0;
		flex: 1;
	}

	.trend-chart {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 6px;
		padding: 8px 10px 9px;
		border: 1px solid rgba(100, 116, 139, 0.14);
		border-radius: 9px;
		background: rgba(15, 23, 42, 0.42);
		min-height: 0;
		min-width: 0;
		overflow: hidden;
	}

	.chart-head {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: center;
		gap: 8px;
		min-height: 24px;
		overflow: hidden;
	}

	.chart-head strong {
		font-size: 12px;
		font-weight: 900;
		letter-spacing: 0.02em;
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 2px 10px;
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.14);
		border: 1px solid rgba(48, 213, 200, 0.32);
		color: #30d5c8;
		flex: 0 0 auto;
		white-space: nowrap;
	}

	.chart-head .muted,
	.chart-head .chart-sub {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		min-width: 0;
	}

	.gpu-empty {
		justify-self: end;
	}

	.gpu-empty-body {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 4px;
		min-height: 0;
		padding: 12px;
		border: 1px dashed rgba(100, 116, 139, 0.28);
		border-radius: 8px;
		background: rgba(15, 23, 42, 0.45);
	}

	.gpu-empty-body span {
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 800;
	}

	.gpu-empty-body small {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		text-align: center;
	}

	.trend-chart :global(.chart) {
		padding: 0;
		background: transparent;
		border: none;
		min-height: 0;
		height: 100%;
	}

	.trend-chart :global(.chart-title) {
		display: none;
	}

	.trend-chart :global(.canvas-wrap) {
		height: 100%;
		min-height: 0;
		flex: 1;
	}

	.chart-host {
		width: 100%;
		min-height: 0;
		min-width: 0;
		position: relative;
	}

	.events {
		gap: 6px;
	}

	@media (max-width: 1600px) {
		.dashboard {
			grid-template-columns: minmax(260px, 290px) minmax(0, 1fr) minmax(360px, 440px);
		}
	}

	@media (max-width: 1400px) {
		.dashboard {
			grid-template-columns: minmax(240px, 270px) minmax(0, 1fr) minmax(320px, 400px);
			gap: 8px;
		}

		.snapshot-grid {
			/* 3-cell (unified · power · temp) 비율 유지. 좁아진 폭에서도 unified
			   가 dual-gauge 두 개 합한 만큼 차지하게 1.6 : 1 : 1. */
			grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr) minmax(0, 1fr);
		}
	}

	@media (max-width: 1200px) {
		:global(html),
		:global(body) {
			overflow: auto;
			height: auto;
		}

		.shell {
			height: auto;
			max-height: none;
			overflow: visible;
		}

		.dashboard {
			grid-template-columns: 1fr;
			overflow: visible;
		}

		.left-rail,
		.right-rail {
			max-height: none;
			overflow: visible;
		}

		.center {
			grid-template-rows: auto;
			overflow: visible;
		}

		.events-split {
			grid-template-rows: auto auto;
		}

		.snapshot-grid {
			/* 매우 좁은 화면 (≤1200px) — 3-cell 을 세로 stack. 가로 grid
			   대신 한 줄씩 쌓아 가독성 우선. */
			grid-template-columns: minmax(0, 1fr);
			grid-template-rows: repeat(3, minmax(160px, auto));
		}

		.trend-grid {
			grid-template-rows: repeat(4, minmax(160px, auto));
		}

		.bottom-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
