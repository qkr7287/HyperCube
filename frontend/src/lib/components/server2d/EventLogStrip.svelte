<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';

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
		onSelect = (_container: any) => {},
	}: {
		events?: EventRow[];
		onSelect?: (container: any) => void;
	} = $props();

	function formatClock(date: Date): string {
		try {
			return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
		} catch {
			return '-';
		}
	}
</script>

<section class="events">
	<div class="head">
		<div class="title">
			<i class="live"></i>
			<span>실시간 이벤트 / 경고</span>
			<InfoTooltip text={`서버에서 지금 주의가 필요한 항목입니다.\n\n• 장애 · 재시작 루프 → 경고(빨강)\n• 일시정지 · 고부하 → 주의(노랑)\n• 등급 위→아래 정렬\n• 대상 클릭 = 컨테이너 상세`} placement="top-start" />
		</div>
		<small>{events.length}건 표시</small>
	</div>
	<div class="body">
		<table>
			<thead>
				<tr>
					<th class="sev-col">등급</th>
					<th class="time-col">시각</th>
					<th>스택</th>
					<th>대상</th>
					<th>내용</th>
					<th class="act-col">조치</th>
				</tr>
			</thead>
			<tbody>
				{#each events.slice(0, 20) as event (event.id)}
					<tr class={event.severity}>
						<td class="sev-col">
							<span class={`sev ${event.severity}`}>
								{event.severity === 'critical' ? '경고' : event.severity === 'warn' ? '주의' : '정보'}
							</span>
						</td>
						<td class="time-col">{formatClock(event.at)}</td>
						<td class="stack">{event.stack}</td>
						<td>
							{#if event.container}
								<button type="button" class="link" onclick={() => onSelect(event.container)}>{event.target}</button>
							{:else}
								{event.target}
							{/if}
						</td>
						<td class="msg">{event.message}</td>
						<td class="act-col">{event.action ?? '-'}</td>
					</tr>
				{:else}
					<tr class="empty-row">
						<td colspan="6">현재 주의가 필요한 항목이 없습니다. 서버 상태 양호.</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</section>

<style>
	.events {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
		min-height: 0;
	}

	.head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
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
		font-weight: 700;
	}

	.body {
		overflow: auto;
		flex: 1;
		min-height: 0;
		border: 1px solid rgba(100, 116, 139, 0.16);
		border-radius: 8px;
		background: rgba(15, 23, 42, 0.42);
	}

	.body::-webkit-scrollbar {
		width: 6px;
		height: 6px;
	}
	.body::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.24);
		border-radius: 3px;
	}

	table {
		width: 100%;
		border-collapse: separate;
		border-spacing: 0;
		font-size: 11px;
	}

	thead th {
		position: sticky;
		top: 0;
		z-index: 2;
		padding: 6px 8px;
		text-align: left;
		background: rgba(13, 17, 23, 0.96);
		border-bottom: 1px solid rgba(100, 116, 139, 0.2);
		color: var(--text-muted);
		font-weight: 800;
		font-size: 10px;
	}

	tbody td {
		padding: 5px 8px;
		border-bottom: 1px dashed rgba(100, 116, 139, 0.14);
		color: var(--text-primary);
		vertical-align: middle;
	}

	.sev-col {
		width: 56px;
	}

	.time-col {
		width: 80px;
		color: var(--text-muted);
		font-family: 'JetBrains Mono', 'Consolas', monospace;
	}

	.act-col {
		width: 80px;
		color: var(--text-muted);
	}

	tbody tr.critical {
		background: rgba(248, 113, 113, 0.05);
	}

	tbody tr.warn {
		background: rgba(251, 191, 36, 0.04);
	}

	.sev {
		display: inline-flex;
		padding: 1px 7px;
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

	.stack {
		color: var(--text-secondary);
		font-weight: 700;
	}

	.link {
		background: none;
		border: none;
		color: #30d5c8;
		font-weight: 800;
		font-size: 11px;
		cursor: pointer;
		padding: 0;
	}

	.link:hover {
		text-decoration: underline;
	}

	.msg {
		color: var(--text-secondary);
	}

	.empty-row td {
		padding: 14px;
		text-align: center;
		color: var(--text-muted);
		font-style: italic;
	}
</style>
