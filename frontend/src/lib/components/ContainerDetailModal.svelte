<script lang="ts">
	import { onMount, onDestroy, untrack } from 'svelte';
	import { base } from '$app/paths';
	import { sendCommand, containerMetricsStore } from '$lib/stores/ws-store';
	import { adaptContainerInspect } from '$lib/utils/data-adapter';
	import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, Legend } from 'chart.js';
	import MetricTrendChart from './MetricTrendChart.svelte';
	import InfoTooltip from './InfoTooltip.svelte';

	Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, Legend);

	interface Container {
		id: string;
		shortId: string;
		names: string[];
		image: string;
		state: string;
		status: string;
		labels: any;
	}

	const MAX_HISTORY = 30;

	let {
		container = null,
		agentId = '',
		accessToken = '',
		onClose = () => {},
		onStateChange = () => {},
	}: {
		container: Container | null;
		agentId?: string;
		accessToken?: string;
		onClose: () => void;
		onStateChange: () => void;
	} = $props();

	let activeTab = $state<'info' | 'metrics' | 'logs'>('info');

	// Loading states
	let loadingInfo = $state(true);
	let loadingLogs = $state(true);
	let controlLoading = $state('');
	let errorMsg = $state('');

	// Info data (= inspect result from Docker API)
	let details: any = $state(null);

	// Metrics data
	let metricsData: any = $state(null);
	let cpuHistory: number[] = $state([]);
	let memoryHistory: number[] = $state([]);

	// 성능 지표 탭 — 모달 전체 조회 단위
	type MetricsRange = '1m' | '10m' | '1h' | '6h' | '24h' | '7d';
	const METRICS_RANGE_OPTIONS: { key: MetricsRange; label: string }[] = [
		{ key: '1m', label: '1분' },
		{ key: '10m', label: '10분' },
		{ key: '1h', label: '1시간' },
		{ key: '6h', label: '6시간' },
		{ key: '24h', label: '24시간' },
		{ key: '7d', label: '7일' },
	];
	let metricsRange = $state<MetricsRange>('1h');
	let peakHistory = $state<{
		cpu: { value: number; ts: string | null };
		memory: { value: number; ts: string | null };
		network: { value: number; ts: string | null };
		disk: { value: number; ts: string | null };
		gpu: { value: number; ts: string | null };
		samples: number;
	}>({
		cpu: { value: 0, ts: null },
		memory: { value: 0, ts: null },
		network: { value: 0, ts: null },
		disk: { value: 0, ts: null },
		gpu: { value: 0, ts: null },
		samples: 0,
	});
	let peakLoading = $state(false);
	type HistoryPoint = { ts: string; cpu: number; mem: number; netRate: number; diskRate: number; gpu: number };
	let historyRows = $state<HistoryPoint[]>([]);
	let netRateSeries = $state<number[]>([]);
	let diskRateSeries = $state<number[]>([]);
	let metricsStats = $state<{
		cpu: { avg: number; min: number };
		memory: { avg: number; min: number };
		network: { avg: number; min: number };
		disk: { avg: number; min: number };
		gpu: { avg: number; min: number };
		cpuMinTs: string | null;
		memMinTs: string | null;
		netMinTs: string | null;
		diskMinTs: string | null;
		gpuMinTs: string | null;
		idleRatio: number;
		normalRatio: number;
		busyRatio: number;
		idleSeconds: number;
		normalSeconds: number;
		busySeconds: number;
	}>({
		cpu: { avg: 0, min: 0 }, memory: { avg: 0, min: 0 }, network: { avg: 0, min: 0 },
		disk: { avg: 0, min: 0 }, gpu: { avg: 0, min: 0 },
		cpuMinTs: null, memMinTs: null, netMinTs: null, diskMinTs: null, gpuMinTs: null,
		idleRatio: 0, normalRatio: 0, busyRatio: 0,
		idleSeconds: 0, normalSeconds: 0, busySeconds: 0,
	});

	// Logs data - raw string array like old project
	let logs: string[] = $state([]);
	let logSearchQuery = $state('');
	let logContainer: HTMLDivElement | undefined = $state(undefined);

	// Env vars expand
	let envExpanded = $state(false);

	// Container state (updated after control actions)
	let containerState = $state('');
	let containerStatus = $state('');

	let containerName = $derived(container?.names?.[0]?.replace('/', '') || container?.shortId || '');

	// Filtered logs
	let filteredLogs = $derived(
		logSearchQuery.trim()
			? logs.filter(l => l.toLowerCase().includes(logSearchQuery.trim().toLowerCase()))
			: logs
	);

	let memLimitMB = $derived((metricsData?.memory?.limit || 1) / 1048576);

	// Chart.js
	let cpuCanvas: HTMLCanvasElement | undefined = $state(undefined);
	let memCanvas: HTMLCanvasElement | undefined = $state(undefined);
	let cpuChart: Chart | null = null;
	let memChart: Chart | null = null;
	let timeLabels: string[] = $state([]);

	function formatTime(date: Date): string {
		return date.toTimeString().slice(0, 8); // HH:MM:SS
	}

	function calcYRange(data: number[], unit: string): { min: number; max: number } {
		if (data.length === 0) return unit === '%' ? { min: 0, max: 10 } : { min: 0, max: 100 };
		const min = Math.min(...data);
		const max = Math.max(...data);
		const range = max - min || 1;
		const padBottom = range * 0.15;
		const padTop = range * 0.3; // extra top padding so dot is never clipped
		const yMin = Math.max(0, Math.floor((min - padBottom) * 10) / 10);
		let yMax = Math.ceil((max + padTop) * 10) / 10;
		if (unit === '%') yMax = Math.min(yMax, 100);
		if (yMin === yMax) return { min: yMin, max: yMax + 1 };
		return { min: yMin, max: yMax };
	}

	function createChart(canvas: HTMLCanvasElement, color: string, unit: string): Chart {
		const ctx = canvas.getContext('2d')!;
		const gradient = ctx.createLinearGradient(0, 0, 0, canvas.clientHeight);
		gradient.addColorStop(0, color.replace(')', ', 0.4)').replace('rgb', 'rgba'));
		gradient.addColorStop(0.6, color.replace(')', ', 0.08)').replace('rgb', 'rgba'));
		gradient.addColorStop(1, color.replace(')', ', 0)').replace('rgb', 'rgba'));

		return new Chart(ctx, {
			type: 'line',
			data: {
				labels: [],
				datasets: [{
					data: [],
					borderColor: color,
					backgroundColor: gradient,
					borderWidth: 2,
					fill: true,
					tension: 0.35,
					pointRadius: 0,
					pointHoverRadius: 5,
					pointHoverBackgroundColor: color,
					pointHoverBorderColor: '#0d1117',
					pointHoverBorderWidth: 2,
					clip: false as any,
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 400, easing: 'easeOutQuart' },
				interaction: { intersect: false, mode: 'index' },
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: '#1e293b',
						titleColor: '#94a3b8',
						bodyColor: '#e2e8f0',
						borderColor: '#334155',
						borderWidth: 1,
						padding: 10,
						titleFont: { size: 11 },
						bodyFont: { size: 13, weight: 'bold' as const },
						displayColors: false,
						callbacks: {
							label: (item) => {
								const val = item.parsed.y;
								return unit === '%' ? `${val.toFixed(2)}%` : `${val.toFixed(1)} MB`;
							}
						}
					}
				},
				scales: {
					x: {
						grid: { color: 'rgba(255,255,255,0.04)', drawTicks: false },
						ticks: {
							color: '#64748b',
							font: { size: 10, family: "'JetBrains Mono', monospace" },
							maxRotation: 0,
							padding: 6,
							autoSkip: true,
							maxTicksLimit: 8,
						},
						border: { display: false }
					},
					y: {
						grid: { color: 'rgba(255,255,255,0.05)', drawTicks: false },
						ticks: {
							color: '#64748b',
							font: { size: 10, family: "'JetBrains Mono', monospace" },
							padding: 8,
							maxTicksLimit: 5,
							callback: (value) => unit === '%'
								? `${Number(value).toFixed(1)}%`
								: (Number(value) >= 1024 ? `${(Number(value) / 1024).toFixed(1)}G` : `${Math.round(Number(value))}M`)
						},
						border: { display: false }
					}
				}
			}
		});
	}

	function pushChartData(chart: Chart | null, data: number[], labels: string[], unit: string) {
		if (!chart) return;
		const ds = chart.data;
		// Spread to plain arrays - Svelte 5 $state proxies break Chart.js property descriptors
		ds.labels = [...labels];
		ds.datasets[0].data = [...data];

		// Dynamic Y range
		const { min, max } = calcYRange(data, unit);
		const yScale = chart.options.scales!.y!;
		(yScale as any).min = min;
		(yScale as any).max = max;

		// Last point dot
		ds.datasets[0].pointRadius = data.map((_, i) => i === data.length - 1 ? 4 : 0) as any;
		ds.datasets[0].pointBackgroundColor = ds.datasets[0].borderColor as string;

		chart.update('none');
	}

	function initCharts() {
		destroyCharts();
		if (cpuCanvas) {
			cpuChart = createChart(cpuCanvas, 'rgb(48, 213, 200)', '%');
			if (cpuHistory.length > 0) pushChartData(cpuChart, cpuHistory, timeLabels, '%');
		}
		if (memCanvas) {
			memChart = createChart(memCanvas, 'rgb(188, 19, 254)', 'MB');
			if (memoryHistory.length > 0) pushChartData(memChart, memoryHistory, timeLabels, 'MB');
		}
	}

	function destroyCharts() {
		if (cpuChart) { cpuChart.destroy(); cpuChart = null; }
		if (memChart) { memChart.destroy(); memChart = null; }
	}

	// Safe accessors for details
	let inspectConfig = $derived(details?.inspect?.Config);
	let inspectStats = $derived(details?.stats);
	let envVars = $derived(inspectConfig?.Env || []);

	async function fetchDetails() {
		if (!container) return;
		try {
			const raw = await sendCommand('inspect', { containerId: container.id });
			details = adaptContainerInspect(raw);
			containerState = details?.inspect?.State?.Status || container.state;
			containerStatus = details?.inspect?.State?.Status || container.status;
		} catch (e: any) {
			errorMsg = e?.message || '컨테이너 정보를 가져오는데 실패했습니다.';
			console.error('[ContainerDetailModal] inspect failed:', e);
		}
	}

	// container_metrics 스트리밍 구독: Agent가 주기적으로 보내는 메트릭을 그대로 사용.
	// 별도 REST 폴링 불필요.
	function consumeMetrics(m: any) {
		if (!m) return;
		metricsData = m;
		const cpuVal = m.cpu?.usage || 0;
		const memVal = (m.memory?.usage || 0) / 1048576;
		const now = formatTime(new Date());
		cpuHistory = [...cpuHistory.slice(-(MAX_HISTORY - 1)), cpuVal];
		memoryHistory = [...memoryHistory.slice(-(MAX_HISTORY - 1)), memVal];
		timeLabels = [...timeLabels.slice(-(MAX_HISTORY - 1)), now];
		pushChartData(cpuChart, cpuHistory, timeLabels, '%');
		pushChartData(memChart, memoryHistory, timeLabels, 'MB');
	}

	async function fetchLogs() {
		if (!container) return;
		try {
			const data = await sendCommand('get_logs', { containerId: container.id, tail: 100 });
			const lines = data?.lines ?? data?.logs ?? [];
			logs = Array.isArray(lines) ? lines : [];
		} catch (e: any) {
			console.error('[ContainerDetailModal] get_logs failed:', e);
			logs = ['로그를 불러오는 중 오류가 발생했습니다: ' + (e?.message || '')];
		}
	}

	function parseLogLine(line: string): { timestamp: string; level: string; message: string } {
		const tsMatch = line.match(/^(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}[\.\d]*)/);
		const nginxTsMatch = line.match(/\[(\d{2}\/\w{3}\/\d{4}:\d{2}:\d{2}:\d{2}[^\]]*)\]/);
		const levelMatch = line.match(/\b(INFO|WARN|ERROR|DEBUG)\b/i);
		const timestamp = tsMatch ? tsMatch[1] : (nginxTsMatch ? nginxTsMatch[1] : '');
		const level = levelMatch ? levelMatch[1].toUpperCase() : '';
		return { timestamp, level, message: line };
	}

	function getLevelColor(level: string): string {
		switch (level) {
			case 'INFO': return '#22c55e';
			case 'WARN': return '#f59e0b';
			case 'ERROR': return '#ef4444';
			case 'DEBUG': return '#64748b';
			default: return '#cbd5e1';
		}
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		if (bytes < 1024) return bytes + ' B';
		if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
		if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
		return (bytes / 1073741824).toFixed(1) + ' GB';
	}

	function formatRate(bytesPerSec: number): string {
		if (!Number.isFinite(bytesPerSec) || bytesPerSec <= 0) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let v = bytesPerSec;
		let i = 0;
		while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
		return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
	}

	function formatMemoryMB(bytes: number): string {
		return (bytes / 1048576).toFixed(1);
	}

	function formatDuration(s: number): string {
		if (!Number.isFinite(s) || s <= 0) return '0초';
		if (s < 60) return `${Math.round(s)}초`;
		if (s < 3600) return `${Math.round(s / 60)}분`;
		return `${Math.floor(s / 3600)}시간 ${Math.round((s % 3600) / 60)}분`;
	}

	function formatPeakTime(ts: string | null): string {
		if (!ts) return '-';
		const d = new Date(ts);
		if (Number.isNaN(d.getTime())) return '-';
		const pad = (n: number) => n.toString().padStart(2, '0');
		return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
	}

	function formatUptime(startedAt: string | null | undefined): string {
		if (!startedAt) return '-';
		const start = new Date(startedAt).getTime();
		if (!start) return '-';
		const sec = Math.max(0, Math.floor((Date.now() - start) / 1000));
		const d = Math.floor(sec / 86400);
		const h = Math.floor((sec % 86400) / 3600);
		const m = Math.floor((sec % 3600) / 60);
		if (d > 0) return `${d}일 ${h}시간`;
		if (h > 0) return `${h}시간 ${m}분`;
		if (m > 0) return `${m}분 ${sec % 60}초`;
		return `${sec}초`;
	}

	async function fetchPeakHistory(forRange: MetricsRange) {
		if (!container || !agentId || !accessToken) return;
		peakLoading = true;
		try {
			const limit = forRange === '7d' || forRange === '24h' ? 500 : 240;
			const cid = container.shortId ?? container.id.slice(0, 12);
			const url = `${base}/api/metrics/containers/?agent=${encodeURIComponent(agentId)}&container_id=${cid}&range=${forRange}&limit=${limit}&ordering=recorded_at`;
			const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
			const data = await res.json();
			const rows: any[] = Array.isArray(data?.data)
				? data.data
				: Array.isArray(data?.results)
					? data.results
					: Array.isArray(data) ? data : [];
			const empty = { value: 0, ts: null as string | null };
			if (rows.length === 0) {
				peakHistory = { cpu: { ...empty }, memory: { ...empty }, network: { ...empty }, disk: { ...empty }, gpu: { ...empty }, samples: 0 };
				historyRows = [];
				netRateSeries = [];
				diskRateSeries = [];
				metricsStats = {
					cpu: { avg: 0, min: 0 }, memory: { avg: 0, min: 0 }, network: { avg: 0, min: 0 },
					disk: { avg: 0, min: 0 }, gpu: { avg: 0, min: 0 },
					cpuMinTs: null, memMinTs: null, netMinTs: null, diskMinTs: null, gpuMinTs: null,
					idleRatio: 0, normalRatio: 0, busyRatio: 0,
					idleSeconds: 0, normalSeconds: 0, busySeconds: 0,
				};
				return;
			}
			const p = { cpu: { ...empty }, memory: { ...empty }, network: { ...empty }, disk: { ...empty }, gpu: { ...empty }, samples: rows.length };
			const mins = {
				cpu: { value: Infinity, ts: null as string | null },
				memory: { value: Infinity, ts: null as string | null },
				network: { value: Infinity, ts: null as string | null },
				disk: { value: Infinity, ts: null as string | null },
				gpu: { value: Infinity, ts: null as string | null },
			};
			const sums = { cpu: 0, memory: 0, gpu: 0, gpuCount: 0 };
			const rateSums = { network: 0, networkCount: 0, disk: 0, diskCount: 0 };
			const points: HistoryPoint[] = [];
			const netSeries: number[] = [];
			const diskSeries: number[] = [];
			let idleCount = 0, normalCount = 0, busyCount = 0;
			let prevNet = -1, prevDisk = -1, prevTs = '';
			let firstTs = '', lastTs = '';
			for (const row of rows) {
				const ts = row.recorded_at as string;
				if (!firstTs) firstTs = ts;
				lastTs = ts;
				const cpu = Number(row.cpu_usage ?? 0);
				const mem = Number(row.memory_percent ?? 0);
				const netCum = Number(row.network_rx ?? 0) + Number(row.network_tx ?? 0);
				const diskCum = Number(row.disk_read ?? 0) + Number(row.disk_write ?? 0);
				const gpu = Number(row.gpu_usage ?? 0);
				if (cpu > p.cpu.value) p.cpu = { value: cpu, ts };
				if (mem > p.memory.value) p.memory = { value: mem, ts };
				if (gpu > p.gpu.value) p.gpu = { value: gpu, ts };
				if (cpu < mins.cpu.value) mins.cpu = { value: cpu, ts };
				if (mem < mins.memory.value) mins.memory = { value: mem, ts };
				const hasGpuRow = row.gpu_usage !== null && row.gpu_usage !== undefined;
				if (hasGpuRow && gpu < mins.gpu.value) mins.gpu = { value: gpu, ts };
				sums.cpu += cpu; sums.memory += mem;
				if (hasGpuRow) { sums.gpu += gpu; sums.gpuCount += 1; }
				if (cpu < 1) idleCount += 1;
				else if (cpu < 10) normalCount += 1;
				else busyCount += 1;
				let netRate = 0, diskRate = 0;
				let hasRate = false;
				if (prevNet >= 0 && prevTs) {
					const dt = (new Date(ts).getTime() - new Date(prevTs).getTime()) / 1000;
					if (dt > 0) {
						netRate = Math.max(0, (netCum - prevNet) / dt);
						diskRate = Math.max(0, (diskCum - prevDisk) / dt);
						hasRate = true;
						if (netRate > p.network.value) p.network = { value: netRate, ts };
						if (diskRate > p.disk.value) p.disk = { value: diskRate, ts };
						if (netRate < mins.network.value) mins.network = { value: netRate, ts };
						if (diskRate < mins.disk.value) mins.disk = { value: diskRate, ts };
						rateSums.network += netRate; rateSums.networkCount += 1;
						rateSums.disk += diskRate; rateSums.diskCount += 1;
					}
				}
				points.push({ ts, cpu, mem, netRate, diskRate, gpu });
				netSeries.push(netRate);
				diskSeries.push(diskRate);
				prevNet = netCum; prevDisk = diskCum; prevTs = ts;
				void hasRate;
			}
			peakHistory = p;
			historyRows = points;
			netRateSeries = netSeries;
			diskRateSeries = diskSeries;

			const totalSec = firstTs && lastTs ? Math.max(0, (new Date(lastTs).getTime() - new Date(firstTs).getTime()) / 1000) : 0;
			const total = idleCount + normalCount + busyCount;
			const ratio = (n: number) => (total > 0 ? n / total : 0);
			metricsStats = {
				cpu: { avg: rows.length > 0 ? sums.cpu / rows.length : 0, min: mins.cpu.value === Infinity ? 0 : mins.cpu.value },
				memory: { avg: rows.length > 0 ? sums.memory / rows.length : 0, min: mins.memory.value === Infinity ? 0 : mins.memory.value },
				gpu: { avg: sums.gpuCount > 0 ? sums.gpu / sums.gpuCount : 0, min: mins.gpu.value === Infinity ? 0 : mins.gpu.value },
				network: { avg: rateSums.networkCount > 0 ? rateSums.network / rateSums.networkCount : 0, min: mins.network.value === Infinity ? 0 : mins.network.value },
				disk: { avg: rateSums.diskCount > 0 ? rateSums.disk / rateSums.diskCount : 0, min: mins.disk.value === Infinity ? 0 : mins.disk.value },
				cpuMinTs: mins.cpu.ts, memMinTs: mins.memory.ts, netMinTs: mins.network.ts, diskMinTs: mins.disk.ts, gpuMinTs: mins.gpu.ts,
				idleRatio: ratio(idleCount), normalRatio: ratio(normalCount), busyRatio: ratio(busyCount),
				idleSeconds: ratio(idleCount) * totalSec,
				normalSeconds: ratio(normalCount) * totalSec,
				busySeconds: ratio(busyCount) * totalSec,
			};
		} catch (e) {
			console.error('[ContainerDetailModal] peak fetch failed:', e);
		} finally {
			peakLoading = false;
		}
	}

	async function handleControl(action: string) {
		if (!container || controlLoading) return;
		controlLoading = action;
		try {
			await sendCommand('control', { containerId: container.id, action });
			await fetchDetails();
			onStateChange();
		} catch (e: any) {
			errorMsg = e?.message || '컨테이너 제어에 실패했습니다.';
			console.error('[ContainerDetailModal] control failed:', e);
		} finally {
			controlLoading = '';
		}
	}

	function downloadLogs() {
		const content = filteredLogs.join('\n');
		const blob = new Blob([content], { type: 'text/plain' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `${containerName}-logs.txt`;
		a.click();
		URL.revokeObjectURL(url);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	async function loadData() {
		if (!container) return;
		loadingInfo = true;
		loadingLogs = true;
		containerState = container.state;
		containerStatus = container.status;
		errorMsg = '';

		const [detailsResult, logsResult] = await Promise.allSettled([
			fetchDetails(),
			fetchLogs()
		]);

		if (detailsResult.status === 'rejected') {
			console.error('Details fetch failed:', detailsResult.reason);
			errorMsg = '컨테이너 정보를 가져오는데 실패했습니다.';
		}
		if (logsResult.status === 'rejected') {
			console.error('Logs fetch failed:', logsResult.reason);
			logs = ['로그를 불러올 수 없습니다.'];
		}

		loadingInfo = false;
		loadingLogs = false;

		// 초기 메트릭: 이미 store에 최신 값이 있으면 한 번 소비.
		// 이후 값은 metrics store 구독으로 자동 수신됨.
		if (container && metricsCache) {
			const cached = metricsCache.get(container.id);
			if (cached) consumeMetrics(cached);
		}
	}

	let metricsCache: Map<string, any> | null = null;
	let unsubMetrics: (() => void) | null = null;

	$effect(() => {
		const current = container;

		untrack(() => {
			if (current) {
				// Reset state for new container
				activeTab = 'info';
				details = null;
				metricsData = null;
				cpuHistory = [];
				memoryHistory = [];
				timeLabels = [];
				logs = [];
				errorMsg = '';
				envExpanded = false;
				containerState = current.state;
				containerStatus = current.status;

				loadData();
			}
		});
	});

	// Initialize charts when metrics tab is active and canvases are ready
	$effect(() => {
		const tab = activeTab;
		const cpu = cpuCanvas;
		const mem = memCanvas;

		untrack(() => {
			if (tab === 'metrics' && cpu && mem) {
				// Wait for canvas to be rendered in DOM
				setTimeout(() => initCharts(), 0);
			} else {
				destroyCharts();
			}
		});
	});

	// Refetch peak history when metrics tab is active and the modal range changes
	$effect(() => {
		const tab = activeTab;
		const r = metricsRange;
		const c = container;
		untrack(() => {
			if (tab === 'metrics' && c) fetchPeakHistory(r);
		});
	});

	onMount(() => {
		document.addEventListener('keydown', handleKeydown);
		unsubMetrics = containerMetricsStore.subscribe((map) => {
			metricsCache = map;
			if (container) {
				const m = map.get(container.id);
				if (m) consumeMetrics(m);
			}
		});
	});

	onDestroy(() => {
		if (unsubMetrics) { unsubMetrics(); unsubMetrics = null; }
		destroyCharts();
		document.removeEventListener('keydown', handleKeydown);
	});
</script>

{#if container}
<div class="overlay" onclick={onClose} role="dialog">
	<div class="modal" class:modal-metrics={activeTab === 'metrics'} class:modal-logs={activeTab === 'logs'} onclick={(e) => e.stopPropagation()}>
		<!-- Header -->
		<div class="modal-header">
			<div class="header-top">
				<div class="header-title">
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none">
						<path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" fill="#30d5c8"/>
					</svg>
					<span class="title-text">컨테이너 상세 정보</span>
				</div>
				<button class="close-btn" onclick={onClose}>
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
						<path d="M18 6L6 18M6 6l12 12"/>
					</svg>
				</button>
			</div>
			<div class="tabs">
				<button class="tab" class:active={activeTab === 'info'} onclick={() => activeTab = 'info'}>정보</button>
				<button class="tab" class:active={activeTab === 'metrics'} onclick={() => activeTab = 'metrics'}>성능 지표</button>
				<button class="tab" class:active={activeTab === 'logs'} onclick={() => activeTab = 'logs'}>로그</button>
			</div>
		</div>

		<!-- Content -->
		<div class="modal-content">
			{#if activeTab === 'info'}
				<!-- INFO TAB -->
				{#if loadingInfo}
					<div class="loading-state">컨테이너 정보를 불러오는 중...</div>
				{:else if errorMsg}
					<div class="loading-state error-text">{errorMsg}</div>
				{:else}
					<section class="section">
						<div class="section-title">
							<div class="section-dot"></div>
							<span>기본정보</span>
							<InfoTooltip placement="bottom-start" text="컨테이너의 신원(어떤 이미지로 언제 만들어졌는지)을 한눈에 보는 영역이에요." />
						</div>
						<div class="info-card">
							<div class="info-grid">
								<div class="info-item">
									<span class="info-label">이름 <InfoTooltip placement="top-start" text="Docker가 이 컨테이너에 붙인 사람이 읽기 쉬운 이름이에요. 보통 docker-compose가 '프로젝트-서비스-번호' 형식으로 자동 생성해요." /></span>
									<span class="info-value">{containerName}</span>
								</div>
								<div class="info-item">
									<span class="info-label">상태 <InfoTooltip placement="top-start" text="컨테이너의 현재 실행 상태예요.\n• 실행 중: 정상 동작\n• 일시정지: 프로세스 멈춤(메모리는 유지)\n• 중지: 종료됨\n• 장애: 비정상 종료\n• 재시작: 자동 재시작 중" /></span>
									<span class="info-value status" class:running={containerState === 'running'} class:stopped={containerState === 'exited' || containerState === 'dead'} class:paused={containerState === 'paused'}>
										{containerState === 'running' ? '실행 중' : containerState === 'paused' ? '일시정지' : containerState === 'exited' ? '중지' : containerState === 'dead' ? '장애' : containerState === 'restarting' ? '재시작' : containerState || '-'}
									</span>
								</div>
								<div class="info-item full">
									<span class="info-label">ID <InfoTooltip placement="top-start" text="Docker가 컨테이너를 구별하는 64자리 고유 식별자예요. 같은 이미지로 여러 컨테이너를 띄워도 ID는 모두 달라요. docker logs/exec 같은 명령에 쓸 수 있어요." /></span>
									<span class="info-value mono">{details?.inspect?.Id || container.id}</span>
								</div>
								<div class="info-item">
									<span class="info-label">이미지 <InfoTooltip placement="top-start" text="이 컨테이너를 만든 Docker 이미지(이름:태그)예요. 이미지 = 같은 실행 환경을 어디서나 똑같이 재현할 수 있는 청사진." /></span>
									<span class="info-value">{container.image}</span>
								</div>
								<div class="info-item">
									<span class="info-label">생성일 <InfoTooltip placement="top-start" text="컨테이너를 docker run / docker-compose up 으로 처음 만든 시각이에요. 재시작해도 이 값은 바뀌지 않아요." /></span>
									<span class="info-value">{details?.inspect?.Created ? new Date(details?.inspect?.Created).toLocaleString('ko-KR') : '-'}</span>
								</div>
								<div class="info-item">
									<span class="info-label">시작 시각 <InfoTooltip placement="top-start" text="컨테이너가 마지막으로 시작된 시각이에요. 재시작하면 갱신되며, 현재 시각과의 차이가 가동 시간(uptime)이에요." /></span>
									<span class="info-value">{details?.inspect?.State?.StartedAt ? new Date(details?.inspect?.State?.StartedAt).toLocaleString('ko-KR') : '-'}</span>
								</div>
							</div>
						</div>
					</section>

					{#if inspectConfig}
						<section class="section">
							<div class="section-title">
								<div class="section-dot"></div>
								<span>설정</span>
								<InfoTooltip placement="bottom-start" text="컨테이너가 시작될 때 사용한 실행 설정이에요. Dockerfile이나 docker-compose.yml에 적힌 값이 그대로 들어와요." />
							</div>
							<div class="settings-grid">
								<div class="info-card compact">
									<span class="info-label">명령어 <InfoTooltip placement="top-start" text="컨테이너가 시작될 때 실행한 첫 명령(ENTRYPOINT + CMD). 보통 서비스의 메인 프로세스예요. 예: python app.py, nginx -g 'daemon off;'" /></span>
									<span class="info-value">{inspectConfig?.Cmd?.join(' ') || '-'}</span>
								</div>
								<div class="info-card compact">
									<span class="info-label">작업 디렉토리 <InfoTooltip placement="top-start" text="위 명령어가 실행되는 컨테이너 내부 폴더 경로예요. 컨테이너 안의 'pwd(현재 위치)'와 같아요." /></span>
									<span class="info-value">{inspectConfig?.WorkingDir || '-'}</span>
								</div>
							</div>
							<div class="info-card">
								<div class="env-header">
									<span class="info-label">환경 변수 <InfoTooltip placement="top-start" text="컨테이너에 주입된 KEY=VALUE 형태의 설정값들이에요. DB 접속 정보·API 키·비밀번호 같은 환경별 설정을 코드 수정 없이 전달할 때 써요." /></span>
									{#if envVars.length > 3}
										<button class="env-toggle" onclick={() => envExpanded = !envExpanded}>
											{envExpanded ? '접기' : `전체 보기 (${envVars.length})`}
										</button>
									{/if}
								</div>
								<div class="env-list">
									{#each (envExpanded ? envVars : envVars.slice(0, 3)) as env}
										{@const parts = env.split('=')}
										<div class="env-item">
											<span class="env-key">{parts[0]}</span>
											<span class="env-val">{parts.slice(1).join('=')}</span>
										</div>
									{/each}
								</div>
							</div>
						</section>
					{/if}

					{#if inspectStats}
						<section class="section">
							<div class="section-title">
								<div class="section-dot"></div>
								<span>리소스 사용량</span>
								<InfoTooltip placement="bottom-start" text="지금 이 순간 컨테이너가 쓰고 있는 자원 한 컷이에요. 시간에 따른 추이는 위 '성능 지표' 탭에서 그래프로 볼 수 있어요." />
							</div>
							<div class="resource-grid">
								<div class="resource-card">
									<span class="info-label">CPU 사용률 <InfoTooltip placement="top-start" text="컨테이너가 호스트 CPU를 얼마나 쓰는지 (%). 100% = 한 코어를 가득 사용. 다중 코어를 동시에 쓰면 100%를 넘을 수도 있어요." /></span>
									<span class="resource-value">{metricsData?.cpu?.usage?.toFixed(2) || '0.00'}%</span>
								</div>
								<div class="resource-card">
									<span class="info-label">메모리 사용량 <InfoTooltip placement="top-start" text="컨테이너가 실제로 점유 중인 메모리(RAM)예요. 컨테이너에 설정된 메모리 한도에 가까워지면 OOM(메모리 부족 종료) 위험이 생겨요." /></span>
									<span class="resource-value">{metricsData?.memory ? formatMemoryMB(metricsData.memory.usage) : (inspectStats?.memory_stats ? formatBytes(inspectStats.memory_stats.usage) : '-')} <small class="resource-unit">{metricsData?.memory ? 'MB' : ''}</small></span>
								</div>
								<div class="resource-card">
									<span class="info-label">네트워크 (RX/TX) <InfoTooltip placement="top-start" text="컨테이너가 시작된 이후 누적된 트래픽이에요.\n• RX(Receive): 받은 데이터\n• TX(Transmit): 보낸 데이터\n실시간 속도가 아니라 누적 합계입니다." /></span>
									<span class="resource-value plain">{metricsData?.network ? formatBytes(metricsData.network.rx) + ' / ' + formatBytes(metricsData.network.tx) : '-'}</span>
								</div>
							</div>
						</section>
					{/if}

					{#if details?.inspect}
						{@const inspect2 = details.inspect}
						{@const restartCount2 = inspect2?.RestartCount ?? 0}
						{@const exitCode2 = inspect2?.State?.ExitCode}
						{@const pid2 = inspect2?.State?.Pid}
						{@const startedAt2 = inspect2?.State?.StartedAt}
						{@const ipAddr2 = (inspect2?.NetworkSettings?.IPAddress as string) || ((Object.values((inspect2?.NetworkSettings?.Networks as any) || {})[0] as any)?.IPAddress) || '-'}
						{@const ports2 = inspect2?.NetworkSettings?.Ports || {}}
						{@const portEntries2 = Object.entries(ports2).filter(([, v]) => Array.isArray(v) && (v as any[]).length > 0) as [string, any[]][]}
						{@const mounts2 = (Array.isArray(inspect2?.Mounts) ? inspect2.Mounts : []) as any[]}
						{@const networkEntries2 = Object.entries((inspect2?.NetworkSettings?.Networks as any) || {}) as [string, any][]}

						<section class="section">
							<div class="section-title">
								<div class="section-dot"></div>
								<span>운영 현황</span>
								<InfoTooltip placement="bottom-start" text="컨테이너의 런타임 상태(Docker inspect 정보)예요. 재시작 횟수가 자주 늘면 비정상 종료를 의심해 보세요." />
							</div>
							<div class="info-card">
								<div class="info-grid">
									<div class="info-item">
										<span class="info-label">가동 시간 <InfoTooltip placement="top-start" text="마지막 시작 시점부터 지금까지 누적된 시간이에요. 재시작하면 0으로 초기화돼요." /></span>
										<span class="info-value">{formatUptime(startedAt2)}</span>
									</div>
									<div class="info-item">
										<span class="info-label">재시작 횟수 <InfoTooltip placement="top-start" text="Docker가 자동으로 다시 시작한 횟수예요. 0이 정상이고, 자주 늘어나면 컨테이너가 죽었다 살아나는 패턴(헬스체크 실패·OOM 등)을 의심해 보세요." /></span>
										<span class="info-value" class:warn-text={restartCount2 > 0}>{restartCount2}</span>
									</div>
									<div class="info-item">
										<span class="info-label">종료 코드 <InfoTooltip placement="top-start" text="가장 최근 종료 시 프로세스가 반환한 exit code. 0 = 정상 종료, 그 외 = 오류. 137 = OOMKilled, 143 = SIGTERM." /></span>
										<span class="info-value">{exitCode2 === undefined || exitCode2 === null ? '-' : exitCode2}</span>
									</div>
									<div class="info-item">
										<span class="info-label">PID <InfoTooltip placement="top-start" text="컨테이너 메인 프로세스의 호스트 PID. 호스트에서 ps/top으로 추적할 때 써요." /></span>
										<span class="info-value mono">{pid2 || '-'}</span>
									</div>
									<div class="info-item">
										<span class="info-label">컨테이너 IP <InfoTooltip placement="top-start" text="Docker 네트워크 안에서 이 컨테이너에 할당된 내부 IP. 호스트의 외부 IP와는 다르고, 같은 Docker 네트워크의 다른 컨테이너만 이 주소로 접근할 수 있어요." /></span>
										<span class="info-value mono">{ipAddr2}</span>
									</div>
								</div>
							</div>
						</section>

						{#if portEntries2.length > 0 || networkEntries2.length > 0 || mounts2.length > 0}
							<section class="section">
								<div class="section-title">
									<div class="section-dot"></div>
									<span>네트워크 · 마운트</span>
									<InfoTooltip placement="bottom-start" text="컨테이너가 노출한 포트, 연결된 Docker 네트워크, 마운트된 볼륨이에요." />
								</div>
								<div class="info-card">
									{#if portEntries2.length > 0}
										<div class="info-block">
											<span class="info-label">노출 포트 <InfoTooltip placement="top-start" text="호스트 포트 → 컨테이너 포트 매핑이에요. 예: 8080 → 80/tcp = 호스트의 8080으로 들어온 요청이 컨테이너 안의 80으로 전달됨." /></span>
											<div class="port-chips">
												{#each portEntries2 as [containerPort, bindings]}
													{#each (bindings as any[]) as b}
														<span class="port-chip" title={`컨테이너 ${containerPort} → 호스트 ${b.HostIp || '0.0.0.0'}:${b.HostPort}`}>
															<b>{b.HostPort}</b>
															<small>→ {containerPort}</small>
														</span>
													{/each}
												{/each}
											</div>
										</div>
									{/if}
									{#if networkEntries2.length > 0}
										<div class="info-block">
											<span class="info-label">Docker 네트워크 <InfoTooltip placement="top-start" text="이 컨테이너가 가입된 Docker 네트워크 목록이에요. 같은 네트워크의 다른 컨테이너끼리는 컨테이너 이름으로 서로 호출할 수 있어요." /></span>
											<ul class="kv-list">
												{#each networkEntries2 as [name, info]}
													<li>
														<span class="kv-key">{name}</span>
														<span class="kv-val mono">{(info as any)?.IPAddress || '-'}</span>
													</li>
												{/each}
											</ul>
										</div>
									{/if}
									{#if mounts2.length > 0}
										<div class="info-block">
											<span class="info-label">마운트 ({mounts2.length}) <InfoTooltip placement="top-start" text="호스트 디렉터리 또는 Docker 볼륨이 컨테이너 내부 경로에 연결된 목록이에요. 컨테이너가 재시작되어도 데이터가 유지되는 영역입니다." /></span>
											<ul class="kv-list">
												{#each mounts2 as m}
													<li>
														<span class="kv-key">{m.Type}</span>
														<span class="kv-val mono" title={m.Source}>{m.Destination}</span>
													</li>
												{/each}
											</ul>
										</div>
									{/if}
								</div>
							</section>
						{/if}
					{/if}
				{/if}

			{:else if activeTab === 'metrics'}
				<!-- 성능 지표 TAB -->
				<div class="metrics-range-row">
					<span class="metrics-range-label">조회 단위</span>
					<div class="metrics-range-tabs" role="tablist" aria-label="성능 지표 조회 단위">
						{#each METRICS_RANGE_OPTIONS as opt (opt.key)}
							<button
								type="button"
								role="tab"
								aria-selected={metricsRange === opt.key}
								class="metrics-range-tab"
								class:active={metricsRange === opt.key}
								onclick={() => metricsRange = opt.key}
							>{opt.label}</button>
						{/each}
					</div>
					<InfoTooltip placement="bottom-end" text="아래 그래프 5개 + 우측 피크 값이 모두 이 시간 범위로 갱신돼요. 짧은 단위(1분/10분)는 실시간 추이를, 긴 단위(24시간/7일)는 장기 패턴을 보기 좋아요." />
				</div>

				{#if containerState !== 'running'}
					<div class="loading-state">컨테이너가 실행 중이 아닙니다.</div>
				{:else}
					{@const cpuPct = Number(metricsData?.cpu?.usage ?? 0)}
					{@const memPct = Number(metricsData?.memory?.percent ?? 0)}
					{@const lastRow = historyRows.length > 0 ? historyRows[historyRows.length - 1] : null}
					{@const netRate = Number(metricsData?.network?.rx_rate ?? metricsData?.network?.rx_rate_bps ?? 0)
						+ Number(metricsData?.network?.tx_rate ?? metricsData?.network?.tx_rate_bps ?? 0)
						|| (lastRow?.netRate ?? 0)}
					{@const diskRate = Number(metricsData?.disk?.read_rate ?? metricsData?.disk?.read_rate_bps ?? 0)
						+ Number(metricsData?.disk?.write_rate ?? metricsData?.disk?.write_rate_bps ?? 0)
						|| (lastRow?.diskRate ?? 0)}
					{@const gpuList = Array.isArray(metricsData?.gpu) ? metricsData.gpu : (metricsData?.gpu ? [metricsData.gpu] : [])}
					{@const gpuPct = gpuList.length > 0 ? Number(gpuList[0]?.usage ?? 0) : 0}
					{@const hasGpu = gpuList.length > 0}
					{@const cid = container.shortId ?? container.id.slice(0, 12)}
					{@const rangeLabel = METRICS_RANGE_OPTIONS.find(o => o.key === metricsRange)?.label ?? metricsRange}
					{@const inspect = details?.inspect}
					{@const restartCount = inspect?.RestartCount ?? 0}
					{@const exitCode = inspect?.State?.ExitCode}
					{@const pid = inspect?.State?.Pid}
					{@const startedAt = inspect?.State?.StartedAt}
					{@const ipAddr = (inspect?.NetworkSettings?.IPAddress as string) || ((Object.values((inspect?.NetworkSettings?.Networks as any) || {})[0] as any)?.IPAddress) || '-'}
					{@const networkMax = Math.max(1, ...netRateSeries)}
					{@const diskMax = Math.max(1, ...diskRateSeries)}
					{@const radarAxes = [
						{ label: 'CPU', value: cpuPct, reference: peakHistory.cpu.value },
						{ label: '메모리', value: memPct, reference: peakHistory.memory.value },
						{ label: 'GPU', value: gpuPct, reference: peakHistory.gpu.value },
					]}
					{@const ports = inspect?.NetworkSettings?.Ports || {}}
					{@const portEntries = Object.entries(ports).filter(([, v]) => Array.isArray(v) && (v as any[]).length > 0) as [string, any[]][]}
					{@const mounts = (Array.isArray(inspect?.Mounts) ? inspect.Mounts : []) as any[]}
					{@const networkEntries = Object.entries((inspect?.NetworkSettings?.Networks as any) || {}) as [string, any][]}

					<div class="metrics-layout">
						<div class="metrics-charts">
							{#key `cpu-${metricsRange}`}
								<div class="metric-stack">
									<div class="metric-stack-head">
										<span class="metric-stack-label">CPU 사용률
											<InfoTooltip placement="top-start" text="이 컨테이너가 호스트 CPU를 얼마나 쓰는지 (%). 100% = 한 코어 가득. 다중 코어면 100%를 넘을 수도 있어요." />
										</span>
										<strong class="metric-stack-current cpu">{cpuPct.toFixed(1)}%</strong>
									</div>
									<MetricTrendChart {agentId} {accessToken} endpoint="/api/metrics/containers/" extraQuery={`container_id=${cid}`} metricField="cpu_usage" liveValue={cpuPct} label="CPU 사용률 (%)" color="#30d5c8" unit="percent" defaultRange={metricsRange} hideRangeTabs compact />
								</div>
							{/key}
							{#key `mem-${metricsRange}`}
								<div class="metric-stack">
									<div class="metric-stack-head">
										<span class="metric-stack-label">메모리 사용률
											<InfoTooltip placement="top-start" text="컨테이너가 점유한 메모리 비율 (%). 한도에 가까워지면 OOM(메모리 부족 종료) 위험이 있어요." />
										</span>
										<strong class="metric-stack-current memory">{memPct.toFixed(1)}%</strong>
									</div>
									<MetricTrendChart {agentId} {accessToken} endpoint="/api/metrics/containers/" extraQuery={`container_id=${cid}`} metricField="memory_percent" liveValue={memPct} label="메모리 사용률 (%)" color="#8b5cf6" unit="percent" defaultRange={metricsRange} hideRangeTabs compact />
								</div>
							{/key}
							{#key `net-${metricsRange}`}
								<div class="metric-stack">
									<div class="metric-stack-head">
										<span class="metric-stack-label">네트워크 처리량
											<InfoTooltip placement="top-start" text="현재 초당 네트워크 처리량(RX+TX, B/s)이에요. Docker는 누적값만 노출하기 때문에 인접 샘플의 변화량으로 환산했어요. 평평 = 트래픽 없음, 솟아오름 = 활발한 통신." />
										</span>
										<strong class="metric-stack-current net">{formatRate(netRate)}</strong>
									</div>
									<MetricTrendChart {agentId} {accessToken} endpoint="/api/metrics/containers/" extraQuery={`container_id=${cid}`} metricField="" metricExtractor={(row) => Number(row?.network_rx ?? 0) + Number(row?.network_tx ?? 0)} liveValue={netRate} label="네트워크 처리량 (B/s)" color="#fbbf24" unit="rate" defaultRange={metricsRange} hideRangeTabs compact derivative />
								</div>
							{/key}
							{#key `disk-${metricsRange}`}
								<div class="metric-stack">
									<div class="metric-stack-head">
										<span class="metric-stack-label">디스크 처리량
											<InfoTooltip placement="top-start" text="현재 초당 디스크 I/O 처리량(읽기+쓰기, B/s)이에요. Docker는 누적값만 노출해서 인접 샘플 변화량으로 환산했고, 평평하면 디스크 접근이 거의 없다는 뜻이에요." />
										</span>
										<strong class="metric-stack-current disk">{formatRate(diskRate)}</strong>
									</div>
									<MetricTrendChart {agentId} {accessToken} endpoint="/api/metrics/containers/" extraQuery={`container_id=${cid}`} metricField="" metricExtractor={(row) => Number(row?.disk_read ?? 0) + Number(row?.disk_write ?? 0)} liveValue={diskRate} label="디스크 처리량 (B/s)" color="#a78bfa" unit="rate" defaultRange={metricsRange} hideRangeTabs compact derivative />
								</div>
							{/key}
							{#if hasGpu}
								{#key `gpu-${metricsRange}`}
									<div class="metric-stack">
										<div class="metric-stack-head">
											<span class="metric-stack-label">GPU 사용률
												<InfoTooltip placement="top-start" text="GPU usage (%). nvidia-smi / rocm-smi가 보고하는 사용률이에요. 측정 불가(usage=null)인 GPU는 제외돼요." />
											</span>
											<strong class="metric-stack-current gpu">{gpuPct.toFixed(1)}%</strong>
										</div>
										<MetricTrendChart {agentId} {accessToken} endpoint="/api/metrics/containers/" extraQuery={`container_id=${cid}`} metricField="gpu_usage" liveValue={gpuPct} label="GPU 사용률 (%)" color="#f472b6" unit="percent" defaultRange={metricsRange} hideRangeTabs compact />
									</div>
								{/key}
							{/if}
						</div>

						<aside class="metrics-summary">
							{#if peakLoading}
								<section class="summary-section"><div class="summary-loading">불러오는 중...</div></section>
							{:else if peakHistory.samples === 0}
								<section class="summary-section"><div class="summary-empty">{rangeLabel} 동안 기록된 데이터가 없어요.</div></section>
							{:else}
								{@const memSwing = peakHistory.memory.value - metricsStats.memory.min}

								<section class="summary-section">
									<div class="summary-section-head">
										<h4 class="summary-h4">{rangeLabel} 평균값</h4>
										<InfoTooltip placement="bottom-end" text="선택한 시간 동안 매 샘플의 평균이에요. 일상적인 부하가 어느 정도인지 가늠하는 기준선이 돼요." />
									</div>
									<ul class="summary-list">
										<li><span class="summary-key">CPU</span><span class="summary-val">{metricsStats.cpu.avg.toFixed(2)}%</span><small class="summary-when">현재 {cpuPct.toFixed(1)}%</small></li>
										<li><span class="summary-key">메모리</span><span class="summary-val">{metricsStats.memory.avg.toFixed(2)}%</span><small class="summary-when">현재 {memPct.toFixed(1)}%</small></li>
										<li><span class="summary-key">네트워크</span><span class="summary-val">{formatRate(metricsStats.network.avg)}</span><small class="summary-when">현재 {formatRate(netRate)}</small></li>
										<li><span class="summary-key">디스크</span><span class="summary-val">{formatRate(metricsStats.disk.avg)}</span><small class="summary-when">현재 {formatRate(diskRate)}</small></li>
										{#if hasGpu}
											<li><span class="summary-key">GPU</span><span class="summary-val">{metricsStats.gpu.avg.toFixed(2)}%</span><small class="summary-when">현재 {gpuPct.toFixed(1)}%</small></li>
										{/if}
									</ul>
								</section>

								<section class="summary-section">
									<div class="summary-section-head">
										<h4 class="summary-h4">{rangeLabel} 피크 값</h4>
										<InfoTooltip placement="bottom-end" text="선택한 시간 동안 가장 높았던 값과 그 시각이에요. NET·DISK는 인접 샘플의 변화량(rate)으로 환산한 최대 처리량입니다." />
									</div>
									<ul class="summary-list">
										<li><span class="summary-key">CPU</span><span class="summary-val">{peakHistory.cpu.value.toFixed(1)}%</span><small class="summary-when">{formatPeakTime(peakHistory.cpu.ts)}</small></li>
										<li><span class="summary-key">메모리</span><span class="summary-val">{peakHistory.memory.value.toFixed(1)}%</span><small class="summary-when">{formatPeakTime(peakHistory.memory.ts)}</small></li>
										<li><span class="summary-key">네트워크</span><span class="summary-val">{formatRate(peakHistory.network.value)}</span><small class="summary-when">{formatPeakTime(peakHistory.network.ts)}</small></li>
										<li><span class="summary-key">디스크</span><span class="summary-val">{formatRate(peakHistory.disk.value)}</span><small class="summary-when">{formatPeakTime(peakHistory.disk.ts)}</small></li>
										{#if hasGpu}
											<li><span class="summary-key">GPU</span><span class="summary-val">{peakHistory.gpu.value.toFixed(1)}%</span><small class="summary-when">{formatPeakTime(peakHistory.gpu.ts)}</small></li>
										{/if}
									</ul>
								</section>

								<section class="summary-section">
									<div class="summary-section-head">
										<h4 class="summary-h4">{rangeLabel} 최저값</h4>
										<InfoTooltip placement="bottom-end" text="선택한 시간 동안 가장 한가했던 값이에요. 평소 idle 수준이 어느 정도인지 가늠할 수 있어요." />
									</div>
									<ul class="summary-list">
										<li><span class="summary-key">CPU</span><span class="summary-val">{metricsStats.cpu.min.toFixed(2)}%</span><small class="summary-when">{formatPeakTime(metricsStats.cpuMinTs)}</small></li>
										<li><span class="summary-key">메모리</span><span class="summary-val">{metricsStats.memory.min.toFixed(2)}%</span><small class="summary-when">{formatPeakTime(metricsStats.memMinTs)}</small></li>
										<li><span class="summary-key">네트워크</span><span class="summary-val">{formatRate(metricsStats.network.min)}</span><small class="summary-when">{formatPeakTime(metricsStats.netMinTs)}</small></li>
										<li><span class="summary-key">디스크</span><span class="summary-val">{formatRate(metricsStats.disk.min)}</span><small class="summary-when">{formatPeakTime(metricsStats.diskMinTs)}</small></li>
										{#if hasGpu}
											<li><span class="summary-key">GPU</span><span class="summary-val">{metricsStats.gpu.min.toFixed(2)}%</span><small class="summary-when">{formatPeakTime(metricsStats.gpuMinTs)}</small></li>
										{/if}
									</ul>
								</section>

								<section class="summary-section activity">
									<div class="summary-section-head">
										<h4 class="summary-h4">{rangeLabel} 활동 패턴</h4>
										<InfoTooltip placement="bottom-end" text="컨테이너가 시간 동안 얼마나 일했는지 보여줘요.\n\n• 거의 쉬는 중 — CPU를 거의 안 쓰는 한가한 시간\n• 가벼운 작업 — 잠깐씩 작업이 들어오는 보통 시간\n• 활발히 작동 — 처리량이 많은 바쁜 시간\n\n쉬는 시간이 길면 idle, 활발히 작동이 자주 보이면 워크로드가 많이 들어왔다는 뜻이에요." />
									</div>
									<div class="dist-bar" aria-hidden="true">
										<span class="dist-seg dist-idle" style={`flex: ${Math.max(0.001, metricsStats.idleRatio)}`}></span>
										<span class="dist-seg dist-normal" style={`flex: ${Math.max(0.001, metricsStats.normalRatio)}`}></span>
										<span class="dist-seg dist-busy" style={`flex: ${Math.max(0.001, metricsStats.busyRatio)}`}></span>
									</div>
									<ul class="summary-list dist-list">
										<li><span class="summary-key dist-key idle">거의 쉬는 중</span><span class="summary-val">{(metricsStats.idleRatio * 100).toFixed(1)}%</span><small class="summary-when">{formatDuration(metricsStats.idleSeconds)}</small></li>
										<li><span class="summary-key dist-key normal">가벼운 작업</span><span class="summary-val">{(metricsStats.normalRatio * 100).toFixed(1)}%</span><small class="summary-when">{formatDuration(metricsStats.normalSeconds)}</small></li>
										<li><span class="summary-key dist-key busy">활발히 작동</span><span class="summary-val">{(metricsStats.busyRatio * 100).toFixed(1)}%</span><small class="summary-when">{formatDuration(metricsStats.busySeconds)}</small></li>
									</ul>
									{#if memSwing > 5}
										<div class="summary-tail">
											<span class="summary-pill warn">메모리 변동 폭 {memSwing.toFixed(1)}% — 누수 의심</span>
										</div>
									{:else if memSwing > 0}
										<div class="summary-tail">
											<span class="summary-pill">메모리 변동 폭 {memSwing.toFixed(1)}%</span>
										</div>
									{/if}
								</section>
							{/if}
						</aside>
					</div>
				{/if}

			{:else}
				<!-- LOGS TAB -->
				<div class="logs-toolbar">
					<div class="log-search">
						<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2">
							<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
						</svg>
						<input type="text" placeholder="로그 검색..." bind:value={logSearchQuery} />
					</div>
					<div class="logs-controls">
						<button class="download-btn" onclick={downloadLogs} title="현재 표시된 로그를 .txt 파일로 저장합니다.">
							<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
							</svg>
							다운로드
						</button>
					</div>
				</div>
				<div class="terminal">
					<div class="terminal-header">
						<div class="terminal-dots">
							<span class="dot red"></span>
							<span class="dot yellow"></span>
							<span class="dot green"></span>
						</div>
						<span class="terminal-title">bash — 로그 뷰어 — {filteredLogs.length} 줄</span>
					</div>
					<div class="terminal-body" bind:this={logContainer}>
						{#if loadingLogs}
							<div class="log-empty">로그 로딩 중...</div>
						{:else if filteredLogs.length === 0}
							<div class="log-empty">로그가 없습니다.</div>
						{:else}
							{#each filteredLogs as line}
								{@const parsed = parseLogLine(line)}
								<div class="log-line">
									{#if parsed.timestamp}
										<span class="log-ts">{parsed.timestamp}</span>
									{/if}
									{#if parsed.level}
										<span class="log-level" style="color: {getLevelColor(parsed.level)}">{parsed.level}</span>
									{/if}
									<span class="log-msg">{parsed.level || parsed.timestamp ? parsed.message.replace(parsed.timestamp, '').trim() : line}</span>
								</div>
							{/each}
						{/if}
					</div>
				</div>
			{/if}
		</div>

		<!-- Footer -->
		<div class="modal-footer">
			{#if containerState === 'running'}
				<button class="action-btn danger" onclick={() => handleControl('stop')} disabled={!!controlLoading} title="컨테이너 프로세스를 정상 종료(SIGTERM)합니다. 데이터는 유지되고 다시 '시작'으로 켤 수 있어요.">
					{controlLoading === 'stop' ? '처리 중...' : '중지'}
				</button>
				<div class="action-right">
					<button class="action-btn secondary" onclick={() => handleControl('restart')} disabled={!!controlLoading} title="중지 후 즉시 다시 시작합니다. 설정 파일을 다시 읽거나 메모리 누수를 초기화할 때 써요.">
						{controlLoading === 'restart' ? '처리 중...' : '재시작'}
					</button>
					<button class="action-btn secondary" onclick={() => handleControl('pause')} disabled={!!controlLoading} title="컨테이너의 모든 프로세스를 동결(freeze)합니다. CPU 사용은 멈추지만 메모리는 유지돼요. '재개'로 즉시 복귀.">
						{controlLoading === 'pause' ? '처리 중...' : '일시정지'}
					</button>
				</div>
			{:else if containerState === 'paused'}
				<button class="action-btn danger" onclick={() => handleControl('stop')} disabled={!!controlLoading} title="일시정지 상태에서 컨테이너를 정상 종료합니다.">
					{controlLoading === 'stop' ? '처리 중...' : '중지'}
				</button>
				<div class="action-right">
					<button class="action-btn accent" onclick={() => handleControl('unpause')} disabled={!!controlLoading} title="일시정지 상태에서 프로세스를 다시 깨워 실행 중으로 되돌립니다.">
						{controlLoading === 'unpause' ? '처리 중...' : '재개'}
					</button>
				</div>
			{:else}
				<button class="action-btn accent" onclick={() => handleControl('start')} disabled={!!controlLoading} title="중지된 컨테이너를 다시 시작합니다. 동일한 설정과 데이터로 부팅돼요.">
					{controlLoading === 'start' ? '처리 중...' : '시작'}
				</button>
				<div class="action-right">
					<button class="action-btn secondary" onclick={() => handleControl('restart')} disabled={!!controlLoading} title="현재 상태와 무관하게 컨테이너를 재시작합니다.">
						{controlLoading === 'restart' ? '처리 중...' : '재시작'}
					</button>
				</div>
			{/if}
		</div>
	</div>
</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 100;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		backdrop-filter: blur(4px);
	}

	.modal {
		width: min(1100px, 92vw);
		max-height: 92vh;
		background: #0d1117;
		border: 1px solid #30d5c8;
		border-radius: 12px;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	/* Metrics tab gets the full real estate so the two charts side-by-side
	   still have room for the range tab row + Y-axis labels. */
	.modal-metrics { width: min(1040px, 88vw); }
	.modal-logs { width: min(1200px, 94vw); }

	/* Header */
	.modal-header {
		flex-shrink: 0;
		border-bottom: 1px solid #1f2937;
	}

	.header-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 24px;
	}

	.header-title {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.title-text {
		font-size: 15px;
		font-weight: 700;
		color: #d9d9d9;
	}

	.close-btn {
		background: none;
		border: none;
		cursor: pointer;
		padding: 4px;
		display: flex;
	}

	.close-btn:hover svg { stroke: #cbd5e1; }

	.tabs {
		display: flex;
		padding: 0 24px;
		gap: 32px;
	}

	.tab {
		padding: 12px 8px;
		border: none;
		background: none;
		font-size: 13px;
		font-weight: 700;
		color: #64748b;
		cursor: pointer;
		border-bottom: 2px solid transparent;
	}

	.tab.active {
		color: #30d5c8;
		border-bottom-color: #30d5c8;
	}

	.tab:hover:not(.active) { color: #94a3b8; }

	/* Content */
	.modal-content {
		flex: 1;
		overflow-y: auto;
		overflow-x: hidden;
		padding: 16px 20px 18px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	/* Loading */
	.loading-state {
		text-align: center;
		color: #64748b;
		font-size: 13px;
		padding: 24px 0;
	}

	.error-text { color: #ef4444; }

	/* Sections */
	.section { display: flex; flex-direction: column; gap: 16px; }

	.section-title {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 13px;
		font-weight: 700;
		color: #64748b;
	}

	.section-dot {
		width: 4px;
		height: 12px;
		background: #0f667b;
		border-radius: 9999px;
	}

	/* Info Cards */
	.info-card {
		background: #121720;
		border-radius: 8px;
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.info-card.compact { gap: 4px; }

	.info-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
	}

	.info-item { display: flex; flex-direction: column; gap: 4px; }
	.info-item.full { grid-column: 1 / -1; }

	.info-label { font-size: 13px; color: #64748b; }

	.info-value { font-size: 14px; color: #cbd5e1; }
	.info-value.mono { font-size: 12px; font-family: monospace; word-break: break-all; }

	.info-value.status { font-size: 12px; font-weight: 700; }
	.info-value.status.running { color: #30d5c8; }
	.info-value.status.stopped { color: #64748b; }
	.info-value.status.paused { color: #f59e0b; }

	/* Settings */
	.settings-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
	}

	/* Env vars */
	.env-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.env-toggle {
		background: none;
		border: none;
		color: #30d5c8;
		font-size: 12px;
		cursor: pointer;
		padding: 0;
	}

	.env-toggle:hover { text-decoration: underline; }

	.env-list { display: flex; flex-direction: column; gap: 4px; }

	.env-item {
		display: flex;
		justify-content: space-between;
		padding: 6px 12px;
		background: #151c27;
		border-radius: 4px;
	}

	.env-key { font-size: 11px; color: #cbd5e1; }
	.env-val { font-size: 11px; color: #30d5c8; }

	/* Resources */
	.resource-grid {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 16px;
	}

	.resource-card {
		background: #121720;
		border-radius: 8px;
		padding: 16px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
	}

	.resource-value { font-size: 20px; font-weight: 500; color: #30d5c8; }
	.resource-value.plain { color: #cbd5e1; font-size: 14px; }
	.resource-unit { font-size: 12px; color: #64748b; font-weight: 400; }

	/* 성능 지표 Tab — 새 레이아웃 */
	.metrics-range-row {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 0;
		padding-bottom: 4px;
		border-bottom: 1px dashed rgba(100, 116, 139, 0.2);
	}
	.metrics-range-label {
		font-size: 12px;
		font-weight: 800;
		color: var(--text-muted);
		letter-spacing: 0.02em;
	}
	.metrics-range-tabs {
		display: inline-flex;
		gap: 2px;
		padding: 2px;
		border: 1px solid rgba(100, 116, 139, 0.24);
		border-radius: 999px;
		background: rgba(15, 23, 42, 0.55);
	}
	.metrics-range-tab {
		border: none;
		background: transparent;
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 800;
		padding: 5px 12px;
		border-radius: 999px;
		cursor: pointer;
		letter-spacing: 0.02em;
	}
	.metrics-range-tab.active {
		background: rgba(48, 213, 200, 0.22);
		color: #30d5c8;
	}

	.metrics-layout {
		display: grid;
		grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr);
		gap: 14px;
		min-width: 0;
		flex: 1 1 auto;
		align-items: stretch;
	}
	.metrics-charts {
		display: flex;
		flex-direction: column;
		gap: 12px;
		min-width: 0;
	}
	.metric-stack {
		background: #121720;
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-radius: 8px;
		padding: 10px 12px 12px;
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}
	.metric-stack-head {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.metric-stack-label {
		font-size: 12px;
		font-weight: 800;
		color: #cbd5e1;
		letter-spacing: 0.02em;
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}
	.metric-stack-current {
		margin-left: auto;
		font-size: 13px;
		font-weight: 900;
		font-variant-numeric: tabular-nums;
	}
	.metric-stack-current.cpu { color: #30d5c8; }
	.metric-stack-current.memory { color: #a78bfa; }
	.metric-stack-current.net { color: #fbbf24; }
	.metric-stack-current.disk { color: #c4b5fd; }
	.metric-stack-current.gpu { color: #f472b6; }
	.metric-stack :global(.trend) { gap: 2px; }
	.metric-stack :global(.canvas-wrap) { height: 110px; }

	.metrics-summary {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
		min-height: 0;
	}
	.metrics-summary > .summary-section {
		flex: 1 1 0;
		min-height: 0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	.metrics-summary > .summary-section.activity {
		flex: 1.4 1 0;
	}
	.metrics-summary .summary-list {
		flex: 1 1 auto;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		gap: 3px;
	}
	.metrics-summary .summary-list li {
		padding-top: 3px;
		padding-bottom: 3px;
	}
	.summary-section {
		background: #121720;
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-radius: 8px;
		padding: 8px 10px 10px;
	}
	.summary-section-head {
		display: flex;
		align-items: center;
		gap: 4px;
		margin-bottom: 8px;
	}
	.summary-h4 {
		margin: 0;
		font-size: 12px;
		font-weight: 800;
		color: #cbd5e1;
		letter-spacing: 0.02em;
	}
	.summary-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 5px;
	}
	.summary-list li {
		display: grid;
		grid-template-columns: 48px minmax(0, 1fr) auto;
		align-items: baseline;
		gap: 6px;
		padding: 3px 8px;
		border-radius: 5px;
		background: rgba(13, 17, 23, 0.55);
		min-width: 0;
	}
	.summary-list li .summary-val {
		text-align: right;
	}
	.summary-list li .summary-when {
		margin-left: 0;
	}
	.summary-key {
		font-size: 10px;
		font-weight: 800;
		color: var(--text-muted);
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}
	.summary-val {
		font-size: 13px;
		font-weight: 900;
		color: #e2e8f0;
		font-variant-numeric: tabular-nums;
	}
	.summary-val.warn { color: #fbbf24; }
	.mono-summary {
		font-family: 'JetBrains Mono', monospace;
		font-weight: 700;
		font-size: 11px;
		color: #94a3b8;
	}
	.summary-when {
		font-size: 10px;
		color: #64748b;
		font-weight: 700;
		text-align: right;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.summary-loading,
	.summary-empty {
		font-size: 11px;
		color: var(--text-muted);
		padding: 8px 4px;
	}
	.summary-meta {
		display: block;
		margin-top: 8px;
		font-size: 10px;
		color: #475569;
		text-align: right;
	}
	.summary-tail {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 5px;
		margin-top: 8px;
		flex: 0 0 auto;
	}
	.metrics-summary .summary-list.dist-list {
		flex: 0 0 auto;
	}
	.summary-pill {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 8px;
		border: 1px solid rgba(100, 116, 139, 0.3);
		border-radius: 999px;
		background: rgba(13, 17, 23, 0.6);
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
	}
	.summary-pill.warn {
		border-color: rgba(251, 191, 36, 0.45);
		background: rgba(251, 191, 36, 0.12);
		color: #fbbf24;
	}
	.dist-bar {
		display: flex;
		gap: 2px;
		height: 12px;
		border-radius: 999px;
		overflow: hidden;
		margin-bottom: 8px;
	}
	.dist-seg {
		display: block;
		min-width: 2px;
	}
	.dist-seg.dist-idle { background: rgba(100, 116, 139, 0.55); }
	.dist-seg.dist-normal { background: rgba(48, 213, 200, 0.7); }
	.dist-seg.dist-busy { background: rgba(251, 113, 133, 0.85); }
	.dist-list li {
		grid-template-columns: 92px minmax(0, 1fr) auto;
	}
	.dist-list .dist-key {
		text-transform: none;
		letter-spacing: 0;
		font-size: 11px;
	}
	.dist-key.idle { color: #94a3b8; }
	.dist-key.normal { color: #30d5c8; }
	.dist-key.busy { color: #fb7185; }
	.summary-empty.small { font-size: 10px; padding: 4px 2px; }
	.summary-row.two {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 10px;
	}
	.radar-section,
	.scatter-section {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.radar-host,
	.scatter-host {
		flex: 1 1 0;
		min-height: 160px;
		min-width: 0;
		position: relative;
	}
	.scatter-host canvas {
		width: 100% !important;
		height: 100% !important;
	}
	.rate-row {
		display: grid;
		grid-template-columns: 36px minmax(0, 1fr) auto;
		align-items: center;
		gap: 8px;
		padding: 4px 0;
	}
	.rate-row + .rate-row {
		border-top: 1px dashed rgba(100, 116, 139, 0.18);
	}
	.rate-label {
		font-size: 9px;
		font-weight: 900;
		letter-spacing: 0.06em;
	}
	.rate-label.net { color: #fbbf24; }
	.rate-label.disk { color: #a78bfa; }
	.rate-spark {
		min-width: 0;
		height: 24px;
	}
	.rate-current {
		font-size: 11px;
		font-weight: 800;
		color: #cbd5e1;
		font-variant-numeric: tabular-nums;
		min-width: 64px;
		text-align: right;
	}
	.summary-list.compact li {
		grid-template-columns: minmax(0, 1fr) auto;
	}
	.port-block + .port-block {
		margin-top: 8px;
		padding-top: 8px;
		border-top: 1px dashed rgba(100, 116, 139, 0.18);
	}
	.port-block-label {
		font-size: 10px;
		font-weight: 800;
		color: var(--text-muted);
		letter-spacing: 0.04em;
		text-transform: uppercase;
		margin-bottom: 5px;
	}
	.port-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}
	.port-chip {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
		padding: 2px 8px;
		border: 1px solid rgba(48, 213, 200, 0.4);
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.08);
		font-size: 11px;
		font-variant-numeric: tabular-nums;
	}
	.port-chip b { color: #30d5c8; font-weight: 900; }
	.port-chip small { color: #64748b; font-size: 9px; }
	.mount-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.mount-list li {
		display: grid;
		grid-template-columns: 64px minmax(0, 1fr);
		gap: 6px;
		align-items: baseline;
		padding: 3px 6px;
		border-radius: 4px;
		background: rgba(13, 17, 23, 0.55);
		font-size: 11px;
	}
	.mount-type {
		font-size: 9px;
		font-weight: 800;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.mount-path {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: #cbd5e1;
	}
	.mount-more {
		justify-self: center;
		font-size: 10px;
		color: var(--text-muted);
		background: transparent;
	}
	@media (max-width: 980px) {
		.metrics-layout {
			grid-template-columns: 1fr;
		}
	}

	/* Legacy metrics-tab styles (unused after redesign — kept for log/info reuse) */
	.metrics-grid-top, .metrics-grid-bottom {
		display: grid;
		/* minmax(0, 1fr) lets columns actually shrink below intrinsic width —
		   without it, charts/tab rows force horizontal scroll in the modal. */
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 24px;
	}

	.metrics-card {
		background: #121720;
		border-radius: 8px;
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}

	.metrics-card-header {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-bottom: 10px;
	}

	/* Push "current value" cell to the far right; title + ? sit together on the left. */
	.metrics-card-header > .metrics-current { margin-left: auto; }

	.metrics-card-title { font-size: 13px; font-weight: 700; color: #cbd5e1; }
	.metrics-card-title.muted { color: #64748b; }

	.metrics-current { font-size: 12px; }
	.metrics-current.cpu { color: #30d5c8; }
	.metrics-current.memory { color: #bc13fe; }

	.chart-area-canvas {
		height: 240px;
		background: #151c27;
		border: 1px solid #1f2937;
		border-radius: 6px;
		padding: 8px 8px 8px 4px;
		position: relative;
	}

	.chart-area-canvas canvas {
		width: 100% !important;
		height: 100% !important;
	}

	/* Network */
	.network-stats { display: flex; gap: 16px; padding-top: 12px; }

	.network-col { flex: 1; display: flex; flex-direction: column; gap: 4px; }
	.network-divider { width: 1px; background: rgba(255,255,255,0.06); }

	.network-label { font-size: 13px; color: #64748b; }
	.network-value-row { display: flex; align-items: baseline; gap: 4px; }
	.network-big { font-size: 14px; font-weight: 500; color: #cbd5e1; }

	.network-bar-track { height: 4px; background: rgba(255,255,255,0.06); border-radius: 2px; }
	.network-bar { height: 100%; border-radius: 2px; transition: width 0.5s ease; }

	/* Disk */
	.disk-stats { display: flex; flex-direction: column; gap: 8px; padding-top: 12px; }
	.disk-row { display: flex; justify-content: space-between; }
	.disk-label { font-size: 13px; color: #64748b; }
	.disk-value { font-size: 12px; color: #cbd5e1; }

	/* Logs Tab */
	.logs-toolbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 16px;
		margin-bottom: 0;
	}

	.log-search {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 16px 7px 40px;
		background: #121720;
		border-radius: 6px;
		position: relative;
		flex: 1;
		max-width: 448px;
	}

	.log-search svg {
		position: absolute;
		left: 16px;
	}

	.log-search input {
		background: none;
		border: none;
		outline: none;
		color: #cbd5e1;
		font-size: 12px;
		width: 100%;
	}

	.log-search input::placeholder { color: #475569; }

	.logs-controls {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.auto-scroll-toggle {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 13px;
		font-weight: 700;
		color: #64748b;
		cursor: pointer;
	}

	.switch {
		width: 36px;
		height: 20px;
		background: #334155;
		border-radius: 10px;
		position: relative;
		cursor: pointer;
		transition: background 0.2s;
	}

	.switch.on { background: #30d5c8; }

	.switch-thumb {
		width: 16px;
		height: 16px;
		background: white;
		border-radius: 50%;
		position: absolute;
		top: 2px;
		left: 2px;
		transition: left 0.2s;
	}

	.switch.on .switch-thumb { left: 18px; }

	.download-btn {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 16px;
		background: #151c27;
		border: 1px solid #1f2937;
		border-radius: 8px;
		color: #cbd5e1;
		font-size: 13px;
		font-weight: 700;
		cursor: pointer;
	}

	.download-btn:hover { background: #1f2937; }

	/* Terminal */
	.terminal {
		background: rgba(0, 0, 0, 0.3);
		border: 1px solid #1f2937;
		border-radius: 8px;
		overflow: hidden;
		flex: 1;
		display: flex;
		flex-direction: column;
	}

	.terminal-header {
		display: flex;
		align-items: center;
		padding: 8px 16px;
		background: #151c27;
		border-bottom: 1px solid rgba(255,255,255,0.04);
		gap: 16px;
	}

	.terminal-dots { display: flex; gap: 6px; }
	.dot { width: 8px; height: 8px; border-radius: 50%; }
	.dot.red { background: rgba(239,68,68,0.5); }
	.dot.yellow { background: rgba(234,179,8,0.5); }
	.dot.green { background: rgba(34,197,94,0.5); }

	.terminal-title { font-size: 10px; color: #64748b; }

	.terminal-body {
		padding: 15px 16px 16px;
		overflow-y: auto;
		flex: 1;
		max-height: 327px;
		display: flex;
		flex-direction: column;
		gap: 3px;
	}

	.log-line {
		display: flex;
		gap: 16px;
		font-size: 12px;
		line-height: 20px;
		font-family: monospace;
	}

	.log-ts { color: #475569; white-space: nowrap; flex-shrink: 0; }
	.log-level { font-weight: 700; white-space: nowrap; flex-shrink: 0; min-width: 40px; }
	.log-msg { color: #cbd5e1; word-break: break-all; }

	.log-empty {
		color: #475569;
		font-size: 12px;
		text-align: center;
		padding: 24px;
	}

	/* Footer */
	.modal-footer {
		flex-shrink: 0;
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 24px;
		background: #121720;
		border-top: 1px solid rgba(255,255,255,0.04);
	}

	.action-right { display: flex; gap: 12px; }

	.action-btn {
		padding: 8px 24px;
		border: none;
		border-radius: 8px;
		font-size: 11px;
		font-weight: 700;
		color: #d9d9d9;
		cursor: pointer;
	}

	.action-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.action-btn.danger { background: #ef3e5e; }
	.action-btn.danger:hover:not(:disabled) { background: #dc2626; }
	.action-btn.secondary { background: #334155; }
	.action-btn.secondary:hover:not(:disabled) { background: #475569; }
	.action-btn.accent { background: #30d5c8; color: #094b66; }
	.action-btn.accent:hover:not(:disabled) { background: #26b8ac; }
</style>
