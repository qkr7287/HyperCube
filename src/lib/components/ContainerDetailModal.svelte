<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

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
		onClose = () => {},
		onStateChange = () => {},
	}: {
		container: Container | null;
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
	let metricsInterval: ReturnType<typeof setInterval> | null = null;

	// Logs data - raw string array like old project
	let logs: string[] = $state([]);
	let logSearchQuery = $state('');
	let autoScroll = $state(true);
	let autoRefreshLogs = $state(false);
	let logContainer: HTMLDivElement | undefined = $state(undefined);
	let logsInterval: ReturnType<typeof setInterval> | null = null;

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

	async function fetchDetails() {
		if (!container) return;
		try {
			const res = await fetch(`/api/containers/${container.id}`);
			const data = await res.json();
			if (data.success) {
				details = data.data;
				containerState = details.inspect?.State?.Status || container.state;
				containerStatus = details.inspect?.State?.Status || container.status;
			} else {
				errorMsg = data.error || 'Failed to fetch details';
			}
		} catch (e) {
			errorMsg = '컨테이너 정보를 가져오는데 실패했습니다.';
			console.error('Failed to fetch details:', e);
		}
	}

	async function fetchMetrics() {
		if (!container) return;
		// Use container.state for first call, containerState for subsequent
		const state = containerState || container?.state;
		if (state !== 'running') return;
		try {
			const res = await fetch(`/api/containers/${container.id}/metrics`);
			const data = await res.json();
			if (data.success) {
				metricsData = data.data;
				const cpuVal = metricsData.cpu?.usage || 0;
				const memVal = (metricsData.memory?.usage || 0) / 1048576;
				cpuHistory = [...cpuHistory.slice(-(MAX_HISTORY - 1)), cpuVal];
				memoryHistory = [...memoryHistory.slice(-(MAX_HISTORY - 1)), memVal];
			}
		} catch (e) {
			console.error('Failed to fetch metrics:', e);
		}
	}

	async function fetchLogs() {
		if (!container) return;
		try {
			const res = await fetch(`/api/containers/${container.id}/logs?tail=100`);
			const data = await res.json();
			if (data.success && data.data?.logs) {
				logs = data.data.logs;
			} else {
				logs = ['로그를 불러올 수 없습니다: ' + (data.error || '')];
			}
		} catch (e) {
			console.error('Failed to fetch logs:', e);
			logs = ['로그를 불러오는 중 오류가 발생했습니다.'];
		}
		if (autoScroll && logContainer) {
			setTimeout(() => { if (logContainer) logContainer.scrollTop = logContainer.scrollHeight; }, 50);
		}
	}

	function parseLogLine(line: string): { timestamp: string; level: string; message: string } {
		// ISO timestamp format
		const tsMatch = line.match(/^(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}[\.\d]*)/);
		// Nginx/Apache log format: [11/Mar/2026:09:26:42 +0000]
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
			const res = await fetch(`/api/containers/${container.id}/control`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ action }),
			});
			const data = await res.json();
			if (data.success) {
				await fetchDetails();
				onStateChange();
			} else {
				errorMsg = data.error || 'Control action failed';
			}
		} catch (e) {
			console.error('Control action failed:', e);
		} finally {
			controlLoading = '';
		}
	}

	function toggleAutoRefreshLogs() {
		autoRefreshLogs = !autoRefreshLogs;
		if (autoRefreshLogs) {
			logsInterval = setInterval(fetchLogs, 3000);
		} else if (logsInterval) {
			clearInterval(logsInterval);
			logsInterval = null;
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

	// Sparkline: handle 1+ data points
	function buildSparklinePath(history: number[], maxVal: number, width: number, height: number): string {
		if (history.length === 0) return '';
		const effectiveMax = maxVal > 0 ? maxVal : 1;
		const stepX = width / (MAX_HISTORY - 1);
		const offsetX = (MAX_HISTORY - history.length) * stepX;
		if (history.length === 1) {
			const y = height - (Math.min(history[0], effectiveMax) / effectiveMax) * height;
			// Draw a horizontal line at the current value
			return `M${offsetX.toFixed(1)},${y.toFixed(1)} L${width.toFixed(1)},${y.toFixed(1)}`;
		}
		return history.map((val, i) => {
			const x = offsetX + i * stepX;
			const y = height - (Math.min(val, effectiveMax) / effectiveMax) * height;
			return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
		}).join(' ');
	}

	function buildSparklineArea(history: number[], maxVal: number, width: number, height: number): string {
		if (history.length === 0) return '';
		const effectiveMax = maxVal > 0 ? maxVal : 1;
		const stepX = width / (MAX_HISTORY - 1);
		const offsetX = (MAX_HISTORY - history.length) * stepX;
		if (history.length === 1) {
			const y = height - (Math.min(history[0], effectiveMax) / effectiveMax) * height;
			return `M${offsetX.toFixed(1)},${y.toFixed(1)} L${width.toFixed(1)},${y.toFixed(1)} L${width.toFixed(1)},${height} L${offsetX.toFixed(1)},${height} Z`;
		}
		const path = history.map((val, i) => {
			const x = offsetX + i * stepX;
			const y = height - (Math.min(val, effectiveMax) / effectiveMax) * height;
			return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
		}).join(' ');
		const lastX = offsetX + (history.length - 1) * stepX;
		return `${path} L${lastX.toFixed(1)},${height} L${offsetX.toFixed(1)},${height} Z`;
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

		// Start metrics after details are loaded
		await fetchMetrics();
	}

	onMount(() => {
		loadData();
		metricsInterval = setInterval(fetchMetrics, 5000);
		document.addEventListener('keydown', handleKeydown);
	});

	onDestroy(() => {
		if (metricsInterval) clearInterval(metricsInterval);
		if (logsInterval) clearInterval(logsInterval);
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
				<button class="tab" class:active={activeTab === 'info'} onclick={() => activeTab = 'info'}>Info</button>
				<button class="tab" class:active={activeTab === 'metrics'} onclick={() => activeTab = 'metrics'}>Metrics</button>
				<button class="tab" class:active={activeTab === 'logs'} onclick={() => activeTab = 'logs'}>Logs</button>
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
						</div>
						<div class="info-card">
							<div class="info-grid">
								<div class="info-item">
									<span class="info-label">이름</span>
									<span class="info-value">{containerName}</span>
								</div>
								<div class="info-item">
									<span class="info-label">상태</span>
									<span class="info-value status" class:running={containerState === 'running'} class:stopped={containerState === 'exited' || containerState === 'dead'} class:paused={containerState === 'paused'}>
										{containerState}
									</span>
								</div>
								<div class="info-item full">
									<span class="info-label">ID</span>
									<span class="info-value mono">{details?.inspect?.Id || container.id}</span>
								</div>
								<div class="info-item">
									<span class="info-label">이미지</span>
									<span class="info-value">{container.image}</span>
								</div>
								<div class="info-item">
									<span class="info-label">생성일</span>
									<span class="info-value">{details?.inspect?.Created ? new Date(details.inspect.Created).toLocaleString('ko-KR') : '-'}</span>
								</div>
								<div class="info-item">
									<span class="info-label">시작 시각</span>
									<span class="info-value">{details?.inspect?.State?.StartedAt ? new Date(details.inspect.State.StartedAt).toLocaleString('ko-KR') : '-'}</span>
								</div>
							</div>
						</div>
					</section>

					{#if details?.inspect?.Config}
						<section class="section">
							<div class="section-title">
								<div class="section-dot"></div>
								<span>설정</span>
							</div>
							<div class="settings-grid">
								<div class="info-card compact">
									<span class="info-label">명령어</span>
									<span class="info-value">{details.inspect.Config.Cmd?.join(' ') || 'N/A'}</span>
								</div>
								<div class="info-card compact">
									<span class="info-label">작업 디렉토리</span>
									<span class="info-value">{details.inspect.Config.WorkingDir || 'N/A'}</span>
								</div>
							</div>
							<div class="info-card">
								<div class="env-header">
									<span class="info-label">환경 변수</span>
									{#if (details.inspect.Config.Env || []).length > 3}
										<button class="env-toggle" onclick={() => envExpanded = !envExpanded}>
											{envExpanded ? '접기' : `전체 보기 (${details.inspect.Config.Env.length})`}
										</button>
									{/if}
								</div>
								<div class="env-list">
									{#each (envExpanded ? (details.inspect.Config.Env || []) : (details.inspect.Config.Env || []).slice(0, 3)) as env}
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

					{#if details?.stats}
						<section class="section">
							<div class="section-title">
								<div class="section-dot"></div>
								<span>리소스 사용량</span>
							</div>
							<div class="resource-grid">
								<div class="resource-card">
									<span class="info-label">CPU 사용률</span>
									<span class="resource-value">{metricsData?.cpu?.usage?.toFixed(2) || '0.00'}%</span>
								</div>
								<div class="resource-card">
									<span class="info-label">메모리 사용량</span>
									<span class="resource-value">{metricsData?.memory ? formatMemoryMB(metricsData.memory.usage) : (details.stats.memory_stats ? formatBytes(details.stats.memory_stats.usage) : 'N/A')} <small class="resource-unit">{metricsData?.memory ? 'MB' : ''}</small></span>
								</div>
								<div class="resource-card">
									<span class="info-label">네트워크 (RX/TX)</span>
									<span class="resource-value plain">{metricsData?.network ? formatBytes(metricsData.network.rx) + ' / ' + formatBytes(metricsData.network.tx) : 'N/A'}</span>
								</div>
							</div>
						</section>
					{/if}
				{/if}

			{:else if activeTab === 'metrics'}
				<!-- METRICS TAB -->
				{#if containerState !== 'running'}
					<div class="loading-state">컨테이너가 실행 중이 아닙니다.</div>
				{:else if !metricsData}
					<div class="loading-state">메트릭 로딩 중...</div>
				{:else}
					<div class="metrics-grid-top">
						<div class="metrics-card">
							<div class="metrics-card-header">
								<span class="metrics-card-title">CPU Usage (%)</span>
								<span class="metrics-current cpu">{metricsData.cpu?.usage?.toFixed(2) || '0.00'}% Current</span>
							</div>
							<div class="chart-area">
								<svg width="100%" height="160" viewBox="0 0 400 160" preserveAspectRatio="none">
									{#each [0, 25, 50, 75, 100] as pct}
										<line x1="0" y1={160 - pct * 1.6} x2="400" y2={160 - pct * 1.6} stroke="rgba(255,255,255,0.04)" stroke-width="1"/>
									{/each}
									{#if cpuHistory.length >= 1}
										<path d={buildSparklineArea(cpuHistory, 100, 400, 160)} fill="rgba(48,213,200,0.15)" />
										<path d={buildSparklinePath(cpuHistory, 100, 400, 160)} fill="none" stroke="#30d5c8" stroke-width="2" />
									{/if}
								</svg>
							</div>
						</div>
						<div class="metrics-card">
							<div class="metrics-card-header">
								<span class="metrics-card-title">Memory Usage (MB)</span>
								<span class="metrics-current memory">{formatMemoryMB(metricsData.memory?.usage || 0)} MB</span>
							</div>
							<div class="chart-area">
								<svg width="100%" height="160" viewBox="0 0 400 160" preserveAspectRatio="none">
									{#each [0, 25, 50, 75, 100] as pct}
										<line x1="0" y1={160 - pct * 1.6} x2="400" y2={160 - pct * 1.6} stroke="rgba(255,255,255,0.04)" stroke-width="1"/>
									{/each}
									{#if memoryHistory.length >= 1}
										<path d={buildSparklineArea(memoryHistory, memLimitMB, 400, 160)} fill="rgba(188,19,254,0.15)" />
										<path d={buildSparklinePath(memoryHistory, memLimitMB, 400, 160)} fill="none" stroke="#bc13fe" stroke-width="2" />
									{/if}
								</svg>
							</div>
						</div>
					</div>
					<div class="metrics-grid-bottom">
						<div class="metrics-card">
							<div class="metrics-card-header">
								<span class="metrics-card-title muted">Network Traffic</span>
							</div>
							<div class="network-stats">
								<div class="network-col">
									<span class="network-label">Inbound</span>
									<div class="network-value-row">
										<span class="network-big">{formatBytes(metricsData.network?.rx || 0)}</span>
									</div>
									<div class="network-bar-track"><div class="network-bar" style="width: {Math.min((metricsData.network?.rx || 0) / ((metricsData.network?.rx || 0) + (metricsData.network?.tx || 0) + 1) * 100, 100)}%; background: #30d5c8;"></div></div>
								</div>
								<div class="network-divider"></div>
								<div class="network-col">
									<span class="network-label">Outbound</span>
									<div class="network-value-row">
										<span class="network-big">{formatBytes(metricsData.network?.tx || 0)}</span>
									</div>
									<div class="network-bar-track"><div class="network-bar" style="width: {Math.min((metricsData.network?.tx || 0) / ((metricsData.network?.rx || 0) + (metricsData.network?.tx || 0) + 1) * 100, 100)}%; background: #bc13fe;"></div></div>
								</div>
							</div>
						</div>
						<div class="metrics-card">
							<div class="metrics-card-header">
								<span class="metrics-card-title muted">Disk I/O</span>
							</div>
							<div class="disk-stats">
								<div class="disk-row">
									<span class="disk-label">READ</span>
									<span class="disk-value">{formatBytes(metricsData.disk?.read || 0)}</span>
								</div>
								<div class="disk-row">
									<span class="disk-label">WRITE</span>
									<span class="disk-value">{formatBytes(metricsData.disk?.write || 0)}</span>
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
						<input type="text" placeholder="Search logs..." bind:value={logSearchQuery} />
					</div>
					<div class="logs-controls">
						<label class="auto-scroll-toggle">
							<span>Auto-refresh</span>
							<div class="switch" class:on={autoRefreshLogs} onclick={toggleAutoRefreshLogs}>
								<div class="switch-thumb"></div>
							</div>
						</label>
						<label class="auto-scroll-toggle">
							<span>Auto-scroll</span>
							<div class="switch" class:on={autoScroll} onclick={() => autoScroll = !autoScroll}>
								<div class="switch-thumb"></div>
							</div>
						</label>
						<button class="download-btn" onclick={downloadLogs}>
							<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
							</svg>
							Download
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
						<span class="terminal-title">bash — log-viewer — {filteredLogs.length} lines</span>
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
				<button class="action-btn danger" onclick={() => handleControl('stop')} disabled={!!controlLoading}>
					{controlLoading === 'stop' ? '처리 중...' : '중지'}
				</button>
				<div class="action-right">
					<button class="action-btn secondary" onclick={() => handleControl('restart')} disabled={!!controlLoading}>
						{controlLoading === 'restart' ? '처리 중...' : '재시작'}
					</button>
					<button class="action-btn secondary" onclick={() => handleControl('pause')} disabled={!!controlLoading}>
						{controlLoading === 'pause' ? '처리 중...' : '일시정지'}
					</button>
				</div>
			{:else if containerState === 'paused'}
				<button class="action-btn danger" onclick={() => handleControl('stop')} disabled={!!controlLoading}>
					{controlLoading === 'stop' ? '처리 중...' : '중지'}
				</button>
				<div class="action-right">
					<button class="action-btn accent" onclick={() => handleControl('unpause')} disabled={!!controlLoading}>
						{controlLoading === 'unpause' ? '처리 중...' : '재개'}
					</button>
				</div>
			{:else}
				<button class="action-btn accent" onclick={() => handleControl('start')} disabled={!!controlLoading}>
					{controlLoading === 'start' ? '처리 중...' : '시작'}
				</button>
				<div class="action-right">
					<button class="action-btn secondary" onclick={() => handleControl('restart')} disabled={!!controlLoading}>
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
		width: 768px;
		max-height: 90vh;
		background: #0d1117;
		border: 1px solid #30d5c8;
		border-radius: 12px;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.modal-metrics { width: 896px; }
	.modal-logs { width: 1024px; }

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
		grid-template-columns: 1fr 1fr;
		gap: 24px;
	}

	.metrics-card {
		background: #121720;
		border-radius: 8px;
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.metrics-card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.metrics-card-title { font-size: 13px; font-weight: 700; color: #cbd5e1; }
	.metrics-card-title.muted { color: #64748b; }

	.metrics-current { font-size: 12px; }
	.metrics-current.cpu { color: #30d5c8; }
	.metrics-current.memory { color: #bc13fe; }

	.chart-area {
		height: 160px;
		background: #151c27;
		border: 1px solid #1f2937;
		border-radius: 4px;
		overflow: hidden;
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
