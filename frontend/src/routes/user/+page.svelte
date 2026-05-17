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
	} from '$lib/utils/container-dashboard';

	type RequestRow = {
		id: string;
		action: string;
		status: string;
		template?: string | null;
		template_name?: string | null;
		target_agent?: string | null;
		target_agent_hostname?: string | null;
		target_container?: string | null;
		target_container_name?: string | null;
		target_container_snapshot_name?: string | null;
		custom_name?: string;
		selected_image?: string;
		progress_message?: string;
		progress_percent?: number | null;
		review_note?: string;
		reviewer_username?: string | null;
		reviewed_at?: string | null;
		created_at: string;
	};

	type MyContainer = {
		container_id: string;
		name: string;
		image: string;
		status: string;
		last_seen: string;
		requested_at?: string | null;
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
	let debouncedSearch = $state('');
	let containers = $state<MyContainer[]>([]);
	let requests = $state<RequestRow[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let newModalOpen = $state(false);
	let newModalPrefill = $state<null | {
		templateId?: string | null;
		agentId?: string | null;
		customName?: string | null;
		selectedImage?: string | null;
	}>(null);

	function scrollFocusedIntoView(which: 'container' | 'history') {
		const id = which === 'container' ? focusedContainerId : focusedRequestId;
		if (!id) return;
		const root = which === 'container' ? containerListEl : historyListEl;
		if (!root) return;
		const el = root.querySelector(`[data-focus-id="${CSS.escape(id)}"]`) as HTMLElement | null;
		if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
	}

	function openNewRequest(prefill: typeof newModalPrefill = null) {
		newModalPrefill = prefill;
		newModalOpen = true;
	}

	function reRequest(r: RequestRow) {
		if (r.action !== 'create') return;
		openNewRequest({
			templateId: r.template ?? null,
			agentId: r.target_agent ?? null,
			customName: r.custom_name ? `${r.custom_name}-재` : null,
			selectedImage: r.selected_image ?? null,
		});
	}
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
	let debouncedHistorySearch = $state('');
	let searchInputEl = $state<HTMLInputElement | null>(null);
	let historySearchInputEl = $state<HTMLInputElement | null>(null);
	let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
	let historySearchDebounceTimer: ReturnType<typeof setTimeout> | null = null;

	$effect(() => {
		const v = search;
		if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
		searchDebounceTimer = setTimeout(() => { debouncedSearch = v; }, 180);
	});

	$effect(() => {
		const v = historySearch;
		if (historySearchDebounceTimer) clearTimeout(historySearchDebounceTimer);
		historySearchDebounceTimer = setTimeout(() => { debouncedHistorySearch = v; }, 180);
	});

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
	let gpuUsageHistory = $state<Record<string, number[]>>({});
	let gpuMemHistory = $state<Record<string, number[]>>({});
	let metricsFetched = false;
	let recentlyChanged = $state<Record<string, number>>({});
	let focusedContainerId = $state('');
	let focusedRequestId = $state('');
	const REQ_PAGE_SIZE = 50;
	let requestPage = $state(1);
	let requestHasMore = $state(false);
	let requestLoadingMore = $state(false);
	let requestTotal = $state(0);
	let ctxMenu = $state<{ x: number; y: number; container: MyContainer } | null>(null);
	let ctxBusy = $state(false);
	let memoPopover = $state<{ x: number; y: number; req: RequestRow } | null>(null);

	function openMemoPopover(e: MouseEvent, r: RequestRow) {
		e.preventDefault();
		e.stopPropagation();
		if (memoPopover?.req.id === r.id) {
			memoPopover = null;
			return;
		}
		const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
		const popW = 320;
		const popH = 180;
		const margin = 8;
		let x = rect.left;
		if (x + popW > window.innerWidth - margin) x = window.innerWidth - popW - margin;
		let y = rect.bottom + 6;
		if (y + popH > window.innerHeight - margin) y = rect.top - popH - 6;
		memoPopover = { x: Math.max(margin, x), y: Math.max(margin, y), req: r };
	}

	function closeMemoPopover() {
		memoPopover = null;
	}

	// idx:  0    1    2    3       4    5    6        7         8    9        10
	//       상태 이름 서버 자원(1fr) CPU  MEM  GPU코어  GPU VRAM 최근 가동시간 액션
	const CONTAINER_COLS_DEFAULT = [110, 240, 200, 290, 105, 105, 110, 115, 90, 110, 220];
	// idx:  0    1    2    3            4    5    6        7    8
	//       유형 이름 상태 템플릿(1fr)  서버 메모 검토자  시각 액션
	const HISTORY_COLS_DEFAULT = [60, 260, 100, 240, 140, 75, 110, 170, 200];
	let containerCols = $state<number[]>([...CONTAINER_COLS_DEFAULT]);
	let historyCols = $state<number[]>([...HISTORY_COLS_DEFAULT]);
	// 자원(idx 3) 컬럼이 남는 가로 공간을 흡수 (1fr). 나머지는 px 고정.
	let containerColsStyle = $derived(
		`--ct-cols: ${containerCols
			.map((w, i) => (i === 3 ? `minmax(${Math.max(260, w)}px, 1fr)` : w + 'px'))
			.join(' ')};`,
	);
	// 템플릿(idx 3) 컬럼이 남는 가로 공간을 흡수 (1fr).
	let historyColsStyle = $derived(
		`--hist-cols: ${historyCols
			.map((w, i) => (i === 3 ? `minmax(${Math.max(220, w)}px, 1fr)` : w + 'px'))
			.join(' ')};`,
	);
	let dragState = $state<{ idx: number; startX: number; startW: number; which: 'container' | 'history' } | null>(null);
	let dragX = $state(0);

	function startResize(e: MouseEvent, idx: number, which: 'container' | 'history') {
		e.preventDefault();
		e.stopPropagation();
		const widths = which === 'container' ? containerCols : historyCols;
		dragState = { idx, startX: e.clientX, startW: widths[idx], which };
		dragX = e.clientX;
		document.body.style.cursor = 'col-resize';
		document.body.style.userSelect = 'none';
		window.addEventListener('mousemove', onResizing);
		window.addEventListener('mouseup', stopResize);
	}

	function onResizing(e: MouseEvent) {
		if (!dragState) return;
		const delta = e.clientX - dragState.startX;
		const newW = Math.max(50, dragState.startW + delta);
		dragX = e.clientX;
		if (dragState.which === 'container') {
			const next = [...containerCols];
			next[dragState.idx] = newW;
			containerCols = next;
		} else {
			const next = [...historyCols];
			next[dragState.idx] = newW;
			historyCols = next;
		}
	}

	function stopResize() {
		if (!dragState) return;
		try {
			if (dragState.which === 'container') localStorage.setItem('hc_user_cont_cols', JSON.stringify(containerCols));
			else localStorage.setItem('hc_user_hist_cols', JSON.stringify(historyCols));
		} catch {
			/* ignore */
		}
		dragState = null;
		document.body.style.cursor = '';
		document.body.style.userSelect = '';
		window.removeEventListener('mousemove', onResizing);
		window.removeEventListener('mouseup', stopResize);
	}

	let _measureCanvas: HTMLCanvasElement | null = null;
	function measureWidth(text: string, font: string): number {
		if (!browser || !text) return 0;
		if (!_measureCanvas) _measureCanvas = document.createElement('canvas');
		const ctx = _measureCanvas.getContext('2d');
		if (!ctx) return text.length * 8;
		ctx.font = font;
		return ctx.measureText(text).width;
	}

	const FONT_NAME = '800 15px Pretendard, sans-serif';
	const FONT_IMAGE = '12.5px ui-monospace, Consolas, monospace';
	const FONT_HOST = '13.5px Pretendard, sans-serif';
	const FONT_META = '12.5px Pretendard, sans-serif';
	const FONT_PILL = '750 13px Pretendard, sans-serif';
	const FONT_HEAD = '900 13px Pretendard, sans-serif';

	function pillWidth(text: string, mono = false): number {
		const font = mono ? FONT_IMAGE : FONT_PILL;
		return measureWidth(text, font) + 26;
	}

	function autoFitContainerCols() {
		if (!browser || containers.length === 0) return;
		try {
			if (localStorage.getItem('hc_user_cont_cols')) return;
		} catch { /* ignore */ }

		const PAD = 32;
		const HEAD_PAD = 36;
		const next = [...CONTAINER_COLS_DEFAULT];

		next[0] = Math.max(next[0], measureWidth('실행 중', FONT_PILL) + 86);
		next[1] = Math.max(next[1], measureWidth('이름 / 이미지', FONT_HEAD) + HEAD_PAD);
		next[2] = Math.max(next[2], measureWidth('서버 · 템플릿', FONT_HEAD) + HEAD_PAD);
		next[3] = Math.max(next[3], measureWidth('자원', FONT_HEAD) + HEAD_PAD);

		for (const c of containers) {
			const nameW = measureWidth(c.name ?? '', FONT_NAME) + PAD;
			const imgW = measureWidth(c.image ?? '', FONT_IMAGE) + PAD;
			next[1] = Math.max(next[1], nameW, imgW);

			const hostW = measureWidth(c.agent_hostname ?? '', FONT_HOST) + PAD;
			const tplW = measureWidth(c.template_name ?? '', FONT_META) + PAD;
			next[2] = Math.max(next[2], hostW, tplW);

			let resourceW = 0;
			if (c.workspace_enabled && c.workspace_host_port) {
				resourceW += pillWidth(`${c.workspace_kind ?? 'ws'} :${c.workspace_host_port}`, true);
			} else {
				const ports = portList(c);
				resourceW += ports ? pillWidth(ports, true) : pillWidth('—', true);
			}
			if (c.allocated_gpu_slice_ids?.length) {
				resourceW += 6 + pillWidth(`GPU ×${c.allocated_gpu_slice_ids.length}`);
			}
			if (c.mounted_model_versions?.length) {
				const name = c.mounted_model_versions[0]?.asset_name ?? '';
				resourceW += 6 + Math.min(160, pillWidth(name));
				if (c.mounted_model_versions.length > 1) {
					resourceW += 6 + pillWidth(`+${c.mounted_model_versions.length - 1}`);
				}
			}
			next[3] = Math.max(next[3], resourceW + 20);
		}

		next[1] = Math.min(next[1], 420);
		next[2] = Math.min(next[2], 360);
		next[3] = Math.min(next[3], 480);

		containerCols = next;
	}

	function autoFitHistoryCols() {
		if (!browser || historyRequests.length === 0) return;
		try {
			if (localStorage.getItem('hc_user_hist_cols')) return;
		} catch { /* ignore */ }

		const PAD = 32;
		const HEAD_PAD = 36;
		const next = [...HISTORY_COLS_DEFAULT];

		next[1] = Math.max(next[1], measureWidth('이름', FONT_HEAD) + HEAD_PAD);
		next[3] = Math.max(next[3], measureWidth('템플릿', FONT_HEAD) + HEAD_PAD);
		next[4] = Math.max(next[4], measureWidth('서버', FONT_HEAD) + HEAD_PAD);

		for (const r of historyRequests) {
			const nameW = measureWidth(requestDisplayName(r), FONT_NAME) + PAD;
			next[1] = Math.max(next[1], nameW);

			const tplW = measureWidth(r.template_name ?? '', FONT_META) + PAD;
			next[3] = Math.max(next[3], tplW);

			const hostW = measureWidth(r.target_agent_hostname ?? '', FONT_META) + PAD;
			next[4] = Math.max(next[4], hostW);
		}

		next[1] = Math.min(next[1], 420);
		next[3] = Math.min(next[3], 360);
		next[4] = Math.min(next[4], 260);

		historyCols = next;
	}

	function resetColumns(which: 'container' | 'history') {
		if (which === 'container') {
			containerCols = [...CONTAINER_COLS_DEFAULT];
			try { localStorage.removeItem('hc_user_cont_cols'); } catch { /* ignore */ }
			autoFitContainerCols();
		} else {
			historyCols = [...HISTORY_COLS_DEFAULT];
			try { localStorage.removeItem('hc_user_hist_cols'); } catch { /* ignore */ }
			autoFitHistoryCols();
		}
	}

	function onRowContextMenu(e: MouseEvent, c: MyContainer) {
		e.preventDefault();
		const margin = 8;
		const menuW = 200;
		const menuH = 200;
		const x = Math.min(e.clientX, window.innerWidth - menuW - margin);
		const y = Math.min(e.clientY, window.innerHeight - menuH - margin);
		ctxMenu = { x, y, container: c };
	}

	function csvEscape(v: unknown): string {
		const s = String(v ?? '');
		if (/[",\n\r]/.test(s)) {
			return '"' + s.replace(/"/g, '""') + '"';
		}
		return s;
	}

	function downloadCsv(filename: string, headers: string[], rows: (string | number | null | undefined)[][]) {
		const lines = [headers.map(csvEscape).join(',')];
		for (const r of rows) lines.push(r.map(csvEscape).join(','));
		const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = filename;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	function tsSuffix(): string {
		const d = new Date();
		const pad = (n: number) => String(n).padStart(2, '0');
		return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
	}

	function exportContainersCsv() {
		const headers = ['상태', '이름', '이미지', '서버', '템플릿', 'GPU 슬라이스', '워크스페이스 포트', '최근 활동'];
		const rows = filteredContainers.map((c) => [
			statusLabel(c.status),
			c.name,
			c.image,
			c.agent_hostname ?? '',
			c.template_name ?? '',
			c.allocated_gpu_slice_ids?.length ?? 0,
			c.workspace_host_port ?? '',
			c.last_seen,
		]);
		downloadCsv(`hypercube-containers-${tsSuffix()}.csv`, headers, rows);
		pushToast('success', `컨테이너 ${rows.length}건을 CSV로 내보냈습니다.`);
	}

	function exportHistoryCsv() {
		const headers = ['유형', '이름', '상태', '템플릿', '서버', '검토 메모', '요청 시각'];
		const rows = filteredHistory.map((r) => [
			r.action === 'create' ? '생성' : r.action === 'delete' ? '삭제' : r.action,
			requestDisplayName(r),
			statusLabel(r.status),
			r.template_name ?? '',
			r.target_agent_hostname ?? '',
			r.review_note ?? '',
			r.created_at,
		]);
		downloadCsv(`hypercube-requests-${tsSuffix()}.csv`, headers, rows);
		pushToast('success', `요청 ${rows.length}건을 CSV로 내보냈습니다.`);
	}

	function onRowMoreClick(e: MouseEvent, c: MyContainer) {
		e.preventDefault();
		e.stopPropagation();
		const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
		const menuW = 200;
		const menuH = 200;
		const margin = 8;
		const x = Math.min(rect.right - menuW, window.innerWidth - menuW - margin);
		const y = Math.min(rect.bottom + 4, window.innerHeight - menuH - margin);
		ctxMenu = { x: Math.max(margin, x), y, container: c };
	}

	function closeCtxMenu() {
		ctxMenu = null;
	}

	async function controlAction(c: MyContainer, action: 'start' | 'stop' | 'restart') {
		if (ctxBusy) return;
		closeCtxMenu();
		const t = token();
		if (!t) return;
		ctxBusy = true;
		try {
			const res = await fetch(`${base}/api/my-containers/${c.container_id}/control/`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' },
				body: JSON.stringify({ action }),
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
			const label = action === 'start' ? '시작' : action === 'stop' ? '정지' : '재시작';
			pushToast('success', `${c.name} ${label} 명령을 보냈습니다`);
			load({ silent: true });
		} catch (err: any) {
			pushToast('error', err?.message || '제어 명령 실패');
		} finally {
			ctxBusy = false;
		}
	}

	async function requestDelete(c: MyContainer) {
		if (ctxBusy) return;
		closeCtxMenu();
		if (!confirm(`${c.name} 컨테이너 삭제를 요청합니다. 관리자 승인 후 삭제됩니다. 계속하시겠습니까?`)) return;
		const t = token();
		if (!t) return;
		ctxBusy = true;
		try {
			const res = await fetch(`${base}/api/requests/`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' },
				body: JSON.stringify({ action: 'delete', target_container: c.container_id }),
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
			pushToast('success', '삭제 요청이 제출되었습니다');
			load({ silent: true });
		} catch (err: any) {
			pushToast('error', err?.message || '삭제 요청 실패');
		} finally {
			ctxBusy = false;
		}
	}

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
					const gpuMemSeries = arr
						.map((p) => {
							const used = Number(p.gpu_memory_used ?? 0);
							const total = Number(p.gpu_memory_total ?? 0);
							return total > 0 ? (used / total) * 100 : 0;
						})
						.filter((n) => Number.isFinite(n));
					const gpuUsageSeries = arr
						.map((p) => Number(p.gpu_usage ?? 0))
						.filter((n) => Number.isFinite(n));
					if (cpuSeries.length > 0) {
						cpuHistory = { ...cpuHistory, [c.container_id]: cpuSeries };
					}
					if (memSeries.length > 0) {
						memHistory = { ...memHistory, [c.container_id]: memSeries };
					}
					if (gpuUsageSeries.length > 0) {
						gpuUsageHistory = { ...gpuUsageHistory, [c.container_id]: gpuUsageSeries };
					}
					if (gpuMemSeries.length > 0) {
						gpuMemHistory = { ...gpuMemHistory, [c.container_id]: gpuMemSeries };
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
	const agentEventsHelp = `에이전트 서버가 online/offline으로 전환될 때마다 push되는 이벤트입니다.
서버가 안정적으로 연결되어 있으면 비어 있습니다.
최근 ${20}건까지 표시합니다.`;

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
		// silent polling 시 사용자가 "더 보기"로 로드한 페이지를 잃지 않도록
		// 현재 누적된 row 수만큼 한 번에 fetch (max_page_size=100 cap)
		const reqSize = opts.silent && requests.length > REQ_PAGE_SIZE
			? Math.min(100, requests.length)
			: REQ_PAGE_SIZE;
		const [reqJson, contJson] = await Promise.all([
			fetchJson(`/api/requests/?page=1&page_size=${reqSize}&ordering=-created_at`, t),
			fetchJson('/api/my-containers/?page_size=100&ordering=-last_seen', t),
		]);
		if (reqJson) {
			requests = reqJson?.data?.results ?? [];
			if (!opts.silent) requestPage = 1;
			requestHasMore = !!reqJson?.data?.next;
			requestTotal = Number(reqJson?.data?.count ?? requests.length) || requests.length;
		}
		if (contJson) {
			const next: MyContainer[] = contJson?.data?.results ?? [];
			const prevMap = Object.fromEntries(containers.map((c) => [c.container_id, c.status]));
			const now = Date.now();
			const flashed: Record<string, number> = {};
			for (const c of next) {
				const prev = prevMap[c.container_id];
				if (prev && prev !== c.status) flashed[c.container_id] = now;
			}
			if (Object.keys(flashed).length > 0) {
				recentlyChanged = { ...recentlyChanged, ...flashed };
				setTimeout(() => {
					const cutoff = Date.now() - 2400;
					recentlyChanged = Object.fromEntries(
						Object.entries(recentlyChanged).filter(([, t]) => t > cutoff),
					);
				}, 2600);
			}
			containers = next;
		}
		loading = false;
		refreshing = false;
		syncPolling();
		if (!metricsFetched && containers.length > 0) {
			metricsFetched = true;
			fetchSparklines(t);
		}
		autoFitContainerCols();
		autoFitHistoryCols();
	}

	async function loadMoreRequests() {
		if (!requestHasMore || requestLoadingMore) return;
		const t = token();
		if (!t) return;
		requestLoadingMore = true;
		try {
			const nextPage = requestPage + 1;
			const json = await fetchJson(`/api/requests/?page=${nextPage}&page_size=${REQ_PAGE_SIZE}&ordering=-created_at`, t);
			if (!json) return;
			const results: RequestRow[] = json?.data?.results ?? [];
			const have = new Set(requests.map((r) => r.id));
			requests = [...requests, ...results.filter((r) => !have.has(r.id))];
			requestPage = nextPage;
			requestHasMore = !!json?.data?.next;
			requestTotal = Number(json?.data?.count ?? requestTotal) || requestTotal;
		} finally {
			requestLoadingMore = false;
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
		if (r.target_container_snapshot_name) return r.target_container_snapshot_name;
		if (r.target_container) {
			const prefix = r.action === 'delete' ? '삭제' : '대상';
			return `${prefix}: ${String(r.target_container).slice(0, 12)}`;
		}
		if (r.action === 'delete') {
			return `삭제 요청 #${String(r.id).slice(0, 8)}`;
		}
		return `요청 #${String(r.id).slice(0, 8)}`;
	}

	function uptimeLabel(c: MyContainer): string {
		const since = c.requested_at;
		if (!since) return '-';
		const ms = Date.now() - new Date(since).getTime();
		if (!Number.isFinite(ms) || ms < 0) return '-';
		const sec = Math.floor(ms / 1000);
		if (sec < 60) return `${sec}초`;
		const min = Math.floor(sec / 60);
		if (min < 60) return `${min}분`;
		const hr = Math.floor(min / 60);
		if (hr < 24) return `${hr}시간`;
		const day = Math.floor(hr / 24);
		const remHr = hr % 24;
		return remHr > 0 ? `${day}일 ${remHr}시간` : `${day}일`;
	}

	function portList(c: MyContainer): string {
		const ports = c.custom_ports;
		if (!ports) return '';
		if (Array.isArray(ports)) {
			const slice = ports.slice(0, 3) as Array<{ host?: number | string; container?: number | string }>;
			if (!slice.length) return '';
			return slice
				.map((p) => {
					const host = String(p?.host ?? '').trim();
					const container = String(p?.container ?? '').trim();
					if (host && container && host !== container) return `${host} → ${container}`;
					return host || container;
				})
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
				const kw = debouncedSearch.trim().toLowerCase();
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
				const kw = debouncedHistorySearch.trim().toLowerCase();
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

	function handleWindowClick(_e: MouseEvent) {
		if (ctxMenu) closeCtxMenu();
		if (memoPopover) closeMemoPopover();
	}

	// Escape 닫기 핸들러 — context menu / memo popover / 검색 입력 reset 만 담당.
	// 이전 단축키(/ n g+c g+h)는 사용성 피드백으로 전면 제거.
	function handleGlobalKeydown(e: KeyboardEvent) {
		if (e.key !== 'Escape') return;
		const target = e.target as HTMLElement | null;
		const tag = target?.tagName;
		const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || (target as any)?.isContentEditable;

		if (ctxMenu) {
			closeCtxMenu();
			e.preventDefault();
			return;
		}
		if (memoPopover) {
			closeMemoPopover();
			e.preventDefault();
			return;
		}
		if (inInput) {
			if (target === searchInputEl) {
				search = '';
				debouncedSearch = '';
				(target as HTMLInputElement).blur();
				e.preventDefault();
			} else if (target === historySearchInputEl) {
				historySearch = '';
				debouncedHistorySearch = '';
				(target as HTMLInputElement).blur();
				e.preventDefault();
			}
		}
	}

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
		const focusContainer = u.searchParams.get('focus');
		if (focusContainer) {
			focusedContainerId = focusContainer;
			activeTab = 'containers';
			setTimeout(() => scrollFocusedIntoView('container'), 400);
			setTimeout(() => { focusedContainerId = ''; }, 4000);
		}
		const focusRequest = u.searchParams.get('req');
		if (focusRequest) {
			focusedRequestId = focusRequest;
			activeTab = 'history';
			setTimeout(() => scrollFocusedIntoView('history'), 400);
			setTimeout(() => { focusedRequestId = ''; }, 4000);
		}
		try {
			const cc = localStorage.getItem('hc_user_cont_cols');
			if (cc) {
				const arr = JSON.parse(cc);
				if (Array.isArray(arr) && arr.length === CONTAINER_COLS_DEFAULT.length) {
					containerCols = arr.map((n) => Math.max(50, Number(n) || 0));
				}
			}
			const hc = localStorage.getItem('hc_user_hist_cols');
			if (hc) {
				const arr = JSON.parse(hc);
				if (Array.isArray(arr) && arr.length === HISTORY_COLS_DEFAULT.length) {
					historyCols = arr.map((n) => Math.max(50, Number(n) || 0));
				}
			}
		} catch {
			/* ignore */
		}
		window.addEventListener('keydown', handleGlobalKeydown);
		window.addEventListener('click', handleWindowClick);
		load();
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
		if (urlSyncTimer) clearTimeout(urlSyncTimer);
		if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
		if (historySearchDebounceTimer) clearTimeout(historySearchDebounceTimer);
		if (browser) {
			window.removeEventListener('keydown', handleGlobalKeydown);
			window.removeEventListener('click', handleWindowClick);
		}
		unsubEvents();
	});
</script>

<div class="page">
	<section class="hero">
		<div class="hero-left">
			<div class="title-row">
				<h1>내 대시보드<span class="title-suffix">컨테이너 · 요청 · 자원 한눈에</span></h1>
				<InfoTooltip text={pageHelp} label="페이지 도움말" placement="bottom-start" maxWidth={420} />
			</div>
			<div class="kpi-inline">
				<span class="kpi-pill kpi-container" class:on={runningCount > 0} title="실행 중 / 전체 컨테이너">
					<span class="kpi-pill-dot running"></span>
					<span class="kpi-pill-num">{runningCount} / {totalCount}</span>
					<span class="kpi-pill-label">컨테이너</span>
				</span>
				<span class="kpi-pill kpi-request" class:on={activeRequests.length > 0} title="대기·승인·배포 중 요청">
					<span class="kpi-pill-dot" class:warn={activeRequests.length > 0}></span>
					<span class="kpi-pill-num">{activeRequests.length}</span>
					<span class="kpi-pill-label">진행 요청</span>
				</span>
				<span class="kpi-pill kpi-gpu" class:on={gpuSliceCount > 0} title="GPU 슬라이스 합계">
					<span class="kpi-pill-dot gpu"></span>
					<span class="kpi-pill-num">{gpuSliceCount}</span>
					<span class="kpi-pill-label">GPU</span>
				</span>
				<span class="kpi-pill kpi-workspace" class:on={workspaceCount > 0} title="활성화된 워크스페이스">
					<span class="kpi-pill-dot ws"></span>
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
			<button class="new-btn" onclick={() => openNewRequest(null)}>+ 새 요청</button>
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

	<div class="main-grid">
		<section class="main-content">

	{#if activeTab === 'containers'}
		<section class="tab-toolbar">
			<div class="filter-chips" role="tablist">
				<button class:active={containerFilter === 'all'} onclick={() => setContainerFilter('all')}>전체 <span class="chip-num">{totalCount}</span></button>
				<button class:active={containerFilter === 'running'} onclick={() => setContainerFilter('running')}>실행 중 <span class="chip-num">{runningCount}</span></button>
				<button class:active={containerFilter === 'workspace'} onclick={() => setContainerFilter('workspace')}>워크스페이스 <span class="chip-num">{workspaceCount}</span></button>
				<button class:active={containerFilter === 'stopped'} onclick={() => setContainerFilter('stopped')}>중지됨 <span class="chip-num">{stoppedCount}</span></button>
			</div>
			<div class="toolbar-right">
				<button class="toolbar-btn" onclick={exportContainersCsv} disabled={filteredContainers.length === 0} title="현재 보이는 컨테이너 CSV 내보내기">CSV</button>
				<div class="search-wrap">
					<input class="search-input" bind:this={searchInputEl} bind:value={search} type="text" placeholder="이름·이미지·서버·템플릿 검색" />
					{#if search}
						<button class="search-clear" onclick={() => { search = ''; debouncedSearch = ''; searchInputEl?.focus(); }} aria-label="검색 초기화" title="검색 초기화 (Esc)">×</button>
					{/if}
				</div>
			</div>
		</section>

		{#if loading && containers.length === 0}
			<div class="skel-table" style={containerColsStyle} aria-busy="true" aria-label="컨테이너 불러오는 중">
				{#each Array(6) as _, i (i)}
					<div class="skel-row skel-row-container">
						<span class="skel-cell"><span class="skel-pill"></span></span>
						<span class="skel-cell skel-cell-stack">
							<span class="skel-bar" style="width: 62%"></span>
							<span class="skel-bar skel-bar-sm" style="width: 88%"></span>
						</span>
						<span class="skel-cell skel-cell-stack">
							<span class="skel-bar" style="width: 56%"></span>
							<span class="skel-bar skel-bar-sm" style="width: 78%"></span>
						</span>
						<span class="skel-cell"><span class="skel-pill" style="width: 78px"></span></span>
						<span class="skel-cell"><span class="skel-spark"></span></span>
						<span class="skel-cell"><span class="skel-spark"></span></span>
						<span class="skel-cell"><span class="skel-spark"></span></span>
						<span class="skel-cell"><span class="skel-spark"></span></span>
						<span class="skel-cell"><span class="skel-bar" style="width: 60%"></span></span>
						<span class="skel-cell"><span class="skel-bar" style="width: 70%"></span></span>
						<span class="skel-cell skel-cell-actions">
							<span class="skel-btn"></span>
							<span class="skel-btn"></span>
						</span>
					</div>
				{/each}
			</div>
		{:else if filteredContainers.length === 0}
			<div class="state empty">
				{#if containers.length === 0}
					<h3>아직 컨테이너가 없습니다</h3>
					<p>아래에서 시작해 보세요.</p>
					<button class="new-btn" onclick={() => openNewRequest(null)}>+ 새 요청 만들기</button>
					<div class="empty-hints">
						<div class="hint-card">
							<strong>워크스페이스</strong>
							<p>Jupyter Lab + GPU 1슬라이스로 빠르게 실험 환경 구성.</p>
						</div>
						<div class="hint-card">
							<strong>서비스 컨테이너</strong>
							<p>Redis · Nginx · 자체 이미지 — 컴포즈 그룹도 지원.</p>
						</div>
					</div>
				{:else}
					<h3>조건에 맞는 컨테이너가 없습니다</h3>
					<p>필터를 바꾸거나 검색어를 지워보세요.</p>
				{/if}
			</div>
		{:else}
			<div class="container-table" style={containerColsStyle}>
				<div class="container-head">
					<button class="th sortable" class:active={sortField === 'status'} onclick={() => setSort('status')}>
						상태{sortField === 'status' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
						<span class="col-resize" onmousedown={(e) => startResize(e, 0, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</button>
					<button class="th sortable" class:active={sortField === 'name'} onclick={() => setSort('name')}>
						이름 / 이미지{sortField === 'name' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
						<span class="col-resize" onmousedown={(e) => startResize(e, 1, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</button>
					<span class="th">서버 · 템플릿
						<span class="col-resize" onmousedown={(e) => startResize(e, 2, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</span>
					<span class="th">자원
						<span class="col-resize" onmousedown={(e) => startResize(e, 3, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</span>
					<button
						class="th sortable"
						class:active={sortField === 'cpu'}
						onclick={() => setSort('cpu')}
						title={`컨테이너 CPU 사용률.\n분모: 자체 cores quota (없으면 host 전체).\n최근 1시간 추세 — 약 2분 간격 30 포인트.`}
					>
						CPU <small>(1H)</small>{sortField === 'cpu' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
						<span class="col-resize" onmousedown={(e) => startResize(e, 4, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</button>
					<button
						class="th sortable"
						class:active={sortField === 'mem'}
						onclick={() => setSort('mem')}
						title={`컨테이너 메모리 사용률.\n분모: 자체 memory_limit (없으면 host 전체).\n최근 1시간 추세 — 약 2분 간격 30 포인트.`}
					>
						MEM <small>(1H)</small>{sortField === 'mem' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
						<span class="col-resize" onmousedown={(e) => startResize(e, 5, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</button>
					<span
						class="th"
						title={`컨테이너 GPU SM 사용률.\n분모: 할당된 GPU slice (full slice 는 host GPU 와 동일, MIG/partial slice 는 비례).\n최근 1시간 추세 — 약 2분 간격 30 포인트.\nGPU 슬라이스 미할당 컨테이너는 빈 칸 (—).`}
					>
						GPU 코어 <small>(1H)</small>
						<span class="col-resize" onmousedown={(e) => startResize(e, 6, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</span>
					<span
						class="th"
						title={`컨테이너 GPU VRAM 사용률.\n분모: 할당된 slice memory.\n최근 1시간 추세 — 약 2분 간격 30 포인트.\nGPU 슬라이스 미할당 컨테이너는 빈 칸 (—).`}
					>
						GPU VRAM <small>(1H)</small>
						<span class="col-resize" onmousedown={(e) => startResize(e, 7, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</span>
					<button class="th sortable" class:active={sortField === 'last_seen'} onclick={() => setSort('last_seen')}>
						최근{sortField === 'last_seen' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
						<span class="col-resize" onmousedown={(e) => startResize(e, 8, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</button>
					<span class="th">가동 시간
						<span class="col-resize" onmousedown={(e) => startResize(e, 9, 'container')} ondblclick={(e) => { e.stopPropagation(); resetColumns('container'); }} aria-hidden="true"></span>
					</span>
					<span class="th th-actions"><span>액션</span></span>
				</div>
				<ul class="container-list" bind:this={containerListEl}>
					{#each filteredContainers as c (c.container_id + ':' + (recentlyChanged[c.container_id] ?? 0))}
						<li class="container-row" class:row-changed={!!recentlyChanged[c.container_id]} class:row-focused={c.container_id === focusedContainerId} data-focus-id={c.container_id} onclick={() => openContainer(c.container_id)} oncontextmenu={(e) => onRowContextMenu(e, c)} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && openContainer(c.container_id)}>
							<span class="row-status">
								<Pill status={c.status} dot size="md" minWidth="76px">{statusLabel(c.status)}</Pill>
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
									<Pill kind="accent" size="md" mono truncate>{c.workspace_kind ?? 'ws'} :{c.workspace_host_port}</Pill>
								{:else if portList(c)}
									<Pill kind="accent" size="md" mono truncate>{portList(c)}</Pill>
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
									{#if series.length >= 2 && sMax >= 0.5}
										{@const sp = sparklinePoints(series, 60, 16)}
										<svg viewBox="0 0 60 16" preserveAspectRatio="none" class="spark-svg">
											<line x1="0" y1="15" x2="60" y2="15" stroke="rgba(100,116,139,0.32)" stroke-width="0.6" stroke-dasharray="2 2" />
											<path d={sp.area} fill="rgba(77,191,179,0.18)" stroke="none" />
											<path d={sp.line} fill="none" stroke="#4dbfb3" stroke-width="1.4" />
										</svg>
									{:else}
										<span class="spark-flat" aria-hidden="true"></span>
									{/if}
									<span class="spark-num">{(series[series.length - 1] ?? 0).toFixed(1)}%</span>
								{:else}
									<span class="spark-pending">—</span>
								{/if}
							</span>
							<span class="row-spark">
								{#if memHistory[c.container_id]}
									{@const series = memHistory[c.container_id]}
									{@const sMax = Math.max(...series)}
									{#if series.length >= 2 && sMax >= 0.5}
										{@const sp = sparklinePoints(series, 60, 16)}
										<svg viewBox="0 0 60 16" preserveAspectRatio="none" class="spark-svg">
											<line x1="0" y1="15" x2="60" y2="15" stroke="rgba(100,116,139,0.32)" stroke-width="0.6" stroke-dasharray="2 2" />
											<path d={sp.area} fill="rgba(165,180,252,0.18)" stroke="none" />
											<path d={sp.line} fill="none" stroke="#a5b4fc" stroke-width="1.4" />
										</svg>
									{:else}
										<span class="spark-flat mem" aria-hidden="true"></span>
									{/if}
									<span class="spark-num mem">{(series[series.length - 1] ?? 0).toFixed(1)}%</span>
								{:else}
									<span class="spark-pending">—</span>
								{/if}
							</span>
							<span class="row-spark">
								{#if (c.allocated_gpu_slice_ids?.length ?? 0) === 0}
									<span class="spark-pending" title="GPU 슬라이스 미할당">—</span>
								{:else if gpuUsageHistory[c.container_id]}
									{@const series = gpuUsageHistory[c.container_id]}
									{@const sMax = Math.max(...series)}
									{#if series.length >= 2 && sMax >= 0.5}
										{@const sp = sparklinePoints(series, 60, 16)}
										<svg viewBox="0 0 60 16" preserveAspectRatio="none" class="spark-svg">
											<line x1="0" y1="15" x2="60" y2="15" stroke="rgba(100,116,139,0.32)" stroke-width="0.6" stroke-dasharray="2 2" />
											<path d={sp.area} fill="rgba(244,114,182,0.18)" stroke="none" />
											<path d={sp.line} fill="none" stroke="#f472b6" stroke-width="1.4" />
										</svg>
									{:else}
										<span class="spark-flat gpu-util" aria-hidden="true"></span>
									{/if}
									<span class="spark-num gpu-util">{(series[series.length - 1] ?? 0).toFixed(1)}%</span>
								{:else}
									<span class="spark-pending">…</span>
								{/if}
							</span>
							<span class="row-spark">
								{#if (c.allocated_gpu_slice_ids?.length ?? 0) === 0}
									<span class="spark-pending" title="GPU 슬라이스 미할당">—</span>
								{:else if gpuMemHistory[c.container_id]}
									{@const series = gpuMemHistory[c.container_id]}
									{@const sMax = Math.max(...series)}
									{#if series.length >= 2 && sMax >= 0.5}
										{@const sp = sparklinePoints(series, 60, 16)}
										<svg viewBox="0 0 60 16" preserveAspectRatio="none" class="spark-svg">
											<line x1="0" y1="15" x2="60" y2="15" stroke="rgba(100,116,139,0.32)" stroke-width="0.6" stroke-dasharray="2 2" />
											<path d={sp.area} fill="rgba(160,135,217,0.18)" stroke="none" />
											<path d={sp.line} fill="none" stroke="#a087d9" stroke-width="1.4" />
										</svg>
									{:else}
										<span class="spark-flat gpu" aria-hidden="true"></span>
									{/if}
									<span class="spark-num gpu">{(series[series.length - 1] ?? 0).toFixed(1)}%</span>
								{:else}
									<span class="spark-pending">…</span>
								{/if}
							</span>
							<span class="row-time">{formatRelativeTime(c.last_seen)}</span>
							<span class="row-uptime" title={c.requested_at ? formatDateTime(c.requested_at) : '-'}>{uptimeLabel(c)}</span>
							<div class="row-actions" onclick={(e) => e.stopPropagation()} role="presentation">
								<button class="row-btn" onclick={() => openContainer(c.container_id)} title="모니터링 대시보드 열기">
									<svg class="row-btn-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
										<path d="M3 3v18h18" />
										<path d="M7 15v3" />
										<path d="M12 10v8" />
										<path d="M17 5v13" />
									</svg>
									<span>모니터링</span>
								</button>
								<button
									class="row-btn"
									onclick={(e) => (c.workspace_enabled && c.workspace_host_port) && openWorkspace(c, e)}
									disabled={!(c.workspace_enabled && c.workspace_host_port) || openingId === c.container_id}
									title={(c.workspace_enabled && c.workspace_host_port) ? 'Jupyter 워크스페이스 열기' : '이 컨테이너는 Jupyter 워크스페이스가 활성화되지 않았습니다'}
								>
									<svg class="row-btn-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
										<ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(45 12 12)" />
										<circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />
									</svg>
									<span>{openingId === c.container_id ? '여는 중…' : 'Jupyter'}</span>
								</button>
								<button
									class="row-btn row-btn-icon row-btn-more"
									onclick={(e) => onRowMoreClick(e, c)}
									title="더 보기 (우클릭과 동일)"
									aria-label="더 많은 액션"
								>
									<svg class="row-btn-ico" viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden="true">
										<circle cx="5" cy="12" r="1.6" />
										<circle cx="12" cy="12" r="1.6" />
										<circle cx="19" cy="12" r="1.6" />
									</svg>
								</button>
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
			<div class="toolbar-right">
				<button class="toolbar-btn" onclick={exportHistoryCsv} disabled={filteredHistory.length === 0} title="현재 보이는 요청 이력 CSV 내보내기">CSV</button>
				<div class="search-wrap">
					<input class="search-input" bind:this={historySearchInputEl} bind:value={historySearch} type="text" placeholder="이름·템플릿·서버·검토 메모 검색" />
					{#if historySearch}
						<button class="search-clear" onclick={() => { historySearch = ''; debouncedHistorySearch = ''; historySearchInputEl?.focus(); }} aria-label="검색 초기화" title="검색 초기화 (Esc)">×</button>
					{/if}
				</div>
			</div>
		</section>

		{#if loading && requests.length === 0}
			<div class="skel-table" style={historyColsStyle} aria-busy="true" aria-label="요청 이력 불러오는 중">
				{#each Array(8) as _, i (i)}
					<div class="skel-row skel-row-history">
						<span class="skel-cell"><span class="skel-pill" style="width: 44px"></span></span>
						<span class="skel-cell"><span class="skel-bar" style="width: 70%"></span></span>
						<span class="skel-cell"><span class="skel-pill"></span></span>
						<span class="skel-cell"><span class="skel-bar" style="width: 65%"></span></span>
						<span class="skel-cell"><span class="skel-bar" style="width: 55%"></span></span>
						<span class="skel-cell"><span class="skel-chip"></span></span>
						<span class="skel-cell"><span class="skel-bar" style="width: 60%"></span></span>
						<span class="skel-cell skel-cell-stack">
							<span class="skel-bar" style="width: 75%"></span>
							<span class="skel-bar skel-bar-sm" style="width: 45%"></span>
						</span>
						<span class="skel-cell skel-cell-actions">
							<span class="skel-btn"></span>
							<span class="skel-btn"></span>
						</span>
					</div>
				{/each}
			</div>
		{:else if filteredHistory.length === 0}
			<div class="state empty">
				<h3>요청 이력이 없습니다</h3>
				<p>완료·반려·취소된 과거 요청이 여기 표시됩니다.</p>
			</div>
		{:else}
			<div class="history-table" style={historyColsStyle}>
				<div class="history-head">
					<button class="th sortable" class:active={historySortField === 'action'} onclick={() => setHistorySort('action')}>
						유형{historySortField === 'action' ? (historySortDir === 'asc' ? ' ↑' : ' ↓') : ''}
						<span class="col-resize" onmousedown={(e) => startResize(e, 0, 'history')} ondblclick={(e) => { e.stopPropagation(); resetColumns('history'); }} aria-hidden="true"></span>
					</button>
					<button class="th sortable" class:active={historySortField === 'name'} onclick={() => setHistorySort('name')}>
						이름{historySortField === 'name' ? (historySortDir === 'asc' ? ' ↑' : ' ↓') : ''}
						<span class="col-resize" onmousedown={(e) => startResize(e, 1, 'history')} ondblclick={(e) => { e.stopPropagation(); resetColumns('history'); }} aria-hidden="true"></span>
					</button>
					<button class="th sortable" class:active={historySortField === 'status'} onclick={() => setHistorySort('status')}>
						상태{historySortField === 'status' ? (historySortDir === 'asc' ? ' ↑' : ' ↓') : ''}
						<span class="col-resize" onmousedown={(e) => startResize(e, 2, 'history')} ondblclick={(e) => { e.stopPropagation(); resetColumns('history'); }} aria-hidden="true"></span>
					</button>
					<span class="th">템플릿
						<span class="col-resize" onmousedown={(e) => startResize(e, 3, 'history')} ondblclick={(e) => { e.stopPropagation(); resetColumns('history'); }} aria-hidden="true"></span>
					</span>
					<span class="th">서버
						<span class="col-resize" onmousedown={(e) => startResize(e, 4, 'history')} ondblclick={(e) => { e.stopPropagation(); resetColumns('history'); }} aria-hidden="true"></span>
					</span>
					<span class="th">검토 메모
						<span class="col-resize" onmousedown={(e) => startResize(e, 5, 'history')} ondblclick={(e) => { e.stopPropagation(); resetColumns('history'); }} aria-hidden="true"></span>
					</span>
					<span class="th">검토자
						<span class="col-resize" onmousedown={(e) => startResize(e, 6, 'history')} ondblclick={(e) => { e.stopPropagation(); resetColumns('history'); }} aria-hidden="true"></span>
					</span>
					<button class="th sortable" class:active={historySortField === 'created_at'} onclick={() => setHistorySort('created_at')}>
						요청 시각{historySortField === 'created_at' ? (historySortDir === 'asc' ? ' ↑' : ' ↓') : ''}
						<span class="col-resize" onmousedown={(e) => startResize(e, 7, 'history')} ondblclick={(e) => { e.stopPropagation(); resetColumns('history'); }} aria-hidden="true"></span>
					</button>
					<span class="th th-actions"><span>액션</span></span>
				</div>
				<ul class="history-list" bind:this={historyListEl}>
					{#each filteredHistory as r (r.id)}
						<li class="history-row" class:row-focused={r.id === focusedRequestId} data-focus-id={r.id}>
							<span class="h-action-cell">
								<Pill
									kind={r.action === 'create' ? 'success' : r.action === 'delete' ? 'danger' : 'neutral'}
									size="md"
									minWidth="46px"
								>
									{r.action === 'create' ? '생성' : r.action === 'delete' ? '삭제' : r.action}
								</Pill>
							</span>
							<strong class="h-name" title={requestDisplayName(r)}>{requestDisplayName(r)}</strong>
							<span class="h-status-cell">
								<Pill status={r.status} dot size="md" minWidth="76px">{statusLabel(r.status)}</Pill>
							</span>
							<span class="h-cell" title={r.template_name ?? ''}>{r.template_name ?? '-'}</span>
							<span class="h-cell" title={r.target_agent_hostname ?? ''}>{r.target_agent_hostname ?? '-'}</span>
							<span class="h-memo">
								{#if r.review_note}
									<button
										class="memo-chip"
										class:memo-chip-active={memoPopover?.req.id === r.id}
										onclick={(e) => openMemoPopover(e, r)}
										title="클릭해서 메모 상세 보기"
										aria-label="검토 메모 보기"
									>메모</button>
								{:else}
									<span class="memo-dash" aria-hidden="true">—</span>
								{/if}
							</span>
							<span class="h-cell h-reviewer" title={r.reviewer_username ?? ''}>{r.reviewer_username || '—'}</span>
							<time class="h-time" title={formatDateTime(r.created_at)}>
								<span>{formatDateTime(r.created_at)}</span>
								<span class="h-time-rel">{formatRelativeTime(r.created_at)}</span>
							</time>
							<div class="h-actions">
								<button
									class="row-btn"
									onclick={() => r.status === 'deployed' && r.target_container && openContainer(r.target_container)}
									disabled={!(r.status === 'deployed' && r.target_container)}
									title={r.status === 'deployed' && r.target_container ? '컨테이너 모니터링 열기' : '배포 완료된 요청만 열 수 있습니다'}
								>
									<svg class="row-btn-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
										<path d="M7 17L17 7" />
										<path d="M9 7h8v8" />
									</svg>
									<span>열기</span>
								</button>
								<button
									class="row-btn"
									onclick={() => r.action === 'create' && r.template && reRequest(r)}
									disabled={!(r.action === 'create' && r.template)}
									title={r.action === 'create' && r.template ? '이 요청과 같은 설정으로 새 요청 만들기' : '생성 요청만 다시 요청할 수 있습니다'}
								>
									<svg class="row-btn-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
										<path d="M21 12a9 9 0 1 1-3-6.7" />
										<path d="M21 4v5h-5" />
									</svg>
									<span>재요청</span>
								</button>
							</div>
						</li>
					{/each}
					{#if requestHasMore}
						<li class="history-loadmore">
							<button class="loadmore-btn" disabled={requestLoadingMore} onclick={loadMoreRequests}>
								{requestLoadingMore ? '불러오는 중…' : `더 보기 (남은 ${Math.max(0, requestTotal - requests.length)}개)`}
							</button>
						</li>
					{/if}
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
					<h2>진행 중 요청<Pill tone="var(--text-secondary)" size="md" minWidth="28px">{activeRequests.length}</Pill></h2>
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
									<Pill status={r.status} dot size="md" minWidth="76px">{statusLabel(r.status)}</Pill>
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
					<h2>서버 상태 변화<Pill tone="var(--text-secondary)" size="md" minWidth="28px">{liveEvents.length}</Pill></h2>
					<InfoTooltip text={agentEventsHelp} label="서버 상태 변화 도움말" placement="bottom-start" />
				</header>
				{#if liveEvents.length === 0}
					<div class="side-empty">서버가 안정 연결 중</div>
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

	{#if dragState}
		<div class="drag-guideline" style="left: {dragX}px;" aria-hidden="true"></div>
	{/if}

	{#if memoPopover}
		{@const m = memoPopover}
		<div
			class="memo-popover"
			style="left: {m.x}px; top: {m.y}px;"
			role="dialog"
			aria-label="검토 메모"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="memo-popover-head">
				<span>검토 메모</span>
				<button class="memo-popover-close" onclick={closeMemoPopover} aria-label="닫기">×</button>
			</div>
			<div class="memo-popover-body">{m.req.review_note}</div>
			<div class="memo-popover-foot">
				{#if m.req.reviewer_username}
					<span>검토자 <strong>{m.req.reviewer_username}</strong></span>
				{/if}
				{#if m.req.reviewed_at}
					<span>{formatDateTime(m.req.reviewed_at)}</span>
				{/if}
			</div>
		</div>
	{/if}

	{#if ctxMenu}
		{@const m = ctxMenu}
		<div
			class="ctx-menu"
			style="left: {m.x}px; top: {m.y}px;"
			role="menu"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="ctx-head" title={m.container.name}>{m.container.name}</div>
			<button class="ctx-item" disabled={ctxBusy || m.container.status === 'running'} onclick={() => controlAction(m.container, 'start')}>시작</button>
			<button class="ctx-item" disabled={ctxBusy || m.container.status !== 'running'} onclick={() => controlAction(m.container, 'stop')}>정지</button>
			<button class="ctx-item" disabled={ctxBusy} onclick={() => controlAction(m.container, 'restart')}>재시작</button>
			<div class="ctx-divider"></div>
			<button class="ctx-item danger" disabled={ctxBusy} onclick={() => requestDelete(m.container)}>삭제 요청</button>
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
	prefill={newModalPrefill}
	onClose={() => { newModalOpen = false; newModalPrefill = null; }}
	onSubmitted={() => {
		newModalPrefill = null;
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
		color: var(--text-muted);
		margin-left: 12px;
		font-size: clamp(11.5px, 0.78vw, 13px);
		letter-spacing: 0.02em;
		position: relative;
		padding-left: 14px;
	}

	.title-suffix::before {
		content: '';
		position: absolute;
		left: 0;
		top: 50%;
		transform: translateY(-50%);
		width: 1px;
		height: 60%;
		background: rgba(100, 116, 139, 0.42);
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
		box-shadow: 0 0 0 2px rgba(95, 186, 133, 0.18);
	}

	.kpi-pill-dot.warn {
		background: #d4a25b;
		box-shadow: 0 0 0 2px rgba(212, 162, 91, 0.22);
		animation: kpiPulse 1.6s ease-in-out infinite;
	}

	.kpi-pill-dot.gpu {
		background: #a087d9;
		box-shadow: 0 0 0 2px rgba(160, 135, 217, 0.18);
	}

	.kpi-pill-dot.ws {
		background: #6c9bd0;
		box-shadow: 0 0 0 2px rgba(108, 155, 208, 0.18);
	}

	.kpi-pill.on.kpi-container {
		border-color: rgba(95, 186, 133, 0.42);
		background: linear-gradient(135deg, rgba(95, 186, 133, 0.10), rgba(13, 17, 23, 0.55));
	}

	.kpi-pill.on.kpi-request {
		border-color: rgba(212, 162, 91, 0.42);
		background: linear-gradient(135deg, rgba(212, 162, 91, 0.10), rgba(13, 17, 23, 0.55));
	}

	.kpi-pill.on.kpi-gpu {
		border-color: rgba(160, 135, 217, 0.42);
		background: linear-gradient(135deg, rgba(160, 135, 217, 0.10), rgba(13, 17, 23, 0.55));
	}

	.kpi-pill.on.kpi-workspace {
		border-color: rgba(108, 155, 208, 0.42);
		background: linear-gradient(135deg, rgba(108, 155, 208, 0.10), rgba(13, 17, 23, 0.55));
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
		position: relative;
		flex: 1;
		min-height: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr) clamp(260px, 22vw, 340px);
		gap: clamp(8px, 0.6vw, 14px);
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
		height: 5px;
		position: relative;
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
		position: relative;
	}

	.fill {
		height: 100%;
		background: linear-gradient(90deg, var(--accent), #6be6dc);
		transition: width 0.4s cubic-bezier(0.4, 0.0, 0.2, 1);
		border-radius: 999px;
		position: relative;
		overflow: hidden;
	}

	.fill::after {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(
			90deg,
			transparent 0%,
			rgba(255, 255, 255, 0.0) 30%,
			rgba(255, 255, 255, 0.35) 50%,
			rgba(255, 255, 255, 0.0) 70%,
			transparent 100%
		);
		background-size: 250% 100%;
		animation: progressShimmer 1.8s linear infinite;
	}

	@keyframes progressShimmer {
		0% { background-position: 200% 0; }
		100% { background-position: -50% 0; }
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

	.toolbar-right {
		display: inline-flex;
		align-items: center;
		gap: 8px;
	}

	.toolbar-btn {
		height: 34px;
		padding: 0 12px;
		font-size: 12px;
		font-weight: 800;
		letter-spacing: 0.03em;
		color: var(--text-secondary);
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 8px;
		cursor: pointer;
		transition: color 0.12s, border-color 0.12s, background 0.12s;
	}

	.toolbar-btn:hover:not(:disabled) {
		color: var(--accent);
		border-color: rgba(77, 191, 179, 0.45);
		background: rgba(77, 191, 179, 0.06);
	}

	.toolbar-btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.search-wrap {
		position: relative;
		display: inline-flex;
		align-items: center;
	}

	.search-input {
		min-width: 240px;
		max-width: 380px;
		padding: 8px 32px 8px 13px;
		font-size: 13.5px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text-primary);
		outline: none;
		width: 100%;
	}

	.search-input:focus {
		border-color: rgba(77, 191, 179, 0.42);
	}

	.search-input::placeholder {
		color: var(--text-muted);
	}

	.search-clear {
		position: absolute;
		right: 6px;
		top: 50%;
		transform: translateY(-50%);
		width: 22px;
		height: 22px;
		border-radius: 50%;
		border: none;
		background: rgba(100, 116, 139, 0.18);
		color: var(--text-secondary);
		font-size: 14px;
		line-height: 1;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0;
	}

	.search-clear:hover {
		background: rgba(100, 116, 139, 0.32);
		color: var(--text-primary);
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

	.skel-table {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 10px;
		overflow: hidden;
		padding: 0;
		flex: 1;
		min-height: 0;
	}

	.skel-row {
		display: grid;
		gap: 10px;
		align-items: center;
		padding: 12px 14px;
		border-top: 1px solid rgba(100, 116, 139, 0.10);
		min-height: 48px;
	}

	.skel-row-container {
		grid-template-columns: var(--ct-cols);
	}

	.skel-row-history {
		grid-template-columns: var(--hist-cols);
	}

	.skel-row:first-child {
		border-top: none;
	}

	.skel-cell {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		overflow: hidden;
	}

	.skel-cell-stack {
		flex-direction: column;
		align-items: flex-start;
		gap: 5px;
	}

	.skel-cell-actions {
		justify-content: center;
		gap: 6px;
	}

	.skel-bar,
	.skel-pill,
	.skel-spark,
	.skel-chip,
	.skel-btn {
		display: block;
		background: rgba(100, 116, 139, 0.12);
		background-image: linear-gradient(
			90deg,
			rgba(100, 116, 139, 0.08) 0%,
			rgba(100, 116, 139, 0.24) 50%,
			rgba(100, 116, 139, 0.08) 100%
		);
		background-size: 220% 100%;
		animation: skelShimmer 1.4s ease-in-out infinite;
		flex-shrink: 0;
	}

	.skel-bar {
		height: 12px;
		border-radius: 4px;
	}

	.skel-bar-sm {
		height: 9px;
	}

	.skel-pill {
		height: 26px;
		width: 70px;
		border-radius: 6px;
	}

	.skel-chip {
		height: 22px;
		width: 38px;
		border-radius: 4px;
	}

	.skel-spark {
		height: 14px;
		width: 60px;
		border-radius: 3px;
	}

	.skel-btn {
		height: 26px;
		width: 78px;
		border-radius: 6px;
	}

	@keyframes skelShimmer {
		0% { background-position: 220% 0; }
		100% { background-position: -120% 0; }
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

	.empty-hints {
		margin: 28px auto 0;
		max-width: 760px;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 12px;
	}

	.hint-card {
		background: rgba(13, 17, 23, 0.5);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 14px 16px;
		text-align: left;
	}

	.hint-card strong {
		display: block;
		font-size: 13px;
		font-weight: 900;
		color: var(--accent);
		margin-bottom: 6px;
		letter-spacing: 0.02em;
	}

	.hint-card p {
		margin: 0;
		font-size: 12.5px;
		color: var(--text-secondary);
		line-height: 1.55;
	}

	.state kbd,
	.empty-hints kbd {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 18px;
		height: 18px;
		padding: 0 5px;
		margin: 0 2px;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 11px;
		font-weight: 700;
		color: var(--text-primary);
		background: rgba(100, 116, 139, 0.18);
		border: 1px solid rgba(100, 116, 139, 0.3);
		border-radius: 4px;
		vertical-align: middle;
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
		grid-template-columns: var(--ct-cols, 110px 240px 200px minmax(290px, 1fr) 105px 105px 110px 115px 90px 110px 220px);
		gap: 10px;
		align-items: center;
	}

	.container-head {
		padding: 11px 14px;
		background: linear-gradient(180deg, rgba(21, 28, 39, 0.95), rgba(13, 17, 23, 0.92));
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 900;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		flex: 0 0 auto;
		position: sticky;
		top: 0;
		z-index: 2;
		border-bottom: 1px solid rgba(100, 116, 139, 0.42);
		box-shadow: 0 1px 0 rgba(100, 116, 139, 0.14);
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

	.container-row.row-changed {
		animation: rowFlash 2.2s ease-out 1;
	}

	.container-row.row-focused,
	.history-row.row-focused {
		background: rgba(77, 191, 179, 0.10);
		box-shadow: inset 3px 0 0 var(--accent);
		animation: rowFocusPulse 1.8s ease-out 2;
	}

	@keyframes rowFocusPulse {
		0% { background: rgba(77, 191, 179, 0.28); }
		100% { background: rgba(77, 191, 179, 0.10); }
	}

	@keyframes rowFlash {
		0% { background: rgba(77, 191, 179, 0.22); }
		60% { background: rgba(77, 191, 179, 0.08); }
		100% { background: transparent; }
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
		display: block;
		max-width: 100%;
		color: var(--text-primary);
		font-size: 15px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.row-image {
		display: block;
		max-width: 100%;
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
		display: block;
		max-width: 100%;
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
		flex-wrap: nowrap;
		min-width: 0;
		overflow: hidden;
	}

	.row-time {
		font-size: 13px;
		color: var(--text-secondary);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.row-uptime {
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

	.spark-flat.gpu {
		border-bottom-color: rgba(160, 135, 217, 0.32);
	}

	.spark-num.gpu {
		color: #a087d9;
	}

	.spark-flat.gpu-util {
		border-bottom-color: rgba(244, 114, 182, 0.32);
	}

	.spark-num.gpu-util {
		color: #f472b6;
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
		display: inline-flex !important;
		flex-wrap: nowrap;
		gap: 6px;
		width: 100%;
		justify-content: center;
		align-items: center !important;
	}

	.th-actions {
		justify-content: center;
	}

	.h-actions {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		justify-content: center;
		width: 100%;
	}

	.row-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		height: 28px;
		padding: 0 11px;
		font-size: 12px;
		font-weight: 750;
		line-height: 1;
		white-space: nowrap;
		background: rgba(13, 17, 23, 0.5);
		border: 1px solid var(--border);
		border-radius: 6px;
		color: var(--text-secondary);
		cursor: pointer;
		transition: background 0.12s, color 0.12s, border-color 0.12s;
	}

	.row-btn:hover {
		color: var(--accent);
		background: rgba(77, 191, 179, 0.08);
		border-color: rgba(77, 191, 179, 0.42);
	}

	.row-btn:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.row-btn-primary {
		color: var(--accent);
		background: rgba(77, 191, 179, 0.10);
		border-color: rgba(77, 191, 179, 0.42);
	}

	.row-btn-primary:hover {
		background: rgba(77, 191, 179, 0.18);
		border-color: rgba(77, 191, 179, 0.6);
	}

	.row-btn-icon {
		padding: 0;
		width: 28px;
	}

	.row-btn-ico {
		width: 13px;
		height: 13px;
		flex-shrink: 0;
	}

	.row-btn-more {
		opacity: 0;
		transition: opacity 0.12s, background 0.12s, color 0.12s, border-color 0.12s;
		color: var(--text-muted);
		background: transparent;
		border-color: transparent;
	}

	.container-row:hover .row-btn-more,
	.row-btn-more:focus-visible {
		opacity: 1;
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
		grid-template-columns: var(--hist-cols, 60px 260px 100px minmax(220px, 1fr) 140px 75px 110px 170px 200px);
		gap: 10px;
		align-items: center;
	}

	.history-head {
		padding: 11px 14px;
		background: linear-gradient(180deg, rgba(21, 28, 39, 0.95), rgba(13, 17, 23, 0.92));
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 900;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		flex: 0 0 auto;
		position: sticky;
		top: 0;
		z-index: 2;
		border-bottom: 1px solid rgba(100, 116, 139, 0.42);
		box-shadow: 0 1px 0 rgba(100, 116, 139, 0.14);
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
		justify-content: center;
	}

	.memo-chip {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 22px;
		padding: 0 8px;
		font-size: 11px;
		font-weight: 800;
		color: var(--accent);
		background: rgba(77, 191, 179, 0.10);
		border: 1px solid rgba(77, 191, 179, 0.30);
		border-radius: 4px;
		cursor: pointer;
		letter-spacing: 0.02em;
		font-family: inherit;
	}

	.memo-chip:hover {
		background: rgba(77, 191, 179, 0.18);
		border-color: rgba(77, 191, 179, 0.5);
	}

	.memo-chip-active {
		background: rgba(77, 191, 179, 0.24);
		border-color: rgba(77, 191, 179, 0.7);
	}

	.memo-popover {
		position: fixed;
		z-index: 100;
		width: 320px;
		background: rgba(13, 17, 23, 0.98);
		border: 1px solid rgba(77, 191, 179, 0.42);
		border-radius: 8px;
		box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.memo-popover-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 8px 12px;
		font-size: 12px;
		font-weight: 900;
		letter-spacing: 0.04em;
		color: var(--accent);
		background: rgba(77, 191, 179, 0.08);
		border-bottom: 1px solid rgba(77, 191, 179, 0.18);
	}

	.memo-popover-close {
		width: 22px;
		height: 22px;
		padding: 0;
		font-size: 16px;
		line-height: 1;
		background: transparent;
		border: none;
		color: var(--text-muted);
		cursor: pointer;
		border-radius: 4px;
	}

	.memo-popover-close:hover {
		background: rgba(100, 116, 139, 0.16);
		color: var(--text-primary);
	}

	.memo-popover-body {
		padding: 12px;
		font-size: 13px;
		color: var(--text-primary);
		line-height: 1.55;
		max-height: 240px;
		overflow-y: auto;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.memo-popover-foot {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		padding: 8px 12px;
		border-top: 1px solid rgba(100, 116, 139, 0.18);
		font-size: 11.5px;
		color: var(--text-muted);
	}

	.memo-popover-foot strong {
		color: var(--text-secondary);
		font-weight: 800;
	}

	.memo-dash {
		color: var(--text-muted);
		opacity: 0.5;
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

	.history-loadmore {
		list-style: none;
		border-top: 1px solid rgba(100, 116, 139, 0.18);
	}

	.loadmore-btn {
		width: 100%;
		padding: 12px 14px;
		background: rgba(13, 17, 23, 0.4);
		border: none;
		color: var(--accent);
		font-weight: 800;
		font-size: 13px;
		cursor: pointer;
		text-align: center;
	}

	.loadmore-btn:hover:not(:disabled) {
		background: rgba(77, 191, 179, 0.08);
		filter: brightness(1.06);
	}

	.loadmore-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.ctx-menu {
		position: fixed;
		z-index: 100;
		min-width: 180px;
		padding: 6px;
		background: rgba(13, 17, 23, 0.98);
		border: 1px solid var(--border);
		border-radius: 8px;
		box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	.ctx-head {
		padding: 6px 10px 8px;
		font-size: 11.5px;
		color: var(--text-muted);
		border-bottom: 1px solid rgba(100, 116, 139, 0.18);
		margin-bottom: 4px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.ctx-item {
		padding: 7px 10px;
		font-size: 13px;
		font-weight: 700;
		background: transparent;
		border: none;
		color: var(--text-primary);
		text-align: left;
		border-radius: 5px;
		cursor: pointer;
	}

	.ctx-item:hover:not(:disabled) {
		background: rgba(77, 191, 179, 0.12);
		color: var(--accent);
	}

	.ctx-item.danger {
		color: #e69b9b;
	}

	.ctx-item.danger:hover:not(:disabled) {
		background: rgba(217, 112, 112, 0.12);
		color: #f0bcbc;
	}

	.ctx-item:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.ctx-divider {
		height: 1px;
		background: rgba(100, 116, 139, 0.18);
		margin: 4px 0;
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
		position: relative;
		display: inline-flex;
		align-items: baseline;
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
	.th small {
		font-size: 9.5px;
		font-weight: 700;
		color: var(--text-muted);
		letter-spacing: 0;
		text-transform: none;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.col-resize {
		position: absolute;
		top: -11px;
		right: -10px;
		width: 10px;
		height: calc(100% + 22px);
		cursor: col-resize;
		z-index: 3;
		background: transparent;
	}

	.col-resize:hover {
		background: rgba(77, 191, 179, 0.22);
	}

	.drag-guideline {
		position: fixed;
		top: 0;
		bottom: 0;
		width: 1px;
		background: linear-gradient(180deg, rgba(77, 191, 179, 0.0) 0%, rgba(77, 191, 179, 0.65) 12%, rgba(77, 191, 179, 0.65) 88%, rgba(77, 191, 179, 0.0) 100%);
		box-shadow: 0 0 6px rgba(77, 191, 179, 0.5);
		z-index: 99;
		pointer-events: none;
	}

	.th.sortable {
		cursor: pointer;
	}

	.th.sortable:hover {
		color: var(--text-primary);
	}

	.th.sortable::after {
		content: '⇅';
		margin-left: 4px;
		font-size: 10px;
		color: var(--text-muted);
		opacity: 0;
		transition: opacity 0.12s;
	}

	.th.sortable:hover::after {
		opacity: 0.55;
	}

	.th.active {
		color: var(--accent);
		font-weight: 950;
		text-shadow: 0 0 8px rgba(77, 191, 179, 0.25);
	}

	.th.active::after {
		opacity: 0;
	}

	.container-head .th.active,
	.history-head .th.active {
		position: relative;
	}

	.container-head .th.active::before,
	.history-head .th.active::before {
		content: '';
		position: absolute;
		left: 0;
		right: 0;
		bottom: -12px;
		height: 2px;
		background: var(--accent);
		border-radius: 2px;
	}

	@media (max-width: 900px) {
		.title-suffix {
			display: none;
		}

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
			grid-template-columns: auto 1fr !important;
			gap: 6px 10px;
			padding: 10px 12px;
		}

		.h-name {
			grid-column: 1 / -1;
		}

		.h-time,
		.h-memo {
			grid-column: 1 / -1;
		}

		.history-row > * {
			border-right: none;
			padding-right: 0;
		}

		.container-head {
			display: none;
		}

		.container-row {
			grid-template-columns: auto 1fr !important;
			gap: 6px 10px;
			padding: 10px 12px;
		}

		.container-row > * {
			border-right: none;
			padding-right: 0;
		}

		.row-name,
		.row-host,
		.row-resources,
		.row-actions {
			grid-column: 1 / -1;
			justify-content: center !important;
			padding-top: 4px;
		}

		.col-resize {
			display: none;
		}

		.main-grid {
			grid-template-columns: minmax(0, 1fr);
		}

		.main-grid .side-panel {
			display: none;
		}
	}
</style>
