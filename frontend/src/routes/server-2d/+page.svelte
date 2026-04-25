<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import type { Plugin } from 'chart.js';
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
	import { connectGlobal, disconnectGlobal, seedActiveAgents } from '$lib/stores/global-events';
	import AdminHeader from '$lib/components/AdminHeader.svelte';
	import ContainerDetailModal from '$lib/components/ContainerDetailModal.svelte';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import TimeRangeSelector from '$lib/components/fleet/TimeRangeSelector.svelte';
	import FleetLineChart from '$lib/components/fleet/FleetLineChart.svelte';
	import ResourceGaugeBar from '$lib/components/server2d/ResourceGaugeBar.svelte';
	import KpiTileRow from '$lib/components/server2d/KpiTileRow.svelte';
	import HotContainersList from '$lib/components/server2d/HotContainersList.svelte';
	import StackSidebar from '$lib/components/server2d/StackSidebar.svelte';
	import ContainersGridPanel from '$lib/components/server2d/ContainersGridPanel.svelte';
	import StackLegendChips from '$lib/components/server2d/StackLegendChips.svelte';
	import DonutChart from '$lib/components/server2d/DonutChart.svelte';
	import HealthRadialGauge from '$lib/components/server2d/HealthRadialGauge.svelte';
	import ResourceRadarChart from '$lib/components/server2d/ResourceRadarChart.svelte';
	import StackBubbleChart from '$lib/components/server2d/StackBubbleChart.svelte';
	import EventLogStrip from '$lib/components/server2d/EventLogStrip.svelte';
	import { rightEdgeLabelsPlugin } from '$lib/charts/rightEdgeLabelsPlugin';
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

	type Agent = { id: string; hostname: string; ip_address: string; container_count?: number };
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
		gpu: number;
	};
	type ContainerTrend = {
		cpu: number[];
		memory: number[];
		network: number[];
		cpuAvg: number;
		memoryAvg: number;
		networkAvg: number;
		samples: number;
	};
	type StackTrend = {
		cpu: number[];
		memory: number[];
		network: number[];
		disk: number[];
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
	let historyModel = $derived(buildHistoryModel(containerHistoryRows, rows, selectedRange, historyAnchorMs));
	let trendLabels = $derived(historyModel.buckets.map((bucket) => formatRangeTick(bucket, selectedRange)));
	let systemTrend = $derived(buildSystemTrend(systemHistoryRows, selectedRange, historyAnchorMs));

	let stackCpuSeries = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stack.name);
			return {
				label: stack.name,
				values: trend?.cpu ?? Array.from({ length: historyModel.buckets.length }, () => 0),
				color: stack.color,
			};
		}),
	);
	let stackMemorySeries = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stack.name);
			return {
				label: stack.name,
				values: trend?.memory ?? Array.from({ length: historyModel.buckets.length }, () => 0),
				color: stack.color,
			};
		}),
	);
	let stackNetworkSeries = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stack.name);
			return {
				label: stack.name,
				values: trend?.network ?? Array.from({ length: historyModel.buckets.length }, () => 0),
				color: stack.color,
			};
		}),
	);
	let stackDiskSeries = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stack.name);
			return {
				label: stack.name,
				values: trend?.disk ?? Array.from({ length: historyModel.buckets.length }, () => 0),
				color: stack.color,
			};
		}),
	);
	let cpuTopNames = $derived(topNamesBySeries(stackCpuSeries));
	let memoryTopNames = $derived(topNamesBySeries(stackMemorySeries));
	let networkTopNames = $derived(topNamesBySeries(stackNetworkSeries));
	let diskTopNames = $derived(topNamesBySeries(stackDiskSeries));
	let cpuLegend = $derived(legendFromSeries(stackCpuSeries));
	let memoryLegend = $derived(legendFromSeries(stackMemorySeries));
	let networkLegend = $derived(legendFromSeries(stackNetworkSeries));
	let diskLegend = $derived(legendFromSeries(stackDiskSeries));

	let sidebarStacks = $derived(
		(stacks as any[]).map((stack: any) => {
			const trend = historyModel.stackMap.get(stack.name);
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
			return {
				name: stack.name,
				color: stack.color,
				running: stack.stats.running,
				total: stack.stats.total,
				problem: stackRows.filter((row) => row.state === 'dead' || row.state === 'restarting').length,
				cpuAvg,
				memoryAvg,
				networkAvg,
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
					return {
						id: row.id,
						name: row.name,
						state: row.state,
						cpu: trend?.cpuAvg ?? row.cpu,
						memory: trend?.memoryAvg ?? row.memory,
						network: trend?.networkAvg ?? row.network,
						gpu: row.gpu,
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
		return events
			.sort((a, b) => {
				const weight = (sev: string) => (sev === 'critical' ? 0 : sev === 'warn' ? 1 : 2);
				return weight(a.severity) - weight(b.severity);
			})
			.slice(0, 50);
	});

	const trendPlugins: Plugin[] = [rightEdgeLabelsPlugin];

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
			await loadAgents();
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
	}

	async function loadAgents() {
		agentsLoading = true;
		try {
			let liveAgents: Agent[] = [];
			try {
				const response = await fetch(`${base}/api/agents/?status=approved&active=true&page_size=200&ordering=hostname`, {
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
			agents = [...liveAgents, DEMO_AGENT];
			seedActiveAgents(liveAgents.map((agent: Agent) => agent.id));
			const saved = browser ? localStorage.getItem('hc_selected_server') : '';
			const preferred = selectedServerId && agents.some((agent) => agent.id === selectedServerId)
				? selectedServerId
				: saved && agents.some((agent) => agent.id === saved)
					? saved
					: agents[0]?.id;
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
		goto(`${base}/`);
	}

	async function fetchPagedRows<T>(endpoint: string, params: URLSearchParams, maxRows: number): Promise<T[]> {
		const rows: T[] = [];
		let page = 1;

		while (rows.length < maxRows) {
			const query = new URLSearchParams(params);
			query.set('page', String(page));
			query.set('page_size', '1000');
			const response = await fetch(`${base}${endpoint}?${query.toString()}`, {
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
			const results = Array.isArray(payload) ? payload : payload?.results ?? [];
			rows.push(...results);
			if (Array.isArray(payload) || !payload?.next || results.length === 0) break;
			page += 1;
		}

		return rows.slice(0, maxRows);
	}

	async function loadHistoricalData() {
		if (!selectedServerId) return;
		const currentSeq = ++historyLoadSeq;
		historyLoading = true;
		historyError = '';
		const anchor = Date.now();
		const from = new Date(anchor - rangeConfig.windowMs).toISOString();
		const to = new Date(anchor).toISOString();

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

			const systemParams = new URLSearchParams({
				agent: selectedServerId,
				from_time: from,
				to_time: to,
				ordering: 'recorded_at',
			});
			const containerParams = new URLSearchParams({
				agent: selectedServerId,
				from_time: from,
				to_time: to,
				ordering: 'recorded_at',
			});

			const [systemRows, containerRows] = await Promise.all([
				fetchPagedRows<SystemHistoryRow>('/api/metrics/system/', systemParams, rangeConfig.maxRawRows),
				fetchPagedRows<ContainerHistoryRow>('/api/metrics/containers/', containerParams, rangeConfig.maxRawRows),
			]);

			if (currentSeq !== historyLoadSeq) return;
			systemHistoryRows = systemRows;
			containerHistoryRows = containerRows;
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
		return Number(metric?.cpu?.usage ?? metric?.cpu_usage ?? metric?.cpu ?? 0);
	}

	function metricMemory(metric: any): number {
		return Number(metric?.memory?.percent ?? metric?.memory_percent ?? metric?.memory?.usage_percent ?? 0);
	}

	function metricNetwork(metric: any): number {
		const stats = Array.isArray(metric?.network_stats) ? metric.network_stats : [];
		if (stats.length) {
			return stats.reduce((sum: number, stat: any) => sum + Number(stat.rx_rate_bps ?? 0) + Number(stat.tx_rate_bps ?? 0), 0);
		}
		return Number(metric?.network?.rx_rate_bps ?? 0) + Number(metric?.network?.tx_rate_bps ?? 0);
	}

	function metricGpu(metric: any): number {
		return Number(metric?.gpu?.usage ?? metric?.gpu_usage ?? 0);
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

	function buildHistoryModel(historyRows: ContainerHistoryRow[], currentRows: Row[], range: MonitoringRange, anchorMs: number): HistoryModel {
		const config = MONITORING_RANGE_CONFIG[range];
		const buckets = buildRangeBuckets(range, anchorMs);
		const bucketIndex = new Map(buckets.map((bucket, index) => [bucket, index]));
		const rowByHistoryId = new Map<string, Row>();

		for (const row of currentRows) {
			rowByHistoryId.set(row.id, row);
			rowByHistoryId.set(row.id.slice(0, 12), row);
			if (row.container.shortId) rowByHistoryId.set(row.container.shortId, row);
		}

		const perContainer = new Map<string, { row: Row; cpuBuckets: number[][]; memoryBuckets: number[][]; networkBuckets: number[][]; diskBuckets: number[][]; samples: number }>();
		for (const row of currentRows) {
			perContainer.set(row.id, {
				row,
				cpuBuckets: Array.from({ length: buckets.length }, () => []),
				memoryBuckets: Array.from({ length: buckets.length }, () => []),
				networkBuckets: Array.from({ length: buckets.length }, () => []),
				diskBuckets: Array.from({ length: buckets.length }, () => []),
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
			entry.samples += 1;
			previousByContainer.set(item.container_id, { rx, tx, dr, dw, at: ts });
		}

		const containerMap = new Map<string, ContainerTrend>();
		const stackTemp = new Map<string, { cpu: number[][]; memory: number[][]; network: number[][]; disk: number[][]; count: number; running: number }>();

		for (const row of currentRows) {
			const entry = perContainer.get(row.id);
			const cpuSeries = fillBuckets(entry?.cpuBuckets ?? [], row.cpu);
			const memorySeries = fillBuckets(entry?.memoryBuckets ?? [], row.memory);
			const networkSeries = fillBuckets(entry?.networkBuckets ?? [], row.network);
			const diskSeries = fillBuckets(entry?.diskBuckets ?? [], 0);
			const cpuAvg = avg(nonZero(cpuSeries, row.cpu));
			const memoryAvg = avg(nonZero(memorySeries, row.memory));
			const networkAvg = avg(nonZero(networkSeries, row.network));

			containerMap.set(row.id, {
				cpu: cpuSeries,
				memory: memorySeries,
				network: networkSeries,
				cpuAvg: cpuAvg || row.cpu,
				memoryAvg: memoryAvg || row.memory,
				networkAvg: networkAvg || row.network,
				samples: entry?.samples ?? 0,
			});

			const stackEntry = stackTemp.get(row.stack) ?? {
				cpu: Array.from({ length: buckets.length }, () => []),
				memory: Array.from({ length: buckets.length }, () => []),
				network: Array.from({ length: buckets.length }, () => []),
				disk: Array.from({ length: buckets.length }, () => []),
				count: 0,
				running: 0,
			};
			for (let index = 0; index < buckets.length; index += 1) {
				stackEntry.cpu[index].push(cpuSeries[index] || 0);
				stackEntry.memory[index].push(memorySeries[index] || 0);
				stackEntry.network[index].push(networkSeries[index] || 0);
				stackEntry.disk[index].push(diskSeries[index] || 0);
			}
			stackEntry.count += 1;
			if (row.state === 'running') stackEntry.running += 1;
			stackTemp.set(row.stack, stackEntry);
		}

		const stackMap = new Map<string, StackTrend>();
		for (const [name, entry] of stackTemp) {
			stackMap.set(name, {
				cpu: entry.cpu.map((values) => avg(values)),
				memory: entry.memory.map((values) => avg(values)),
				network: entry.network.map((values) => avg(values)),
				disk: entry.disk.map((values) => avg(values)),
				count: entry.count,
				running: entry.running,
			});
		}

		return { containerMap, stackMap, buckets };
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

		return {
			cpu: cpuSeries,
			memory: memSeries,
			disk: diskSeries,
			gpu: gpuSeries,
			network: netSeries,
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

{#if !isLoggedIn}
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
{:else if !selectedServerId}
	<div class="shell">
		<AdminHeader totalAgents={agents.length} username={currentUsername} onLogout={doLogout} />
		<main class="server-picker">
			<h1>서버 선택</h1>
			<p>이 화면은 한 번에 서버 하나를 깊게 보는 2D 관제 페이지입니다. 분석할 서버를 선택하세요.</p>
			{#if agentsLoading}
				<div class="empty-state">서버 목록을 불러오는 중입니다.</div>
			{:else if agents.length === 0}
				<div class="empty-state">연결된 서버가 없습니다.</div>
			{:else}
				<div class="server-grid">
					{#each agents as agent (agent.id)}
						<button type="button" class="server-card" onclick={() => selectServer(agent.id)}>
							<strong>{agent.hostname}</strong>
							<span>{agent.ip_address}</span>
							<small>컨테이너 {agent.container_count ?? 0}개</small>
						</button>
					{/each}
				</div>
			{/if}
		</main>
	</div>
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
					<span class="range-label">추이 범위</span>
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
				<button type="button" class="ctrl-btn primary" onclick={open3d} title="3D 상세 모니터링" aria-label="3D 상세">
					<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" aria-hidden="true"><path d="M12 2 2 7v10l10 5 10-5V7zm0 2.18 7.55 3.78L12 11.74 4.45 7.96zM4 9.5l7 3.5v7.34L4 16.66zm9 10.84V13l7-3.5v7.16z"/></svg>
					<span>3D 상세</span>
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
						<div class="panel-title">서버 스냅샷 <InfoTooltip text={`서버 한 대를 4개 그래프로 한눈에.\n\n• 도넛: 컨테이너 상태 분포\n• 원형 게이지: 종합 건강 점수\n• 레이더: 자원 6축 밸런스\n• 버블: 스택 CPU × 메모리 부하 (크기 = 컨테이너 수)`} placement="bottom-start" /></div>
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
						<div class="snap-cell">
							<div class="snap-title">컨테이너 상태</div>
							<div class="snap-body">
								<DonutChart
									segments={stateSegments}
									centerLabel="전체"
									centerValue={String(total)}
								/>
							</div>
						</div>
						<div class="snap-cell">
							<div class="snap-title">종합 건강 점수</div>
							<div class="snap-body">
								<HealthRadialGauge score={healthScore} label={healthLabel(health)} tone={healthTone} />
							</div>
						</div>
						<div class="snap-cell">
							<div class="snap-title">자원 밸런스</div>
							<div class="snap-body">
								<ResourceRadarChart axes={radarAxes} primaryColor="#30d5c8" />
							</div>
						</div>
						<div class="snap-cell">
							<div class="snap-title">스택 부하 (CPU × MEM)</div>
							<div class="snap-body">
								<StackBubbleChart stacks={bubbleStacks} />
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
								<StackLegendChips entries={cpuLegend} maxChips={5} />
							</div>
							<FleetLineChart
								title={`CPU 평균 / ${rangeConfig.label}`}
								help="모든 스택 CPU 평균."
								labels={trendLabels}
								unit="percent"
								series={stackCpuSeries}
								topNames={cpuTopNames}
								soloLabel={view.soloStack}
								extraPlugins={[]}
								rightPadding={0}
							/>
						</div>
						<div class="trend-chart">
							<div class="chart-head">
								<strong>메모리</strong>
								<StackLegendChips entries={memoryLegend} maxChips={5} />
							</div>
							<FleetLineChart
								title={`메모리 평균 / ${rangeConfig.label}`}
								help="모든 스택 메모리 평균."
								labels={trendLabels}
								unit="percent"
								series={stackMemorySeries}
								topNames={memoryTopNames}
								soloLabel={view.soloStack}
								extraPlugins={[]}
								rightPadding={0}
							/>
						</div>
						<div class="trend-chart">
							<div class="chart-head">
								<strong>트래픽</strong>
								<StackLegendChips entries={networkLegend} format={formatRateCompact} maxChips={5} />
							</div>
							<FleetLineChart
								title={`트래픽 평균 / ${rangeConfig.label}`}
								help="모든 스택 네트워크 트래픽."
								labels={trendLabels}
								unit="rate"
								series={stackNetworkSeries}
								topNames={networkTopNames}
								soloLabel={view.soloStack}
								extraPlugins={[]}
								rightPadding={0}
							/>
						</div>
						<div class="trend-chart">
							<div class="chart-head">
								<strong>디스크 I/O</strong>
								<StackLegendChips entries={diskLegend} format={formatRateCompact} maxChips={5} />
							</div>
							<FleetLineChart
								title={`디스크 I/O / ${rangeConfig.label}`}
								help="모든 스택의 디스크 읽기·쓰기 합계 평균."
								labels={trendLabels}
								unit="rate"
								series={stackDiskSeries}
								topNames={diskTopNames}
								soloLabel={view.soloStack}
								extraPlugins={[]}
								rightPadding={0}
							/>
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
		height: 24px;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		line-height: 1;
		padding: 0 10px;
		border: 1px dashed rgba(100, 116, 139, 0.32);
		border-radius: 999px;
		white-space: nowrap;
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
		height: 24px;
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
		grid-template-rows: minmax(0, 0.85fr) minmax(0, 1.85fr);
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
		overflow: hidden;
	}

	.hot-inline {
		display: flex;
		align-items: center;
		gap: 5px;
		flex-wrap: nowrap;
		min-width: 0;
		max-width: 100%;
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
		grid-template-columns: minmax(0, 0.78fr) minmax(0, 0.78fr) minmax(0, 0.95fr) minmax(0, 1.85fr);
		grid-template-rows: minmax(0, 1fr);
		gap: 8px;
		min-height: 0;
		flex: 1;
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
		align-items: start;
		gap: 8px;
		min-height: 24px;
	}

	.chart-head strong {
		font-size: 12px;
		font-weight: 900;
		letter-spacing: 0.02em;
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 2px 10px;
		margin-top: 2px;
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
			grid-template-columns: repeat(4, minmax(0, 1fr));
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
			grid-template-columns: repeat(2, minmax(0, 1fr));
			grid-template-rows: repeat(2, minmax(200px, 1fr));
		}

		.trend-grid {
			grid-template-rows: repeat(4, minmax(160px, auto));
		}

		.bottom-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
