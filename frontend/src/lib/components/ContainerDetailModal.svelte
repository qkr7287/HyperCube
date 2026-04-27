<script lang="ts">
	import { onMount, onDestroy, untrack } from 'svelte';
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

	function formatMemoryMB(bytes: number): string {
		return (bytes / 1048576).toFixed(1);
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
				<button class="tab" class:active={activeTab === 'metrics'} onclick={() => activeTab = 'metrics'}>메트릭</button>
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
								<InfoTooltip placement="bottom-start" text="지금 이 순간 컨테이너가 쓰고 있는 자원 한 컷이에요. 시간에 따른 추이는 위 '메트릭' 탭에서 그래프로 볼 수 있어요." />
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
				{/if}

			{:else if activeTab === 'metrics'}
				<!-- METRICS TAB -->
				{#if containerState !== 'running'}
					<div class="loading-state">컨테이너가 실행 중이 아닙니다.</div>
				{:else}
					{@const cpuPct = Number(metricsData?.cpu?.usage ?? 0)}
					{@const memPct = Number(metricsData?.memory?.percent ?? 0)}
					{@const netRxBytes = Number(metricsData?.network?.rx ?? 0)}
					{@const netTxBytes = Number(metricsData?.network?.tx ?? 0)}

					<div class="metrics-grid-top">
						<div class="metrics-card">
							<div class="metrics-card-header">
								<span class="metrics-card-title">CPU 사용률</span>
								<InfoTooltip
									placement="bottom-start"
									text="이 컨테이너가 호스트 CPU를 얼마나 쓰고 있는지예요. 100%면 단일 코어 한 개를 가득 쓰는 중이고, 다중 코어면 100%를 넘을 수도 있어요. 오래 높게 머물면 로직이 과부하라는 신호예요."
								/>
								<span class="metrics-current cpu">{cpuPct.toFixed(2)}%</span>
							</div>
							<MetricTrendChart
								{agentId}
								{accessToken}
								endpoint="/api/metrics/containers/"
								extraQuery={`container_id=${container?.shortId ?? (container?.id ?? '').slice(0, 12)}`}
								metricField="cpu_usage"
								liveValue={cpuPct}
								label="컨테이너 CPU 사용률 (%)"
								color="#30d5c8"
								unit="percent"
								defaultRange="10m"
							/>
						</div>
						<div class="metrics-card">
							<div class="metrics-card-header">
								<span class="metrics-card-title">메모리 사용률</span>
								<InfoTooltip
									placement="bottom-start"
									text="컨테이너에 할당된 메모리 중 실제 사용하는 비율이에요. 100%에 가까우면 OOM (메모리 부족으로 컨테이너가 죽을 위험)이 생길 수 있어요."
								/>
								<span class="metrics-current memory">{memPct.toFixed(1)}%</span>
							</div>
							<MetricTrendChart
								{agentId}
								{accessToken}
								endpoint="/api/metrics/containers/"
								extraQuery={`container_id=${container?.shortId ?? (container?.id ?? '').slice(0, 12)}`}
								metricField="memory_percent"
								liveValue={memPct}
								label="컨테이너 메모리 사용률 (%)"
								color="#8b5cf6"
								unit="percent"
								defaultRange="10m"
							/>
						</div>
					</div>
					<div class="metrics-grid-bottom">
						<div class="metrics-card">
							<div class="metrics-card-header">
								<span class="metrics-card-title muted">네트워크 트래픽</span>
								<InfoTooltip
									placement="bottom-start"
									text="컨테이너가 주고받은 네트워크 총량 (누적). Inbound는 받은 데이터, Outbound는 보낸 데이터예요. 숫자가 꾸준히 커지면 계속 트래픽이 오가는 중이고, 평평하면 통신이 없거나 적은 상태예요."
								/>
							</div>
							<div class="network-stats">
								<div class="network-col">
									<span class="network-label">수신</span>
									<div class="network-value-row">
										<span class="network-big">{formatBytes(netRxBytes)}</span>
									</div>
									<div class="network-bar-track"><div class="network-bar" style="width: {Math.min(netRxBytes / (netRxBytes + netTxBytes + 1) * 100, 100)}%; background: #30d5c8;"></div></div>
								</div>
								<div class="network-divider"></div>
								<div class="network-col">
									<span class="network-label">송신</span>
									<div class="network-value-row">
										<span class="network-big">{formatBytes(netTxBytes)}</span>
									</div>
									<div class="network-bar-track"><div class="network-bar" style="width: {Math.min(netTxBytes / (netRxBytes + netTxBytes + 1) * 100, 100)}%; background: #bc13fe;"></div></div>
								</div>
							</div>
						</div>
						<div class="metrics-card">
							<div class="metrics-card-header">
								<span class="metrics-card-title muted">디스크 I/O</span>
								<InfoTooltip
									placement="bottom-start"
									text="컨테이너가 디스크를 읽고 쓴 누적 양. READ는 읽은 데이터, WRITE는 쓴 데이터예요. 숫자가 꾸준히 올라가면 지금 디스크 접근 중이고, 멈춰 있으면 I/O가 없는 상태예요."
								/>
							</div>
							<div class="disk-stats">
								<div class="disk-row">
									<span class="disk-label">읽기</span>
									<span class="disk-value">{formatBytes(metricsData?.disk?.read || 0)}</span>
								</div>
								<div class="disk-row">
									<span class="disk-label">쓰기</span>
									<span class="disk-value">{formatBytes(metricsData?.disk?.write || 0)}</span>
								</div>
							</div>
						</div>
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
	.modal-metrics { width: min(1280px, 95vw); }
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
		padding: 24px;
		display: flex;
		flex-direction: column;
		gap: 32px;
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

	/* Metrics Tab */
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
