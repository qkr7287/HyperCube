<!--
  EventList — 컨테이너 라이프사이클 이벤트 목록 패널.
  /api/my-containers/<id>/events/ 응답 그대로 받아 시간 내림차순으로 표시.
  kind 별 색/아이콘 매핑 + tooltip 으로 추가 필드 (exitCode/signal/healthStatus) 노출.
-->
<script lang="ts">
	import { formatDateTime } from '$lib/utils/container-dashboard';
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
					<span class="time">{formatDateTime(ev.ts)}</span>
				</li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	.panel {
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		border-radius: var(--radius-panel);
		padding: clamp(6px, 0.6vw, 14px);
		margin-top: 18px;
		transition: border-color var(--ease-fast);
	}
	.panel:hover {
		border-color: rgba(48, 213, 200, 0.22);
	}
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 18px;
		margin-bottom: clamp(4px, 0.4vw, 10px);
	}
	h2 {
		font-size: 20px;
		margin-bottom: 4px;
	}
	.panel-header p {
		font-size: 12px;
		color: var(--text-secondary);
	}
	.count {
		font-size: 11px;
		color: var(--text-muted);
		padding: 4px 10px;
		border-radius: 999px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.86);
	}

	.empty {
		padding: 16px;
		border-radius: 12px;
		background: rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
		font-size: 13px;
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
		gap: 3px;
		max-height: clamp(120px, 16vh, 300px);
		overflow-y: auto;
	}

	.list li {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.62);
		border: 1px solid rgba(31, 41, 55, 0.6);
		font-size: 11px;
	}

	.dot {
		flex: 0 0 auto;
		width: 6px;
		height: 6px;
		border-radius: 50%;
	}

	.badge {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 7px;
		border-radius: 999px;
		font-size: 10px;
		font-weight: 700;
	}
	.badge.success { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); }
	.badge.warn    { background: rgba(234, 179, 8, 0.18);  color: #fde047; border: 1px solid rgba(234, 179, 8, 0.35); }
	.badge.danger  { background: rgba(239, 68, 68, 0.18);  color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }
	.badge.info    { background: rgba(59, 130, 246, 0.18); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.35); }
	.badge.muted   { background: rgba(100, 116, 139, 0.16); color: var(--text-secondary); border: 1px solid rgba(100, 116, 139, 0.32); }

	.icon {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 10px;
	}

	.detail {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 11px;
		font-weight: 700;
		padding: 2px 6px;
		border-radius: 4px;
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
		margin-left: auto;
		font-size: 11px;
		color: var(--text-secondary);
	}
</style>
