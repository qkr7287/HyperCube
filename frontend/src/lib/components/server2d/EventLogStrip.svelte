<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import AutoSlideCarousel from './AutoSlideCarousel.svelte';
	import { view } from '$lib/stores/server2d-view.svelte';

	type EventRow = {
		id: string;
		severity: 'warn' | 'critical' | 'info';
		at: Date;
		stack: string;
		target: string;
		message: string;
		container?: any;
		action?: string;
	};

	let {
		events = [] as EventRow[],
		pageSize = 4,
		intervalMs = 6000,
		onSelect = (_container: any) => {},
	}: {
		events?: EventRow[];
		pageSize?: number;
		intervalMs?: number;
		onSelect?: (container: any) => void;
	} = $props();

	function formatClock(date: Date): string {
		try {
			return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
		} catch {
			return '-';
		}
	}

	function severityLabel(sev: 'critical' | 'warn' | 'info'): string {
		if (sev === 'critical') return '경고';
		if (sev === 'warn') return '주의';
		return '정보';
	}
</script>

<section class="events">
	<div class="head">
		<div class="title">
			<i class="live"></i>
			<span>실시간 이벤트</span>
			<InfoTooltip text={`서버에서 지금 주의가 필요한 항목입니다.\n\n• 갱신 주기: WebSocket 실시간 (Agent 송출 즉시 반영)\n• 추이 범위(1m/5m/1h/24h/7d) 영향 없음\n\n• 장애 · 재시작 루프 → 경고 (빨강)\n• 일시정지 · 고부하 → 주의 (노랑)\n• 등급 위→아래 정렬\n• 카드 클릭 = 컨테이너 상세\n• 자동 순환`} placement="bottom-end" />
		</div>
		<small>{events.length}건</small>
	</div>
	{#if events.length === 0}
		<div class="empty">
			<span class="ok">●</span>
			<strong>서버 정상</strong>
			<small>주의 항목 없음</small>
		</div>
	{:else}
		<div class="body">
			<AutoSlideCarousel
				items={events}
				pageSize={pageSize}
				intervalMs={intervalMs}
				userPaused={view.eventsPaused}
				hideBar={true}
				pauseLabel="이벤트 슬라이드"
			>
				{#snippet children(pageItems: EventRow[])}
					<div class="list">
						{#each pageItems as event (event.id)}
							<button
								type="button"
								class={`row ${event.severity}`}
								onclick={() => event.container && onSelect(event.container)}
								disabled={!event.container}
							>
								<header>
									<span class={`sev ${event.severity}`}>{severityLabel(event.severity)}</span>
									<strong class="target" title={event.target}>{event.target}</strong>
									<span class="time">{formatClock(event.at)}</span>
								</header>
								<p class="msg" title={`${event.stack} · ${event.message}`}>
									<em class="stack-tag">{event.stack}</em>
									<span>{event.message}</span>
								</p>
							</button>
						{/each}
					</div>
				{/snippet}
			</AutoSlideCarousel>
		</div>
	{/if}
</section>

<style>
	.events {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 6px;
		min-width: 0;
		min-height: 0;
		height: 100%;
	}

	.head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
		min-height: 22px;
	}

	.title {
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 850;
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		overflow: hidden;
	}

	.title span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.live {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #34d399;
		box-shadow: 0 0 8px rgba(52, 211, 153, 0.6);
		animation: pulse 1.6s ease-in-out infinite;
		flex: 0 0 auto;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.6; transform: scale(0.85); }
		50% { opacity: 1; transform: scale(1.2); }
	}

	.head small {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		flex: 0 0 auto;
	}

	.body {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 5px;
		min-height: 0;
		align-content: flex-start;
	}

	.row {
		display: grid;
		grid-template-rows: auto auto;
		gap: 3px;
		padding: 7px 10px 8px;
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-left: 3px solid #94a3b8;
		border-radius: 7px;
		background: rgba(15, 23, 42, 0.55);
		text-align: left;
		cursor: pointer;
		min-width: 0;
		font-size: 11px;
		flex: 0 0 auto;
		transition: border-color 0.12s ease, transform 0.12s ease, background-color 0.12s ease;
	}

	.row:disabled {
		cursor: default;
	}

	.row:not(:disabled):hover {
		border-color: rgba(48, 213, 200, 0.5);
		transform: translateY(-1px);
	}

	.row.critical {
		border-left-color: #f87171;
		background: rgba(248, 113, 113, 0.07);
	}

	.row.warn {
		border-left-color: #fbbf24;
		background: rgba(251, 191, 36, 0.06);
	}

	.row.info {
		border-left-color: #60a5fa;
	}

	.row header {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}

	.sev {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 1px 6px;
		border-radius: 999px;
		font-size: 9px;
		font-weight: 800;
		flex: 0 0 auto;
	}

	.sev.critical {
		background: rgba(248, 113, 113, 0.22);
		color: #f87171;
	}

	.sev.warn {
		background: rgba(251, 191, 36, 0.22);
		color: #fbbf24;
	}

	.sev.info {
		background: rgba(96, 165, 250, 0.2);
		color: #60a5fa;
	}

	.target {
		color: var(--text-primary);
		font-size: 11px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.time {
		color: var(--text-muted);
		font-family: 'JetBrains Mono', 'Consolas', monospace;
		font-size: 10px;
		font-weight: 700;
		flex: 0 0 auto;
	}

	.msg {
		display: flex;
		gap: 5px;
		align-items: baseline;
		margin: 0;
		padding-left: 4px;
		min-width: 0;
		overflow: hidden;
	}

	.stack-tag {
		font-style: normal;
		color: #94a3b8;
		font-size: 9px;
		font-weight: 800;
		background: rgba(2, 6, 23, 0.45);
		padding: 1px 6px;
		border-radius: 999px;
		flex: 0 0 auto;
	}

	.msg span {
		color: var(--text-secondary);
		font-size: 10px;
		font-weight: 700;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.empty {
		display: grid;
		grid-template-columns: auto auto auto;
		justify-content: center;
		align-items: center;
		gap: 8px;
		padding: 16px 14px;
		border: 1px dashed rgba(52, 211, 153, 0.3);
		border-radius: 8px;
		background: rgba(52, 211, 153, 0.05);
		min-height: 0;
	}

	.empty .ok {
		color: #34d399;
		font-size: 12px;
	}

	.empty strong {
		color: #34d399;
		font-size: 12px;
		font-weight: 800;
	}

	.empty small {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
	}
</style>
