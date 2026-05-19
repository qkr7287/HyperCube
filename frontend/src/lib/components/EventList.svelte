<!--
  EventList — 컨테이너 라이프사이클 이벤트 목록 패널.
  /api/my-containers/<id>/events/ 응답 그대로 받아 시간 내림차순으로 표시.
  kind 별 색/아이콘 매핑 + tooltip 으로 추가 필드 (exitCode/signal/healthStatus) 노출.
-->
<script lang="ts">
	import { formatDateTime, formatRelativeTime } from '$lib/utils/container-dashboard';
	import StateBox from './StateBox.svelte';
	import InfoTooltip from './InfoTooltip.svelte';

	const HEADER_HELP = `컨테이너 라이프사이클 이벤트. agent 가 docker events stream 으로 받아 backend ContainerEvent 에 저장.

종류:
· start / stop / die / restart / pause / unpause / kill
· oom (메모리 한도 초과로 OOM killer 가 죽임)
· health_status (HEALTHCHECK 결과 전환 — healthy / unhealthy / starting)

메트릭과 달리 cleanup 없이 영구 보존. 컨테이너 삭제 시에만 함께 사라짐. 최대 200건 한 번에 fetch.`;

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

	// 최근 24h 운영 요약 — panel 하단 footer 에 항상 표시.
	// 이벤트가 1~2건이라 list 가 휑할 때도 "지금 안정 상태인가" 한 줄 직관 제공.
	const SUMMARY_WINDOW_MS = 24 * 60 * 60 * 1000;
	type Summary = { restart: number; exit: number; oom: number; unhealthy: number };
	let summary = $derived.by<Summary>(() => {
		const cutoff = Date.now() - SUMMARY_WINDOW_MS;
		const out: Summary = { restart: 0, exit: 0, oom: 0, unhealthy: 0 };
		for (const ev of events) {
			const ts = new Date(ev.ts).getTime();
			if (!Number.isFinite(ts) || ts < cutoff) continue;
			if (ev.kind === 'restart') out.restart += 1;
			else if (ev.kind === 'oom') out.oom += 1;
			else if (ev.kind === 'die' && typeof ev.exit_code === 'number' && ev.exit_code !== 0) out.exit += 1;
			else if (ev.kind === 'kill') out.exit += 1;
			else if (ev.kind === 'health_status' && ev.health_status === 'unhealthy') out.unhealthy += 1;
		}
		return out;
	});
	let summaryTone = $derived.by<'ok' | 'warn' | 'danger'>(() => {
		if (summary.oom > 0 || summary.unhealthy > 0) return 'danger';
		if (summary.restart > 0 || summary.exit > 0) return 'warn';
		return 'ok';
	});
</script>

