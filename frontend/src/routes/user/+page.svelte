<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { base } from '$app/paths';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import NewRequestModal from '$lib/components/NewRequestModal.svelte';
	import Pill from '$lib/components/Pill.svelte';
	import { statusEvents, type AgentStatusEvent } from '$lib/stores/global-events';
	import {
		formatDateTime,
		formatRelativeTime,
		statusLabel,
		statusTone,
	} from '$lib/utils/container-dashboard';

	type RequestRow = {
		id: string;
		action: string;
		status: string;
		template_name?: string | null;
		target_agent_hostname?: string | null;
		target_container?: string | null;
		target_container_name?: string | null;
		custom_name?: string;
		progress_message?: string;
		progress_percent?: number | null;
		review_note?: string;
		created_at: string;
	};

	type MyContainer = {
		container_id: string;
		name: string;
		image: string;
		status: string;
		last_seen: string;
		agent_hostname?: string;
		template_name?: string | null;
		allocated_gpu_slice_ids?: (string | number)[];
		custom_ports?: Record<string, unknown> | null;
		workspace_enabled?: boolean;
		workspace_kind?: string | null;
		workspace_host_port?: number | null;
		workspace_runtime_expires_at?: string | null;
		mounted_model_versions?: Array<{
			id: string;
			asset_name: string;
			asset_slug: string;
			version: string;
		}>;
	};

	type TabKey = 'containers' | 'history';
	type ContainerFilter = 'all' | 'running' | 'workspace' | 'stopped';
	type HistoryFilter = 'all' | 'deployed' | 'rejected' | 'others';

	const ACTIVE_STATUSES = new Set(['pending', 'approved', 'deploying']);
	const STOPPED_STATUSES = new Set(['exited', 'stopped', 'dead', 'paused', 'created']);

	let activeTab = $state<TabKey>('containers');
	let containerFilter = $state<ContainerFilter>('all');
	let historyFilter = $state<HistoryFilter>('all');
	let search = $state('');
	let containers = $state<MyContainer[]>([]);
	let requests = $state<RequestRow[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let newModalOpen = $state(false);
	let openingId = $state('');
	let errorMsg = $state('');
	let username = $state('');
	let toasts = $state<Array<{ id: number; kind: 'success' | 'error' | 'info'; text: string }>>([]);
	let toastSeq = 0;
	let sortField = $state<'name' | 'status' | 'cpu' | 'mem' | 'last_seen'>('last_seen');
	let sortDir = $state<'asc' | 'desc'>('desc');
	let historySortField = $state<'name' | 'status' | 'action' | 'created_at'>('created_at');
	let historySortDir = $state<'asc' | 'desc'>('desc');
	let historySearch = $state('');

	function pushToast(kind: 'success' | 'error' | 'info', text: string) {
		const id = ++toastSeq;
		toasts = [...toasts, { id, kind, text }];
		setTimeout(() => {
			toasts = toasts.filter((t) => t.id !== id);
		}, 4000);
	}

	function dismissToast(id: number) {
		toasts = toasts.filter((t) => t.id !== id);
	}
	let pollTimer: ReturnType<typeof setInterval> | null = null;
	let urlSyncTimer: ReturnType<typeof setTimeout> | null = null;

	const ROW_HEIGHT = 44;
	let containerListEl = $state<HTMLElement | null>(null);
	let historyListEl = $state<HTMLElement | null>(null);
	let containerListHeight = $state(0);
	let historyListHeight = $state(0);
	let liveEvents = $state<AgentStatusEvent[]>([]);
	let cpuHistory = $state<Record<string, number[]>>({});
	let memHistory = $state<Record<string, number[]>>({});
	let metricsFetched = false;

	const unsubEvents = statusEvents.subscribe((value) => {
		liveEvents = value;
	});

	async function fetchSparklines(t: string) {
		const targets = containers.slice(0, 12);
		await Promise.all(
			targets.map(async (c) => {
				try {
					const res = await fetch(
						`${base}/api/my-containers/${c.container_id}/metrics-history/?range=1h&limit=30`,
						{ headers: { Authorization: `Bearer ${t}` } },
					);
					if (!res.ok) return;
					const json = await res.json();
					const arr: any[] = Array.isArray(json)
						? json
						: Array.isArray(json?.data)
							? json.data
							: (json?.data?.points ?? json?.points ?? []);
					const cpuSeries = arr
						.map((p) => Number(p.cpu_usage ?? p.cpu_percent ?? p.cpu ?? 0))
						.filter((n) => Number.isFinite(n));
					const memSeries = arr
						.map((p) => Number(p.memory_percent ?? p.mem_percent ?? 0))
						.filter((n) => Number.isFinite(n));
					if (cpuSeries.length > 0) {
						cpuHistory = { ...cpuHistory, [c.container_id]: cpuSeries };
					}
					if (memSeries.length > 0) {
						memHistory = { ...memHistory, [c.container_id]: memSeries };
					}
				} catch {
					/* ignore per-container failure */
				}
			}),
		);
	}

	function sparklinePoints(series: number[], width = 60, height = 16): { line: string; area: string } {
		if (!series || series.length === 0) return { line: '', area: '' };
		const max = Math.max(...series, 5);
		const min = Math.min(...series, 0);
		const range = Math.max(max - min, 1);
		const step = series.length > 1 ? width / (series.length - 1) : width;
		const pts = series.map((v, i) => {
			const x = series.length > 1 ? i * step : width / 2;
			const y = height - ((v - min) / range) * height;
			return { x, y };
		});
		const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
		const area = `${line} L ${pts[pts.length - 1].x.toFixed(1)} ${height} L ${pts[0].x.toFixed(1)} ${height} Z`;
		return { line, area };
	}

	$effect(() => {
		if (!containerListEl) return;
		const ro = new ResizeObserver(() => {
			containerListHeight = containerListEl?.clientHeight ?? 0;
		});
		ro.observe(containerListEl);
		return () => ro.disconnect();
	});

	$effect(() => {
		if (!historyListEl) return;
		const ro = new ResizeObserver(() => {
			historyListHeight = historyListEl?.clientHeight ?? 0;
		});
		ro.observe(historyListEl);
		return () => ro.disconnect();
	});

	const pageHelp = `요청한 자원을 한 곳에서 관리합니다.

KPI — 컨테이너·요청·자원 합계
진행 중 요청 — 승인 대기·배포 중 작업의 진행도
컨테이너 탭 — 내가 보유한 컨테이너 (필터·검색)
요청 이력 탭 — 완료·반려·취소된 과거 요청`;
	const kpiContainerHelp = `실행 중인 컨테이너 / 전체 보유 컨테이너 수입니다.`;
	const kpiRequestHelp = `대기·승인·배포 중인 요청 수입니다.`;
	const kpiGpuHelp = `내 컨테이너에 할당된 GPU 슬라이스 합계입니다.`;
	const kpiWorkspaceHelp = `workspace_enabled 인 컨테이너 수 (Jupyter 등 작업 환경).`;
	const activeBannerHelp = `아직 끝나지 않은 요청들의 실시간 진행 상황입니다. 4초마다 자동 갱신됩니다.`;
	const historyTabHelp = `완료·반려·실패한 과거 요청의 이력입니다. 배포 완료 항목은 컨테이너로 바로 이동할 수 있습니다.`;

	function decodeJwt(t: string): Record<string, unknown> {
		try {
			return JSON.parse(atob(t.split('.')[1]));
		} catch {
			return {};
		}
	}

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function fetchJson(path: string, t: string) {
		try {
			const res = await fetch(`${base}${path}`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (!res.ok) return null;
			return await res.json();
		} catch {
			return null;
		}
	}

	async function load(opts: { silent?: boolean } = {}) {
		const t = token();
		if (!t) return;
		if (opts.silent) refreshing = true;
		else loading = containers.length === 0 && requests.length === 0;
		const [reqJson, contJson] = await Promise.all([
			fetchJson('/api/requests/?page_size=200&ordering=-created_at', t),
			fetchJson('/api/my-containers/?page_size=200&ordering=-last_seen', t),
		]);
		if (reqJson) requests = reqJson?.data?.results ?? [];
		if (contJson) containers = contJson?.data?.results ?? [];
		loading = false;
		refreshing = false;
		syncPolling();
		if (!metricsFetched && containers.length > 0) {
			metricsFetched = true;
			fetchSparklines(t);
		}
	}

	let pollMode = $state<'idle' | 'active'>('idle');

	function syncPolling() {
		const hasActive = requests.some((r) => ACTIVE_STATUSES.has(r.status));
		const next: 'idle' | 'active' = hasActive ? 'active' : 'idle';
		if (next === pollMode && pollTimer) return;
		if (pollTimer) clearInterval(pollTimer);
		pollMode = next;
		const interval = hasActive ? 4000 : 60000;
		pollTimer = setInterval(() => load({ silent: true }), interval);
	}

	function openContainer(containerId: string) {
		goto(`${base}/user/containers/${containerId}`);
	}

	async function openWorkspace(c: MyContainer, event?: MouseEvent) {
		event?.stopPropagation();
		const t = token();
		if (!t || openingId) return;
		openingId = c.container_id;
		errorMsg = '';
		try {
			const res = await fetch(`${base}/api/workspaces/${c.container_id}/open/`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${t}` },
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || json?.error || `HTTP ${res.status}`);
			const url = json.data?.url;
			if (url) {
				window.open(`${base}${url}`, '_blank', 'noopener,noreferrer');
				pushToast('success', `${c.name} Jupyter를 새 탭으로 열었습니다.`);
			} else {
				pushToast('error', 'Jupyter URL 응답이 비어있습니다.');
			}
		} catch (error: any) {
			const msg = error?.message || 'Jupyter 열기에 실패했습니다.';
			errorMsg = msg;
			pushToast('error', msg);
		} finally {
			openingId = '';
		}
	}

	function requestDisplayName(r: RequestRow): string {
		if (r.custom_name) return r.custom_name;
		if (r.target_container_name) return r.target_container_name;
		if (r.target_container) {
			const prefix = r.action === 'delete' ? '삭제' : '대상';
			return `${prefix}: ${String(r.target_container).slice(0, 12)}`;
		}
		if (r.action === 'delete') {
			return `삭제 요청 #${String(r.id).slice(0, 8)}`;
		}
		return `요청 #${String(r.id).slice(0, 8)}`;
	}

	function portList(c: MyContainer): string {
		const ports = c.custom_ports;
		if (!ports) return '';
		if (Array.isArray(ports)) {
			const slice = ports.slice(0, 3) as Array<{ host?: number | string; container?: number | string }>;
			if (!slice.length) return '';
			return slice
				.map((p) => String(p?.host ?? p?.container ?? '').trim())
				.filter((s) => s && s !== '0')
				.join(', ');
		}
		if (typeof ports !== 'object') return '';
		const entries = Object.entries(ports).slice(0, 3);
		if (!entries.length) return '';
		return entries
			.map(([k]) => k.split('/')[0])
			.filter((s) => s && s !== '0')
			.join(', ');
	}

	function isStopped(c: MyContainer): boolean {
		return STOPPED_STATUSES.has(c.status);
	}

	function dismissError() {
		errorMsg = '';
	}

	let activeRequests = $derived(requests.filter((r) => ACTIVE_STATUSES.has(r.status)));
	let historyRequests = $derived(requests.filter((r) => !ACTIVE_STATUSES.has(r.status)));

	let totalCount = $derived(containers.length);
	let runningCount = $derived(containers.filter((c) => c.status === 'running').length);
	let workspaceCount = $derived(containers.filter((c) => c.workspace_enabled).length);
	let stoppedCount = $derived(containers.filter((c) => isStopped(c)).length);
	let gpuSliceCount = $derived(
		containers.reduce((sum, c) => sum + (c.allocated_gpu_slice_ids?.length ?? 0), 0),
	);

	function lastValue(map: Record<string, number[]>, id: string): number {
		const s = map[id];
		return s && s.length ? s[s.length - 1] : 0;
	}

	function compareContainers(a: MyContainer, b: MyContainer): number {
		const dir = sortDir === 'asc' ? 1 : -1;
		switch (sortField) {
			case 'name':
				return a.name.localeCompare(b.name) * dir;
			case 'status':
				return a.status.localeCompare(b.status) * dir;
			case 'cpu':
				return (lastValue(cpuHistory, a.container_id) - lastValue(cpuHistory, b.container_id)) * dir;
			case 'mem':
				return (lastValue(memHistory, a.container_id) - lastValue(memHistory, b.container_id)) * dir;
			case 'last_seen':
			default:
				return (new Date(a.last_seen).getTime() - new Date(b.last_seen).getTime()) * dir;
		}
	}

	function setSort(field: typeof sortField) {
		if (sortField === field) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDir = field === 'name' || field === 'status' ? 'asc' : 'desc';
		}
	}

	let filteredContainers = $derived(
		containers
			.filter((c) => {
				if (containerFilter === 'running' && c.status !== 'running') return false;
				if (containerFilter === 'workspace' && !c.workspace_enabled) return false;
				if (containerFilter === 'stopped' && !isStopped(c)) return false;
				const kw = search.trim().toLowerCase();
				if (!kw) return true;
				return [c.name, c.image, c.agent_hostname, c.template_name].some((v) =>
					String(v ?? '').toLowerCase().includes(kw),
				);
			})
			.slice()
			.sort(compareContainers),
	);

	function compareHistory(a: RequestRow, b: RequestRow): number {
		const dir = historySortDir === 'asc' ? 1 : -1;
		switch (historySortField) {
			case 'name':
				return requestDisplayName(a).localeCompare(requestDisplayName(b)) * dir;
			case 'status':
				return a.status.localeCompare(b.status) * dir;
			case 'action':
				return a.action.localeCompare(b.action) * dir;
			case 'created_at':
			default:
				return (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * dir;
		}
	}

	function setHistorySort(field: typeof historySortField) {
		if (historySortField === field) {
			historySortDir = historySortDir === 'asc' ? 'desc' : 'asc';
		} else {
			historySortField = field;
			historySortDir = field === 'created_at' ? 'desc' : 'asc';
		}
	}

	let filteredHistory = $derived(
		historyRequests
			.filter((r) => {
				if (historyFilter === 'deployed' && r.status !== 'deployed') return false;
				if (historyFilter === 'rejected' && r.status !== 'rejected') return false;
				if (historyFilter === 'others' && (r.status === 'deployed' || r.status === 'rejected')) return false;
				const kw = historySearch.trim().toLowerCase();
				if (!kw) return true;
				return [requestDisplayName(r), r.template_name, r.target_agent_hostname, r.review_note].some(
					(v) => String(v ?? '').toLowerCase().includes(kw),
				);
			})
			.slice()
			.sort(compareHistory),
	);

	const MIN_VISUAL_ROWS = 6;
	let containerEmptyRows = $derived(
		Math.max(0, Math.min(MIN_VISUAL_ROWS, Math.floor(containerListHeight / ROW_HEIGHT)) - filteredContainers.length),
	);
	let historyEmptyRows = $derived(
		Math.max(0, Math.min(MIN_VISUAL_ROWS, Math.floor(historyListHeight / ROW_HEIGHT)) - filteredHistory.length),
	);

	let sidePanelEmpty = $derived(activeRequests.length === 0 && liveEvents.length === 0);

	let historyCounts = $derived({
		all: historyRequests.length,
		deployed: historyRequests.filter((r) => r.status === 'deployed').length,
		rejected: historyRequests.filter((r) => r.status === 'rejected').length,
		others: historyRequests.filter((r) => r.status !== 'deployed' && r.status !== 'rejected').length,
	});

	function setTab(tab: TabKey) {
		activeTab = tab;
		queueUrlSync();
	}

	function setContainerFilter(f: ContainerFilter) {
		containerFilter = f;
		queueUrlSync();
	}

	function setHistoryFilter(f: HistoryFilter) {
		historyFilter = f;
		queueUrlSync();
	}

	function queueUrlSync() {
		if (!browser) return;
		if (urlSyncTimer) clearTimeout(urlSyncTimer);
		urlSyncTimer = setTimeout(() => {
			const params = new URLSearchParams();
			if (activeTab !== 'containers') params.set('tab', activeTab);
			if (activeTab === 'containers' && containerFilter !== 'all') params.set('filter', containerFilter);
			if (activeTab === 'history' && historyFilter !== 'all') params.set('history', historyFilter);
			const qs = params.toString();
			const next = `${location.pathname}${qs ? '?' + qs : ''}`;
			history.replaceState({}, '', next);
		}, 80);
	}

	onMount(() => {
		const t = token();
		if (t) username = String(decodeJwt(t).username ?? '');
		const u = $page.url;
		const tab = u.searchParams.get('tab');
		if (tab === 'history') activeTab = 'history';
		const filter = u.searchParams.get('filter');
		if (filter === 'running' || filter === 'workspace' || filter === 'stopped') {
			containerFilter = filter;
		}
		const hist = u.searchParams.get('history');
		if (hist === 'deployed' || hist === 'rejected' || hist === 'others') {
			historyFilter = hist;
		}
		load();
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
		if (urlSyncTimer) clearTimeout(urlSyncTimer);
		unsubEvents();
	});
</script>

<div class="page">
	<section class="hero">
		<div class="hero-left">
			<div class="title-row">
				<h1>{username || 'user'}<span class="title-suffix">의 작업공간</span></h1>
				<InfoTooltip text={pageHelp} label="페이지 도움말" placement="bottom-start" maxWidth={420} />
			</div>
			<div class="kpi-inline">
				<span class="kpi-pill" title="실행 중 / 전체 컨테이너">
					<span class="kpi-pill-dot running"></span>
					<span class="kpi-pill-num">{runningCount} / {totalCount}</span>
					<span class="kpi-pill-label">컨테이너</span>
				</span>
				<span class="kpi-pill" title="대기·승인·배포 중 요청">
					<span class="kpi-pill-dot" class:warn={activeRequests.length > 0}></span>
					<span class="kpi-pill-num">{activeRequests.length}</span>
					<span class="kpi-pill-label">진행 요청</span>
				</span>
				<span class="kpi-pill" title="GPU 슬라이스 합계">
					<span class="kpi-pill-num">{gpuSliceCount}</span>
					<span class="kpi-pill-label">GPU</span>
				</span>
				<span class="kpi-pill" title="활성화된 워크스페이스">
					<span class="kpi-pill-num">{workspaceCount}</span>
					<span class="kpi-pill-label">워크스페이스</span>
				</span>
			</div>
		</div>
		<div class="hero-actions">
			<button class="ghost-btn" onclick={() => load({ silent: true })} disabled={refreshing || loading}>
				<span class="btn-spinner" class:spinning={refreshing}></span>
				{refreshing ? '갱신 중…' : '새로고침'}
			</button>
			<button class="new-btn" onclick={() => (newModalOpen = true)}>+ 새 요청</button>
		</div>
	</section>

	<nav class="page-tabs" aria-label="페이지 탭">
		<button class:active={activeTab === 'containers'} onclick={() => setTab('containers')}>
			컨테이너 <Pill tone="var(--text-secondary)" size="md" minWidth="28px">{totalCount}</Pill>
		</button>
		<button class:active={activeTab === 'history'} onclick={() => setTab('history')}>
			요청 이력 <Pill tone="var(--text-secondary)" size="md" minWidth="28px">{historyRequests.length}</Pill>
			<InfoTooltip text={historyTabHelp} label="요청 이력 도움말" placement="bottom-start" />
		</button>
	</nav>

	<div class="main-grid" class:no-side={sidePanelEmpty}>
		<section class="main-content">

	{#if activeTab === 'containers'}
		<section class="tab-toolbar">
			<div class="filter-chips" role="tablist">
				<button class:active={containerFilter === 'all'} onclick={() => setContainerFilter('all')}>전체 <span class="chip-num">{totalCount}</span></button>
				<button class:active={containerFilter === 'running'} onclick={() => setContainerFilter('running')}>실행 중 <span class="chip-num">{runningCount}</span></button>
				<button class:active={containerFilter === 'workspace'} onclick={() => setContainerFilter('workspace')}>워크스페이스 <span class="chip-num">{workspaceCount}</span></button>
				<button class:active={containerFilter === 'stopped'} onclick={() => setContainerFilter('stopped')}>중지됨 <span class="chip-num">{stoppedCount}</span></button>
			</div>
			<input class="search-input" bind:value={search} type="text" placeholder="이름·이미지·서버·템플릿 검색" />
		</section>

		{#if loading && containers.length === 0}
			<div class="state">불러오는 중…</div>
		{:else if filteredContainers.length === 0}
			<div class="state empty">
				{#if containers.length === 0}
					<h3>아직 컨테이너가 없습니다</h3>
					<p>첫 요청을 만들어 배포해 보세요.</p>
					<button class="new-btn" onclick={() => (newModalOpen = true)}>+ 첫 요청 만들기</button>
				{:else}
					<h3>조건에 맞는 컨테이너가 없습니다</h3>
					<p>필터를 바꾸거나 검색어를 지워보세요.</p>
				{/if}
			</div>
		{:else}
			<div class="container-table">
				<div class="container-head">
					<button class="th sortable" class:active={sortField === 'status'} onclick={() => setSort('status')}>
						상태{sortField === 'status' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</button>
					<button class="th sortable" class:active={sortField === 'name'} onclick={() => setSort('name')}>
						이름 / 이미지{sortField === 'name' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</button>
					<span class="th">서버 · 템플릿</span>
					<span class="th">자원</span>
					<button class="th sortable" class:active={sortField === 'cpu'} onclick={() => setSort('cpu')}>
						CPU (1h){sortField === 'cpu' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</button>
					<button class="th sortable" class:active={sortField === 'mem'} onclick={() => setSort('mem')}>
						MEM (1h){sortField === 'mem' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</button>
					<button class="th sortable" class:active={sortField === 'last_seen'} onclick={() => setSort('last_seen')}>
						최근{sortField === 'last_seen' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</button>
					<span class="th"></span>
				</div>
				<ul class="container-list" bind:this={containerListEl}>
					{#each filteredContainers as c (c.container_id)}
						<li class="container-row" onclick={() => openContainer(c.container_id)} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && openContainer(c.container_id)}>
							<span class="row-status">
								<span class="dot" class:running={c.status === 'running'} aria-hidden="true"></span>
								<Pill tone={statusTone(c.status)} size="md" minWidth="70px">{statusLabel(c.status)}</Pill>
							</span>
							<div class="row-name">
								<strong title={c.name}>{c.name}</strong>
								<span class="row-image" title={c.image}>{c.image}</span>
							</div>
							<div class="row-host">
								<span title={c.agent_hostname ?? ''}>{c.agent_hostname ?? '-'}</span>
								<span class="row-template" title={c.template_name ?? ''}>{c.template_name ?? '템플릿 없음'}</span>
							</div>
							<div class="row-resources">
								{#if c.workspace_enabled && c.workspace_host_port}
									<Pill tone="var(--accent)" size="md" mono truncate>{c.workspace_kind ?? 'ws'} :{c.workspace_host_port}</Pill>
								{:else if portList(c)}
									<Pill tone="var(--accent)" size="md" mono truncate>{portList(c)}</Pill>
								{:else}
									<Pill tone="var(--text-muted)" size="md" mono>—</Pill>
								{/if}
								{#if c.allocated_gpu_slice_ids && c.allocated_gpu_slice_ids.length > 0}
									<Pill tone="#a5b4fc" size="md" title="GPU 슬라이스 {c.allocated_gpu_slice_ids.length}개">GPU ×{c.allocated_gpu_slice_ids.length}</Pill>
								{/if}
								{#if c.mounted_model_versions && c.mounted_model_versions.length > 0}
									{#each c.mounted_model_versions.slice(0, 1) as mv (mv.id)}
										<Pill tone="#93c5fd" size="md" truncate maxWidth="140px" title="{mv.asset_name} · v{mv.version}">{mv.asset_name}</Pill>
									{/each}
									{#if c.mounted_model_versions.length > 1}
										<Pill tone="var(--text-muted)" size="md">+{c.mounted_model_versions.length - 1}</Pill>
									{/if}
								{/if}
							</div>
							<span class="row-spark">
								{#if cpuHistory[c.container_id]}
									{@const series = cpuHistory[c.container_id]}
									{@const sMax = Math.max(...series)}
									{#if series.length >= 3 && sMax > 1}
										{@const sp = sparklinePoints(series, 60, 16)}
										<svg viewBox="0 0 60 16" preserveAspectRatio="none" class="spark-svg">
											<line x1="0" y1="15" x2="60" y2="15" stroke="rgba(100,116,139,0.32)" stroke-width="0.6" stroke-dasharray="2 2" />
											<path d={sp.area} fill="rgba(77,191,179,0.18)" stroke="none" />
											<path d={sp.line} fill="none" stroke="#4dbfb3" stroke-width="1.4" />
										</svg>
									{:else}
										<span class="spark-flat" aria-hidden="true"></span>
									{/if}
									<span class="spark-num">{(series[series.length - 1] ?? 0).toFixed(0)}%</span>
								{:else}
									<span class="spark-pending">—</span>
								{/if}
							</span>
							<span class="row-spark">
								{#if memHistory[c.container_id]}
									{@const series = memHistory[c.container_id]}
									{@const sMax = Math.max(...series)}
									{#if series.length >= 3 && sMax > 1}
										{@const sp = sparklinePoints(series, 60, 16)}
										<svg viewBox="0 0 60 16" preserveAspectRatio="none" class="spark-svg">
											<line x1="0" y1="15" x2="60" y2="15" stroke="rgba(100,116,139,0.32)" stroke-width="0.6" stroke-dasharray="2 2" />
											<path d={sp.area} fill="rgba(165,180,252,0.18)" stroke="none" />
											<path d={sp.line} fill="none" stroke="#a5b4fc" stroke-width="1.4" />
										</svg>
									{:else}
										<span class="spark-flat mem" aria-hidden="true"></span>
									{/if}
									<span class="spark-num mem">{(series[series.length - 1] ?? 0).toFixed(0)}%</span>
								{:else}
									<span class="spark-pending">—</span>
								{/if}
							</span>
							<span class="row-time">{formatRelativeTime(c.last_seen)}</span>
							<div class="row-actions" onclick={(e) => e.stopPropagation()} role="presentation">
								<button class="row-action ghost" onclick={() => openContainer(c.container_id)} title="모니터링 대시보드 열기">모니터링</button>
								{#if c.workspace_enabled && c.workspace_host_port}
									<button
										class="row-action primary"
										onclick={(e) => openWorkspace(c, e)}
										disabled={openingId === c.container_id}
										title="Jupyter 워크스페이스 열기"
									>
										{openingId === c.container_id ? '여는 중…' : 'Jupyter'}
									</button>
								{:else}
									<span class="row-action-placeholder" aria-hidden="true"></span>
								{/if}
							</div>
						</li>
					{/each}
					{#each Array(containerEmptyRows) as _, i (i)}
						<li class="container-row empty-row" aria-hidden="true">
							<span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span>
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	{:else}
		<section class="tab-toolbar">
			<div class="filter-chips">
				<button class:active={historyFilter === 'all'} onclick={() => setHistoryFilter('all')}>전체 <span class="chip-num">{historyCounts.all}</span></button>
				<button class:active={historyFilter === 'deployed'} onclick={() => setHistoryFilter('deployed')}>완료 <span class="chip-num">{historyCounts.deployed}</span></button>
				<button class:active={historyFilter === 'rejected'} onclick={() => setHistoryFilter('rejected')}>반려 <span class="chip-num">{historyCounts.rejected}</span></button>
				<button class:active={historyFilter === 'others'} onclick={() => setHistoryFilter('others')}>기타 <span class="chip-num">{historyCounts.others}</span></button>
			</div>
			<input class="search-input" bind:value={historySearch} type="text" placeholder="이름·템플릿·서버·검토 메모 검색" />
		</section>

		{#if loading && requests.length === 0}
			<div class="state">불러오는 중…</div>
		{:else if filteredHistory.length === 0}
			<div class="state empty">
				<h3>요청 이력이 없습니다</h3>
				<p>완료·반려·취소된 과거 요청이 여기 표시됩니다.</p>
			</div>
		{:else}
			<div class="history-table">
				<div class="history-head">
					<button class="th sortable" class:active={historySortField === 'action'} onclick={() => setHistorySort('action')}>
						유형{historySortField === 'action' ? (historySortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</button>
					<button class="th sortable" class:active={historySortField === 'name'} onclick={() => setHistorySort('name')}>
						이름{historySortField === 'name' ? (historySortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</button>
					<button class="th sortable" class:active={historySortField === 'status'} onclick={() => setHistorySort('status')}>
						상태{historySortField === 'status' ? (historySortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</button>
					<span class="th">템플릿</span>
					<span class="th">서버</span>
					<span class="th">검토 메모</span>
					<button class="th sortable" class:active={historySortField === 'created_at'} onclick={() => setHistorySort('created_at')}>
						요청 시각{historySortField === 'created_at' ? (historySortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</button>
					<span class="th"></span>
				</div>
				<ul class="history-list" bind:this={historyListEl}>
					{#each filteredHistory as r (r.id)}
						<li class="history-row">
							<span class="h-action-cell">
								<Pill
									tone={r.action === 'create' ? '#8ed4a8' : r.action === 'delete' ? '#fca5a5' : 'var(--text-secondary)'}
									size="md"
									minWidth="46px"
								>
									{r.action === 'create' ? '생성' : r.action === 'delete' ? '삭제' : r.action}
								</Pill>
							</span>
							<strong class="h-name" title={requestDisplayName(r)}>{requestDisplayName(r)}</strong>
							<span class="h-status-cell">
								<Pill tone={statusTone(r.status)} size="md" minWidth="70px">{statusLabel(r.status)}</Pill>
							</span>
							<span class="h-cell" title={r.template_name ?? ''}>{r.template_name ?? '-'}</span>
							<span class="h-cell" title={r.target_agent_hostname ?? ''}>{r.target_agent_hostname ?? '-'}</span>
							<span class="h-memo" title={r.review_note ?? ''}>{r.review_note || '-'}</span>
							<time class="h-time" title={formatDateTime(r.created_at)}>
								<span>{formatDateTime(r.created_at)}</span>
								<span class="h-time-rel">{formatRelativeTime(r.created_at)}</span>
							</time>
							{#if r.status === 'deployed' && r.target_container}
								<button class="link-btn" onclick={() => openContainer(r.target_container!)}>열기 →</button>
							{:else}
								<span></span>
							{/if}
						</li>
					{/each}
					{#each Array(historyEmptyRows) as _, i (i)}
						<li class="history-row empty-row" aria-hidden="true">
							<span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span>
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	{/if}

		</section>

		<aside class="side-panel" aria-label="사이드 패널">
			<section class="side-section">
				<header class="side-head">
					<h2>진행 중 요청<Pill tone="var(--accent)" size="md" minWidth="28px">{activeRequests.length}</Pill></h2>
					<InfoTooltip text={activeBannerHelp} label="진행 중 도움말" placement="bottom-start" />
				</header>
				{#if activeRequests.length === 0}
					<div class="side-empty">진행 중 요청 없음</div>
				{:else}
					<ul class="side-req-list">
						{#each activeRequests.slice(0, 6) as r (r.id)}
							<li class="side-req-item">
								<div class="side-req-top">
									<strong title={requestDisplayName(r)}>
										{requestDisplayName(r)}
									</strong>
									<Pill tone={statusTone(r.status)} size="md" minWidth="70px">{statusLabel(r.status)}</Pill>
								</div>
								<div class="side-req-meta">{r.template_name ?? '-'} · {r.target_agent_hostname ?? '-'}</div>
								<div class="track tiny">
									<div class="fill" style="width: {r.progress_percent ?? 0}%"></div>
								</div>
								<div class="side-req-msg">
									<span>{r.progress_message ?? '대기 중'}</span>
									<span>{r.progress_percent != null ? `${r.progress_percent}%` : ''}</span>
								</div>
							</li>
						{/each}
					</ul>
				{/if}
			</section>

			<section class="side-section">
				<header class="side-head">
					<h2>최근 이벤트</h2>
				</header>
				{#if liveEvents.length === 0}
					<div class="side-empty">최근 변화 없음</div>
				{:else}
					<ul class="side-event-list">
						{#each liveEvents.slice(0, 10) as ev (ev.receivedAt + ev.server_id)}
							<li class="side-event-item">
								<span class="event-dot" class:online={ev.status === 'online'}></span>
								<div class="event-body">
									<div class="event-row">
										<strong title={ev.hostname || 'unknown'}>{ev.hostname || 'unknown'}</strong>
										<span>{ev.status === 'online' ? '온라인' : '오프라인'}</span>
									</div>
									<time>{formatRelativeTime(new Date(ev.receivedAt).toISOString())}</time>
								</div>
							</li>
						{/each}
					</ul>
				{/if}
			</section>
		</aside>
	</div>

	{#if errorMsg}
		<div class="toast error legacy" role="status">
			<span>{errorMsg}</span>
			<button class="toast-close" onclick={dismissError} aria-label="닫기">×</button>
		</div>
	{/if}

	<div class="toast-stack" role="region" aria-label="알림">
		{#each toasts as t (t.id)}
			<div class="toast {t.kind}" role="status">
				<span>{t.text}</span>
				<button class="toast-close" onclick={() => dismissToast(t.id)} aria-label="닫기">×</button>
			</div>
		{/each}
	</div>
</div>

<NewRequestModal
	open={newModalOpen}
	onClose={() => (newModalOpen = false)}
	onSubmitted={() => {
		pushToast('success', '새 요청이 제출되었습니다. 승인 대기 중입니다.');
		load();
	}}
/>

<style>
	.page {
		padding: clamp(10px, 0.8vw, 18px) clamp(14px, 1.4vw, 28px);
		max-width: none;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: clamp(8px, 0.6vw, 12px);
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}


	.hero {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 14px;
		padding: clamp(8px, 0.55vw, 12px) clamp(14px, 1vw, 20px);
		background:
			linear-gradient(135deg, rgba(77, 191, 179, 0.1), rgba(9, 75, 102, 0.12)),
			var(--bg-card);
		border: 1px solid rgba(77, 191, 179, 0.16);
		border-radius: 10px;
		flex: 0 0 auto;
	}

	.hero-left {
		display: flex;
		align-items: center;
		gap: 16px;
		min-width: 0;
		flex-wrap: wrap;
	}

	.title-row,
	.kpi-label {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	h1 {
		font-size: clamp(17px, 1.2vw, 22px);
		line-height: 1.15;
		margin: 0;
		font-weight: 800;
	}

	.title-suffix {
		font-weight: 500;
		color: var(--text-secondary);
		margin-left: 4px;
	}

	.kpi-inline {
		display: inline-flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	.kpi-pill {
		background: rgba(13, 17, 23, 0.55);
		color: var(--text-secondary);
	}

	.kpi-pill-num {
		color: var(--text-primary);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		font-size: 14px;
	}

	.kpi-pill-label {
		font-weight: 600;
		color: var(--text-muted);
		font-size: 12.5px;
	}

	.kpi-pill-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--text-muted);
	}

	.kpi-pill-dot.running {
		background: #6dc090;
		box-shadow: 0 0 0 2px rgba(52, 211, 153, 0.18);
	}

	.kpi-pill-dot.warn {
		background: #fbbf24;
		box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.18);
		animation: kpiPulse 1.6s ease-in-out infinite;
	}

	@keyframes kpiPulse {
		0%, 100% { box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.18); }
		50% { box-shadow: 0 0 0 4px rgba(251, 191, 36, 0.35); }
	}

	.hero-actions {
		display: flex;
		gap: 8px;
	}

	.new-btn,
	.ghost-btn {
		border: none;
		border-radius: 8px;
		padding: 8px 14px;
		font-size: 12px;
		font-weight: 700;
		cursor: pointer;
	}

	.new-btn {
		background: var(--accent);
		color: var(--accent-dark);
	}

	.ghost-btn {
		background: rgba(13, 17, 23, 0.62);
		color: var(--text-primary);
		border: 1px solid var(--border);
	}

	.new-btn:hover,
	.ghost-btn:hover {
		filter: brightness(1.08);
	}

	.ghost-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.ghost-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.btn-spinner {
		width: 0;
		height: 0;
		opacity: 0;
		transition: width 0.12s, opacity 0.12s;
	}

	.btn-spinner.spinning {
		width: 12px;
		height: 12px;
		opacity: 1;
		border: 1.6px solid rgba(77, 191, 179, 0.3);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.kpi-strip {
		display: none;
	}

	.main-grid {
		flex: 1;
		min-height: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr) clamp(260px, 22vw, 340px);
		gap: clamp(8px, 0.6vw, 14px);
	}

	.main-grid.no-side {
		grid-template-columns: minmax(0, 1fr);
	}

	.main-grid.no-side .side-panel {
		display: none;
	}

	.main-content {
		min-height: 0;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: clamp(6px, 0.45vw, 10px);
	}

	.side-panel {
		display: grid;
		grid-template-rows: 1fr 1fr;
		gap: clamp(8px, 0.6vw, 12px);
		min-height: 0;
	}

	.side-section {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 10px;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}

	.side-section > ul {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.side-empty {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.side-head {
		flex: 0 0 auto;
		padding: 9px 12px;
		border-bottom: 1px solid rgba(100, 116, 139, 0.22);
		background: rgba(13, 17, 23, 0.45);
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.side-head h2 {
		margin: 0;
		font-size: 13.5px;
		font-weight: 900;
		color: var(--text-primary);
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.side-empty {
		padding: 20px 14px;
		text-align: center;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.side-req-list,
	.side-event-list {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.side-req-item {
		padding: 9px 12px;
		border-top: 1px solid rgba(100, 116, 139, 0.1);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.side-req-item:first-child {
		border-top: none;
	}

	.side-req-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 6px;
	}

	.side-req-top strong {
		flex: 1;
		min-width: 0;
		font-size: 13px;
		font-weight: 850;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.side-req-meta {
		font-size: 12.5px;
		color: var(--text-secondary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.track.tiny {
		height: 4px;
	}

	.side-req-msg {
		display: flex;
		justify-content: space-between;
		gap: 6px;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.side-event-item {
		padding: 8px 12px;
		border-top: 1px solid rgba(100, 116, 139, 0.1);
		display: flex;
		gap: 8px;
		align-items: flex-start;
	}

	.side-event-item:first-child {
		border-top: none;
	}

	.event-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #d98080;
		margin-top: 5px;
		flex-shrink: 0;
	}

	.event-dot.online {
		background: #6dc090;
	}

	.event-body {
		flex: 1;
		min-width: 0;
	}

	.event-row {
		display: flex;
		justify-content: space-between;
		gap: 8px;
	}

	.event-row strong {
		font-size: 13.5px;
		color: var(--text-primary);
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.event-row span {
		font-size: 12.5px;
		color: var(--text-secondary);
		flex-shrink: 0;
	}

	.event-body time {
		font-size: 12px;
		color: var(--text-muted);
	}

	.kpi {
		padding: clamp(9px, 0.65vw, 14px);
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: clamp(6px, 0.4vw, 10px);
		display: flex;
		flex-direction: column;
		gap: 3px;
		min-height: clamp(80px, 6.5vh, 110px);
	}

	.kpi-label {
		font-size: clamp(10px, 0.62vw, 13px);
		color: var(--text-muted);
		font-weight: 800;
		letter-spacing: 0.3px;
	}

	.kpi strong {
		font-size: clamp(20px, 1.4vw, 28px);
		color: var(--text-primary);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
	}

	.kpi-divider {
		color: var(--text-muted);
		font-size: clamp(14px, 1vw, 18px);
		font-weight: 600;
	}

	.kpi-total {
		color: var(--text-secondary);
		font-size: clamp(14px, 1vw, 20px);
		font-weight: 600;
	}

	.kpi-meta {
		font-size: clamp(10px, 0.62vw, 12px);
		color: var(--text-muted);
		font-weight: 600;
		margin-top: auto;
	}

	.active-banner {
		background: linear-gradient(180deg, rgba(77, 191, 179, 0.08), rgba(13, 17, 23, 0.4) 45%);
		border: 1px solid rgba(77, 191, 179, 0.28);
		border-radius: 10px;
		overflow: hidden;
	}

	.banner-head {
		padding: 10px 14px;
		border-bottom: 1px solid rgba(77, 191, 179, 0.18);
	}

	.banner-head h2 {
		margin: 0;
		font-size: 13.5px;
		font-weight: 900;
		color: var(--text-primary);
		display: inline-flex;
		align-items: center;
		gap: 8px;
	}

	.banner-list {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.banner-item {
		padding: 10px 14px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		border-top: 1px solid rgba(100, 116, 139, 0.12);
	}

	.banner-item:first-child {
		border-top: none;
	}

	.banner-top {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
		min-width: 0;
	}

	.banner-name {
		flex: 0 1 auto;
		min-width: 0;
		font-size: 13px;
		font-weight: 850;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.banner-meta {
		flex: 1 1 auto;
		min-width: 0;
		font-size: 12.5px;
		color: var(--text-secondary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.track {
		height: 6px;
		background: rgba(30, 41, 59, 0.85);
		border-radius: 999px;
		overflow: hidden;
	}

	.fill {
		height: 100%;
		background: linear-gradient(90deg, var(--accent), #6be6dc);
		transition: width 0.3s ease;
	}

	.prog-text {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		font-size: 12px;
		color: var(--text-muted);
	}

	.page-tabs {
		display: inline-flex;
		gap: 22px;
		padding: 0 2px;
		background: transparent;
		border: none;
		border-bottom: 1px solid var(--border);
		align-self: stretch;
	}

	.page-tabs button {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 10px 2px;
		margin-bottom: -1px;
		border: none;
		background: transparent;
		color: var(--text-secondary);
		font-size: 15px;
		font-weight: 800;
		border-radius: 0;
		border-bottom: 2px solid transparent;
		cursor: pointer;
		transition: color 0.12s, border-color 0.12s;
	}

	.page-tabs button:hover {
		color: var(--text-primary);
	}

	.page-tabs button.active {
		background: transparent;
		color: var(--accent);
		border-bottom-color: var(--accent);
		box-shadow: none;
	}

	.tab-toolbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	.filter-chips {
		display: inline-flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	.filter-chips button {
		gap: 5px;
		color: var(--text-secondary);
		background: var(--bg-card);
		border-color: var(--border);
		cursor: pointer;
	}

	.filter-chips button:hover {
		color: var(--text-primary);
		border-color: rgba(77, 191, 179, 0.42);
	}

	.filter-chips button.active {
		color: var(--accent);
		background: rgba(77, 191, 179, 0.08);
		border-color: rgba(77, 191, 179, 0.5);
	}

	.chip-num {
		font-size: 12.5px;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}

	.filter-chips button.active .chip-num {
		color: var(--accent);
	}

	.search-input {
		min-width: 240px;
		max-width: 380px;
		padding: 8px 13px;
		font-size: 13.5px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text-primary);
		outline: none;
	}

	.search-input:focus {
		border-color: rgba(77, 191, 179, 0.42);
	}

	.search-input::placeholder {
		color: var(--text-muted);
	}

	.state {
		padding: 50px 24px;
		text-align: center;
		background: var(--bg-card);
		border: 1px dashed var(--border);
		border-radius: 12px;
		color: var(--text-secondary);
		font-size: 13px;
	}

	.state.empty h3 {
		margin: 0 0 6px;
		font-size: 16px;
		font-weight: 800;
		color: var(--text-primary);
	}

	.state.empty p {
		margin: 0 0 16px;
		font-size: 12.5px;
	}

	.container-table {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 10px;
		overflow: hidden;
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
	}

	.container-list {
		list-style: none;
		margin: 0;
		padding: 0;
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.container-head,
	.container-row {
		display: grid;
		grid-template-columns: 110px minmax(180px, 1.4fr) minmax(150px, 1fr) minmax(160px, 1.1fr) 105px 105px 80px 180px;
		gap: 10px;
		align-items: center;
	}

	.container-head {
		padding: 11px 14px;
		background: rgba(13, 17, 23, 0.82);
		color: var(--text-secondary);
		font-size: 13.5px;
		font-weight: 900;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		flex: 0 0 auto;
		position: sticky;
		top: 0;
		z-index: 2;
		border-bottom: 1px solid rgba(100, 116, 139, 0.32);
	}

	.container-row {
		padding: 10px 14px;
		min-height: 48px;
		border-top: 1px solid rgba(100, 116, 139, 0.14);
		cursor: pointer;
		transition: background 0.12s;
	}

	.container-row > * {
		min-width: 0;
		border-right: 1px solid rgba(100, 116, 139, 0.10);
		padding-right: 10px;
		height: 100%;
		display: flex;
		align-items: center;
	}

	.container-row > *:last-child {
		border-right: none;
		padding-right: 0;
	}

	.container-head > * {
		border-right: 1px solid rgba(100, 116, 139, 0.18);
		padding-right: 10px;
	}

	.container-head > *:last-child {
		border-right: none;
	}

	.container-row:not(.empty-row):hover {
		background: rgba(21, 28, 39, 0.7);
	}

	.container-row:focus-visible {
		outline: 2px solid rgba(77, 191, 179, 0.5);
		outline-offset: -2px;
	}

	.container-row.empty-row {
		cursor: default;
		pointer-events: none;
		min-height: 48px;
		border-top: 1px solid rgba(100, 116, 139, 0.08);
	}

	.container-row.empty-row > * {
		border-right-color: transparent;
	}

	.row-status {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--text-muted);
		flex-shrink: 0;
	}

	.dot.running {
		background: #6dc090;
		box-shadow: 0 0 0 2px rgba(52, 211, 153, 0.18);
	}

	.row-name {
		flex-direction: column !important;
		align-items: flex-start !important;
		justify-content: center;
		gap: 2px;
		min-width: 0;
	}

	.row-name strong {
		color: var(--text-primary);
		font-size: 15px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.row-image {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 12.5px;
		color: var(--text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.row-host {
		flex-direction: column !important;
		align-items: flex-start !important;
		justify-content: center;
		gap: 2px;
		min-width: 0;
		font-size: 13.5px;
		color: var(--text-secondary);
	}

	.row-host > span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.row-template {
		color: var(--text-muted);
		font-size: 12.5px;
	}

	.row-resources {
		display: flex;
		align-items: center;
		gap: 5px;
		flex-wrap: wrap;
		min-width: 0;
	}

	.row-time {
		font-size: 13px;
		color: var(--text-secondary);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.row-spark {
		display: flex;
		align-items: center;
		gap: 4px;
		min-width: 0;
	}

	.spark-svg {
		width: 60px;
		height: 16px;
		flex-shrink: 0;
	}

	.spark-flat {
		display: inline-block;
		width: 60px;
		height: 16px;
		flex-shrink: 0;
		border-bottom: 1px dashed rgba(77, 191, 179, 0.32);
		opacity: 0.6;
	}

	.spark-flat.mem {
		border-bottom-color: rgba(165, 180, 252, 0.32);
	}

	.spark-num {
		font-size: 12.5px;
		font-weight: 800;
		color: var(--accent);
		font-variant-numeric: tabular-nums;
	}

	.spark-num.mem {
		color: #a5b4fc;
	}

	.spark-pending {
		font-size: 13px;
		color: var(--text-muted);
	}

	.row-actions {
		display: grid !important;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
		width: 100%;
		align-items: center !important;
	}

	.row-action {
		width: 100%;
		padding: 6px 10px;
		font-size: 12px;
		font-weight: 800;
		border-radius: 6px;
		cursor: pointer;
		border: 1px solid transparent;
		white-space: nowrap;
	}

	.row-action-placeholder {
		display: block;
		width: 100%;
	}

	.row-action.ghost {
		background: rgba(13, 17, 23, 0.5);
		border-color: var(--border);
		color: var(--text-primary);
	}

	.row-action.ghost:hover {
		border-color: rgba(77, 191, 179, 0.4);
		color: var(--accent);
	}

	.row-action.primary {
		background: var(--accent);
		color: var(--accent-dark);
	}

	.row-action.primary:hover {
		filter: brightness(1.06);
	}

	.row-action:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	/* filter-chips / kpi-pill 은 Pill 컴포넌트 size=md 와 동일한 외형 (height 30, radius 6) */
	.filter-chips button,
	.kpi-pill {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		height: 30px;
		padding: 0 12px;
		border-radius: 6px;
		font-size: 13px;
		font-weight: 750;
		background: transparent;
		border: 1px solid rgba(100, 116, 139, 0.32);
		color: var(--text-secondary);
		white-space: nowrap;
		flex-shrink: 0;
		box-sizing: border-box;
		letter-spacing: 0.01em;
	}

	.link-btn {
		background: transparent;
		border: none;
		color: var(--accent);
		font-size: 12.5px;
		font-weight: 800;
		cursor: pointer;
		padding: 2px 4px;
	}

	.link-btn:hover {
		filter: brightness(1.18);
	}

	.history-table {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 10px;
		overflow: hidden;
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
	}

	.history-list {
		list-style: none;
		margin: 0;
		padding: 0;
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.history-head,
	.history-row {
		display: grid;
		grid-template-columns: 60px minmax(160px, 1.4fr) 90px minmax(150px, 1.3fr) minmax(110px, 0.85fr) minmax(90px, 0.55fr) 170px 80px;
		gap: 10px;
		align-items: center;
	}

	.history-head {
		padding: 11px 14px;
		background: rgba(13, 17, 23, 0.82);
		color: var(--text-secondary);
		font-size: 13.5px;
		font-weight: 900;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		flex: 0 0 auto;
		position: sticky;
		top: 0;
		z-index: 2;
		border-bottom: 1px solid rgba(100, 116, 139, 0.32);
	}

	.history-row {
		padding: 10px 14px;
		min-height: 48px;
		border-top: 1px solid rgba(100, 116, 139, 0.14);
		font-size: 12.5px;
	}

	.history-row > * {
		min-width: 0;
		border-right: 1px solid rgba(100, 116, 139, 0.10);
		padding-right: 10px;
		height: 100%;
		display: flex;
		align-items: center;
	}

	.h-action-cell,
	.h-status-cell {
		justify-content: center !important;
	}

	.history-row > *:last-child {
		border-right: none;
		padding-right: 0;
	}

	.history-head > * {
		border-right: 1px solid rgba(100, 116, 139, 0.18);
		padding-right: 10px;
	}

	.history-head > *:last-child {
		border-right: none;
	}

	.history-row:not(.empty-row):hover {
		background: rgba(21, 28, 39, 0.7);
	}

	.history-row.empty-row {
		cursor: default;
		pointer-events: none;
		min-height: 48px;
		border-top: 1px solid rgba(100, 116, 139, 0.08);
	}

	.history-row.empty-row > * {
		border-right-color: transparent;
	}

	.h-name {
		min-width: 0;
		font-size: 14.5px;
		font-weight: 800;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.h-cell,
	.h-memo {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--text-secondary);
		font-size: 13px;
	}

	.h-memo {
		color: var(--text-muted);
	}

	.h-time {
		flex-direction: column !important;
		align-items: flex-start !important;
		justify-content: center;
		font-size: 13px;
		color: var(--text-secondary);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.h-time-rel {
		font-size: 11.5px;
		color: var(--text-muted);
	}

	.toast-stack {
		position: fixed;
		right: 18px;
		bottom: 18px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		z-index: 80;
		pointer-events: none;
	}

	.toast {
		max-width: 380px;
		padding: 10px 14px;
		border-radius: 8px;
		font-size: 12.5px;
		display: flex;
		align-items: center;
		gap: 10px;
		pointer-events: auto;
		box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
		animation: toastIn 0.18s ease-out;
	}

	.toast.legacy {
		position: fixed;
		right: 18px;
		bottom: 18px;
		z-index: 80;
	}

	.toast.success {
		background: rgba(6, 78, 59, 0.95);
		border: 1px solid rgba(52, 211, 153, 0.55);
		color: #d1fae5;
	}

	.toast.error {
		background: rgba(127, 29, 29, 0.95);
		border: 1px solid rgba(248, 113, 113, 0.55);
		color: #fee2e2;
	}

	.toast.info {
		background: rgba(30, 58, 138, 0.95);
		border: 1px solid rgba(96, 165, 250, 0.55);
		color: #dbeafe;
	}

	@keyframes toastIn {
		from { transform: translateY(8px); opacity: 0; }
		to { transform: translateY(0); opacity: 1; }
	}

	.toast-close {
		background: transparent;
		border: none;
		color: inherit;
		font-size: 16px;
		cursor: pointer;
		line-height: 1;
		opacity: 0.85;
	}

	.toast-close:hover {
		opacity: 1;
	}

	.th {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		background: transparent;
		border: none;
		color: inherit;
		font: inherit;
		text-transform: inherit;
		letter-spacing: inherit;
		padding: 0;
		text-align: left;
	}

	.th.sortable {
		cursor: pointer;
	}

	.th.sortable:hover {
		color: var(--text-primary);
	}

	.th.active {
		color: var(--accent);
	}

	@media (max-width: 900px) {
		.hero {
			flex-direction: column;
			align-items: stretch;
		}

		.hero-actions {
			justify-content: flex-end;
		}

		.tab-toolbar {
			flex-direction: column;
			align-items: stretch;
		}

		.search-input {
			max-width: none;
		}

		.history-head {
			display: none;
		}

		.history-row {
			grid-template-columns: 1fr 1fr;
			gap: 6px;
			padding: 10px 12px;
		}

		.h-name {
			grid-column: 1 / -1;
		}

		.h-time,
		.h-memo {
			grid-column: 1 / -1;
		}
	}
</style>
