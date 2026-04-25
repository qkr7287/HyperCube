<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import AutoSlideCarousel from './AutoSlideCarousel.svelte';

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
		pageSize = 5,
		intervalMs = 5500,
		onSelect = (_container: any) => {},
	}: {
		events?: EventRow[];
		pageSize?: number;
		intervalMs?: number;
		onSelect?: (container: any) => void;
	} = $props();

	function formatClock(date: Date): string {
		try {
			return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
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
			<span>실시간 이벤트 / 경고</span>
			<InfoTooltip text={`서버에서 지금 주의가 필요한 항목입니다.\n\n• 장애 · 재시작 루프 → 경고 (빨강)\n• 일시정지 · 고부하 → 주의 (노랑)\n• 등급 위→아래 정렬\n• 대상 클릭 = 컨테이너 상세\n• 5건씩 자동 순환`} placement="top-start" />
		</div>
		<small>{events.length}건</small>
	</div>
	{#if events.length === 0}
		<div class="empty">현재 주의 항목이 없습니다. 서버 상태 양호.</div>
	{:else}
		<div class="body">
			<AutoSlideCarousel items={events} pageSize={pageSize} intervalMs={intervalMs}>
				{#snippet children(pageItems: EventRow[])}
					<div class="list">
						{#each pageItems as event (event.id)}
							<button
								type="button"
								class={`row ${event.severity}`}
								onclick={() => event.container && onSelect(event.container)}
								disabled={!event.container}
							>
								<span class={`sev ${event.severity}`}>{severityLabel(event.severity)}</span>
								<span class="time">{formatClock(event.at)}</span>
								<span class="stack" title={event.stack}>{event.stack}</span>
								<span class="target" title={event.target}>{event.target}</span>
								<span class="msg" title={event.message}>{event.message}</span>
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
	}

	.live {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: #34d399;
		box-shadow: 0 0 10px rgba(52, 211, 153, 0.6);
		animation: pulse 1.6s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.6; transform: scale(0.85); }
		50% { opacity: 1; transform: scale(1.2); }
	}

	.head small {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
	}

	.body {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
	}

	.list {
		display: grid;
		grid-auto-flow: row;
		grid-auto-rows: minmax(0, 1fr);
		gap: 4px;
		min-height: 0;
		height: 100%;
	}

	.row {
		display: grid;
		grid-template-columns: 38px 56px minmax(0, 1fr) minmax(0, 1.4fr) minmax(0, 2fr);
		align-items: center;
		gap: 6px;
		padding: 4px 9px;
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-left: 3px solid #94a3b8;
		border-radius: 6px;
		background: rgba(15, 23, 42, 0.55);
		text-align: left;
		cursor: pointer;
		min-width: 0;
		min-height: 0;
		font-size: 11px;
		transition: border-color 0.12s ease;
	}

	.row:disabled {
		cursor: default;
	}

	.row:hover:not(:disabled) {
		border-color: rgba(48, 213, 200, 0.45);
	}

	.row.critical {
		border-left-color: #f87171;
		background: rgba(248, 113, 113, 0.06);
	}

	.row.warn {
		border-left-color: #fbbf24;
		background: rgba(251, 191, 36, 0.05);
	}

	.row.info {
		border-left-color: #60a5fa;
	}

	.sev {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 2px 0;
		border-radius: 999px;
		font-size: 9px;
		font-weight: 800;
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

	.time {
		color: var(--text-muted);
		font-family: 'JetBrains Mono', 'Consolas', monospace;
		font-size: 10px;
		font-weight: 700;
	}

	.stack {
		color: var(--text-secondary);
		font-weight: 700;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.target {
		color: #30d5c8;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.msg {
		color: var(--text-secondary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.empty {
		padding: 14px;
		border: 1px dashed rgba(100, 116, 139, 0.28);
		border-radius: 8px;
		color: var(--text-muted);
		font-size: 11px;
		text-align: center;
		font-style: italic;
	}
</style>
