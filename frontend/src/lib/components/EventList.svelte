<!--
  EventList — 컨테이너 라이프사이클 이벤트 목록 패널.
  /api/my-containers/<id>/events/ 응답 그대로 받아 시간 내림차순으로 표시.
  kind 별 색/아이콘 매핑 + tooltip 으로 추가 필드 (exitCode/signal/healthStatus) 노출.
-->
<script lang="ts">
	import { formatDateTime, formatRelativeTime } from '$lib/utils/container-dashboard';
	import StateBox from './StateBox.svelte';

	export type EventRow = {
		id: number;
		ts: string;
		kind: string;
		exit_code?: number | null;
		signal?: string;
		health_status?: string;
	};

	let {
		events = [],
		loading = false,
		errorMsg = '',
	}: {
		events?: EventRow[];
		loading?: boolean;
		errorMsg?: string;
	} = $props();

	// kind → 시각 표현. EChartLine 의 markLine 색과 일관 유지 → 호출처에서 같은 매핑 사용.
	const KIND_META: Record<string, { label: string; color: string; tone: string; icon: string }> = {
		start:         { label: '시작',     color: '#10b981', tone: 'success', icon: '▶' },
		stop:          { label: '중지',     color: '#f59e0b', tone: 'warn',    icon: '■' },
		die:           { label: '종료',     color: '#fb923c', tone: 'warn',    icon: '✖' },
		restart:       { label: '재시작',   color: '#3b82f6', tone: 'info',    icon: '↻' },
		pause:         { label: '일시정지', color: '#eab308', tone: 'warn',    icon: '❚❚' },
		unpause:       { label: '재개',     color: '#10b981', tone: 'success', icon: '▶' },
		kill:          { label: '강제종료', color: '#ef4444', tone: 'danger',  icon: '✕' },
		oom:           { label: 'OOM',      color: '#ef4444', tone: 'danger',  icon: '☠' },
		health_status: { label: 'Health',   color: '#06b6d4', tone: 'info',    icon: '♡' },
	};

	function metaFor(kind: string) {
		return KIND_META[kind] || { label: kind, color: '#94a3b8', tone: 'muted', icon: '·' };
	}

	function detail(e: EventRow): string {
		const parts: string[] = [];
		if (e.kind === 'die' && typeof e.exit_code === 'number') parts.push(`exit ${e.exit_code}`);
		if (e.kind === 'kill' && e.signal) parts.push(e.signal);
		if (e.kind === 'health_status' && e.health_status) parts.push(e.health_status);
		if (e.kind === 'oom') parts.push('Out of Memory');
		return parts.join(' · ');
	}

	function detailTone(e: EventRow): 'danger' | 'warn' | 'muted' {
		if (e.kind === 'oom') return 'danger';
		if (e.kind === 'die' && typeof e.exit_code === 'number' && e.exit_code !== 0) return 'danger';
		if (e.kind === 'kill') return 'danger';
		if (e.kind === 'health_status' && e.health_status === 'unhealthy') return 'danger';
		if (e.kind === 'health_status' && e.health_status === 'starting') return 'warn';
		return 'muted';
	}

	let displayed = $derived([...events].reverse()); // 시간 내림차순 (최신이 위)
</script>