<section class="panel">
	<div class="panel-header slim">
		<div>
			<h2>최근 이벤트<InfoTooltip text={HEADER_HELP} placement="bottom-start" /></h2>
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
				<li class="row" data-tone={m.tone} style:--kind={m.color}>
					<span class="row-icon" aria-hidden="true">{m.icon}</span>
					<div class="row-body">
						<div class="row-head">
							<span class="kind-label">{m.label}</span>
							{#if detail(ev)}
								<span class="detail" data-tone={detailTone(ev)}>{detail(ev)}</span>
							{/if}
						</div>
						<div class="row-time">
							<span class="time-abs">{formatDateTime(ev.ts)}</span>
							<span class="time-rel">· {formatRelativeTime(ev.ts)}</span>
						</div>
					</div>
				</li>
			{/each}
		</ul>
		{#if displayed.length <= 3 && summaryTone === 'ok'}
			<!-- 이벤트 거의 없을 때 — 빈 공간이 휑하지 않도록 안정 상태 hint.
			     summary footer 와 중복 정보지만 큰 빈 공간보단 안내가 낫다. -->
			<div class="stable-hint">
				<span class="hint-icon" aria-hidden="true">✓</span>
				<div class="hint-body">
					<strong>최근 큰 이벤트 없음</strong>
					<span>지난 24시간 안정 상태. 재시작·OOM·unhealthy 0건.</span>
				</div>
			</div>
		{/if}
	{/if}

	<!-- 운영 요약 footer — 최근 24h 의 restart/exit/oom/unhealthy 집계.
	     이벤트 목록이 짧아도 "지금 안정한가" 한눈에. -->
	<div class="summary" data-tone={summaryTone} aria-label="최근 24시간 운영 요약">
		<span class="summary-window">최근 24h</span>
		<span class="summary-counts">
			<span><b>{summary.restart}</b>재시작</span>
			<span><b>{summary.exit}</b>비정상 종료</span>
			<span><b>{summary.oom}</b>OOM</span>
			<span><b>{summary.unhealthy}</b>unhealthy</span>
		</span>
		<span class="summary-verdict">
			{#if summaryTone === 'ok'}안정{:else if summaryTone === 'warn'}주의{:else}위험{/if}
		</span>
	</div>
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
		overflow-y: auto;
		overflow-x: hidden;
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
		gap: 5px;
		flex: 0 1 auto;
		min-height: 0;
		min-width: 0;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		max-height: none;
		overflow: visible;
		padding: 0 2px 0 0;
	}

	/* 한 row 구조 — 좌측 colored stripe + icon 박스 + body (라벨/디테일/시간) */
	.row {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: stretch;
		gap: 9px;
		padding: 8px 10px 8px 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.58);
		border: 1px solid rgba(100, 116, 139, 0.16);
		border-left: 3px solid var(--kind, rgba(148, 163, 184, 0.5));
		transition: border-color var(--ease-fast), background-color var(--ease-fast);
	}
	.row:hover {
		background: rgba(13, 17, 23, 0.75);
		border-color: rgba(48, 213, 200, 0.32);
		border-left-color: var(--kind, rgba(148, 163, 184, 0.7));
	}

	.row-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 26px;
		height: 26px;
		border-radius: 6px;
		background: color-mix(in srgb, var(--kind) 18%, transparent);
		color: var(--kind);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 13px;
		font-weight: 800;
		flex: 0 0 auto;
	}

	.row-body {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}
	.row-head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		flex-wrap: wrap;
	}
	.kind-label {
		font-size: 12px;
		font-weight: 800;
		letter-spacing: 0.01em;
		color: var(--text-primary);
	}
	.detail {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 10.5px;
		font-weight: 750;
		padding: 1px 6px;
		border-radius: 5px;
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
	.row-time {
		display: flex;
		align-items: baseline;
		gap: 6px;
		font-size: 10.5px;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		overflow: hidden;
	}
	.time-abs {
		color: var(--text-secondary);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	/* 이벤트 적을 때 빈 공간 채우는 안정 상태 hint */
	.stable-hint {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 12px 14px;
		margin-top: 8px;
		border-radius: 9px;
		background:
			linear-gradient(180deg, rgba(16, 185, 129, 0.06), rgba(16, 185, 129, 0.02)),
			rgba(13, 17, 23, 0.4);
		border: 1px dashed rgba(16, 185, 129, 0.3);
		flex: 0 0 auto;
	}
	.hint-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: rgba(16, 185, 129, 0.18);
		color: #6ee7b7;
		font-size: 16px;
		font-weight: 900;
		flex: 0 0 auto;
	}
	.hint-body {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}
	.hint-body strong {
		font-size: 12px;
		font-weight: 800;
		color: var(--text-primary);
	}
	.hint-body span {
		font-size: 10.5px;
		color: var(--text-muted);
	}

	/* 운영 요약 footer — list 가 짧을 때도 "지금 안정 상태" 한눈 제공.
	   tone 별 좌측 stripe + verdict pill. */
	.summary {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 9px;
		margin-top: auto;
		padding: 7px 10px 7px 14px;
		border-radius: 8px;
		background: rgba(2, 6, 12, 0.4);
		border: 1px solid rgba(100, 116, 139, 0.16);
		position: relative;
		overflow: hidden;
	}
	.summary::before {
		content: '';
		position: absolute;
		left: 0;
		top: 6px;
		bottom: 6px;
		width: 3px;
		border-radius: 2px;
		background: rgba(148, 163, 184, 0.55);
	}
	.summary-window {
		color: var(--text-muted);
		font-size: 9.5px;
		font-weight: 900;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		white-space: nowrap;
	}
	.summary-counts {
		display: inline-flex;
		flex-wrap: wrap;
		gap: 4px 10px;
		color: var(--text-secondary);
		font-size: 10.5px;
		font-weight: 750;
		font-variant-numeric: tabular-nums;
	}
	.summary-counts span {
		display: inline-flex;
		align-items: baseline;
		gap: 3px;
	}
	.summary-counts b {
		color: var(--text-primary);
		font-weight: 900;
	}
	.summary-verdict {
		font-size: 10.5px;
		font-weight: 900;
		letter-spacing: 0.02em;
		padding: 3px 9px;
		border-radius: 999px;
		background: rgba(13, 17, 23, 0.6);
		border: 1px solid rgba(100, 116, 139, 0.22);
		color: var(--text-secondary);
		white-space: nowrap;
	}
	.summary[data-tone='ok']::before {
		background: #34d399;
		box-shadow: 0 0 8px rgba(52, 211, 153, 0.5);
	}
	.summary[data-tone='ok'] .summary-verdict {
		color: #6ee7b7;
		border-color: rgba(16, 185, 129, 0.36);
		background: rgba(16, 185, 129, 0.08);
	}
	.summary[data-tone='warn']::before {
		background: #fbbf24;
		box-shadow: 0 0 8px rgba(251, 191, 36, 0.5);
	}
	.summary[data-tone='warn'] .summary-verdict {
		color: #fde68a;
		border-color: rgba(251, 191, 36, 0.4);
		background: rgba(251, 191, 36, 0.1);
	}
	.summary[data-tone='warn'] .summary-counts b {
		color: #fde68a;
	}
	.summary[data-tone='danger']::before {
		background: #f87171;
		box-shadow: 0 0 8px rgba(248, 113, 113, 0.5);
	}
	.summary[data-tone='danger'] .summary-verdict {
		color: #fca5a5;
		border-color: rgba(239, 68, 68, 0.4);
		background: rgba(239, 68, 68, 0.1);
	}
	.summary[data-tone='danger'] .summary-counts b {
		color: #fca5a5;
	}
</style>