<section class="panel">
	<div class="panel-header slim">
		<div>
			<h2>최근 이벤트</h2>
		</div>
		<span class="count">{events.length}건</span>
	</div>

	{#if errorMsg}
		<StateBox kind="error" message={errorMsg} />
	{:else if loading && events.length === 0}
		<StateBox kind="loading" message="이벤트 불러오는 중..." />
	{:else if displayed.length === 0}
		<StateBox kind="empty" message="표시할 이벤트가 없습니다." icon="📭" />
	{:else}
		<ul class="list">
			{#each displayed as ev (ev.id)}
				{@const m = metaFor(ev.kind)}
				<li>
					<span class="dot" style:background={m.color}></span>
					<span class="badge {m.tone}" title={ev.kind}>
						<span class="icon">{m.icon}</span>{m.label}
					</span>
					{#if detail(ev)}
						<span class="detail" data-tone={detailTone(ev)}>{detail(ev)}</span>
					{/if}
					<span class="time" title={formatDateTime(ev.ts)}>{formatRelativeTime(ev.ts)}</span>
				</li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	.panel {
		background:
			linear-gradient(180deg, rgba(21, 27, 38, 0.98), rgba(15, 20, 29, 0.98)),
			rgba(18, 23, 32, 0.96);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: var(--radius-panel);
		padding: clamp(5px, 0.45vw, 8px);
		margin-top: 0;
		transition: border-color var(--ease-fast);
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		height: 100%;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
		position: relative;
		box-shadow:
			0 8px 24px rgba(0, 0, 0, 0.16),
			inset 0 1px 0 rgba(255, 255, 255, 0.025);
	}
	.panel::before {
		content: '';
		position: absolute;
		inset: 0 0 auto;
		height: 2px;
		background: linear-gradient(90deg, rgba(96, 165, 250, 0.58), rgba(48, 213, 200, 0.14));
		opacity: 0.68;
	}
	.panel:hover {
		border-color: rgba(48, 213, 200, 0.22);
	}
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
		margin-bottom: 5px;
		padding-bottom: 5px;
		border-bottom: 1px solid rgba(100, 116, 139, 0.12);
	}
	h2 {
		font-size: 14px;
		margin-bottom: 0;
	}
	.panel-header p {
		display: none;
		font-size: 11px;
		color: var(--text-secondary);
	}
	.count {
		font-size: 10px;
		color: var(--text-muted);
		padding: 2px 7px;
		border-radius: 999px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.86);
	}

	.empty {
		padding: 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
		font-size: 11px;
		color: var(--text-secondary);
	}
	.empty.error {
		color: #fecaca;
		border-color: rgba(239, 68, 68, 0.3);
		background: rgba(127, 29, 29, 0.18);
	}

	.list {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 4px;
		flex: 1 1 0;
		min-height: 0;
		min-width: 0;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		max-height: none;
		overflow-y: auto;
		padding-right: 2px;
	}

	.list li {
		display: grid;
		grid-template-columns: auto auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 7px;
		padding: 7px 9px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.58);
		border: 1px solid rgba(100, 116, 139, 0.16);
		font-size: 11.5px;
		transition: border-color var(--ease-fast), background-color var(--ease-fast);
	}
	.list li:hover {
		border-color: rgba(48, 213, 200, 0.32);
		background: rgba(13, 17, 23, 0.75);
	}

	.dot {
		flex: 0 0 auto;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		box-shadow: 0 0 8px currentColor;
	}

	.badge {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 2px 8px;
		border-radius: 999px;
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.01em;
	}
	.badge.success { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); }
	.badge.warn    { background: rgba(234, 179, 8, 0.18);  color: #fde047; border: 1px solid rgba(234, 179, 8, 0.35); }
	.badge.danger  { background: rgba(239, 68, 68, 0.18);  color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }
	.badge.info    { background: rgba(59, 130, 246, 0.18); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.35); }
	.badge.muted   { background: rgba(100, 116, 139, 0.16); color: var(--text-secondary); border: 1px solid rgba(100, 116, 139, 0.32); }

	.icon {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 11px;
	}

	.detail {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 10.5px;
		font-weight: 750;
		padding: 2px 7px;
		border-radius: 5px;
		justify-self: start;
	}
	.detail[data-tone='muted'] {
		color: var(--text-muted);
	}
	.detail[data-tone='warn'] {
		color: #fde68a;
		background: rgba(251, 191, 36, 0.12);
	}
	.detail[data-tone='danger'] {
		color: #fca5a5;
		background: rgba(239, 68, 68, 0.14);
	}

	.time {
		grid-column: -2 / -1;
		font-size: 10.5px;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
</style>
