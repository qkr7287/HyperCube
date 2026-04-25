<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
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
		intervalMs = 5000,
		onSelect = (_container: any) => {},
	}: {
		events?: EventRow[];
		intervalMs?: number;
		onSelect?: (container: any) => void;
	} = $props();

	let activeIndex = $state(0);
	let hovered = $state(false);
	let timer: ReturnType<typeof setInterval> | null = null;
	let progress = $state(0);
	let progressTimer: ReturnType<typeof setInterval> | null = null;

	const sortedEvents = $derived.by(() =>
		[...events].sort((a, b) => {
			const weight = (sev: string) => (sev === 'critical' ? 0 : sev === 'warn' ? 1 : 2);
			return weight(a.severity) - weight(b.severity);
		}),
	);
	const counts = $derived.by(() => {
		const c = { critical: 0, warn: 0, info: 0 };
		for (const event of events) c[event.severity] += 1;
		return c;
	});
	const featured = $derived(sortedEvents[activeIndex] ?? null);

	function advance() {
		if (sortedEvents.length === 0) return;
		activeIndex = (activeIndex + 1) % sortedEvents.length;
		progress = 0;
	}

	function start() {
		stop();
		if (sortedEvents.length <= 1 || hovered) return;
		const tick = 80;
		const steps = Math.max(1, Math.floor(intervalMs / tick));
		progress = 0;
		progressTimer = setInterval(() => {
			progress = Math.min(100, progress + 100 / steps);
		}, tick);
		timer = setInterval(advance, intervalMs);
	}

	function stop() {
		if (timer) clearInterval(timer);
		if (progressTimer) clearInterval(progressTimer);
		timer = null;
		progressTimer = null;
	}

	$effect(() => {
		sortedEvents.length;
		hovered;
		intervalMs;
		if (activeIndex >= sortedEvents.length) activeIndex = 0;
		start();
		return stop;
	});

	onMount(start);
	onDestroy(stop);

	function handleClick() {
		if (featured?.container) onSelect(featured.container);
	}

	function severityLabel(sev: 'critical' | 'warn' | 'info'): string {
		if (sev === 'critical') return '경고';
		if (sev === 'warn') return '주의';
		return '정보';
	}

	function formatClock(date: Date): string {
		try {
			return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
		} catch {
			return '-';
		}
	}
</script>

<section
	class="ticker"
	class:hovered
	onmouseenter={() => (hovered = true)}
	onmouseleave={() => (hovered = false)}
>
	<div class="counts">
		<i class="live-dot" aria-hidden="true"></i>
		<span class="title">실시간 경고
			<InfoTooltip text={`서버에서 지금 주의가 필요한 항목을 좌→우로 자동 순환하며 표시합니다.\n\n• 빨강: 경고 (장애·재시작 루프·임계 초과)\n• 노랑: 주의 (일시정지·고부하)\n• 클릭 = 해당 컨테이너 상세\n• 마우스 올리면 순환 일시 정지`} placement="top-start" />
		</span>
		{#if counts.critical > 0}
			<span class="count critical">경고 {counts.critical}</span>
		{/if}
		{#if counts.warn > 0}
			<span class="count warn">주의 {counts.warn}</span>
		{/if}
		{#if counts.info > 0}
			<span class="count info">정보 {counts.info}</span>
		{/if}
	</div>

	{#if featured}
		<button
			type="button"
			class={`featured ${featured.severity}`}
			onclick={handleClick}
			disabled={!featured.container}
			title={`${featured.target} · ${featured.stack}`}
			aria-live="polite"
		>
			<span class={`sev-pill ${featured.severity}`}>{severityLabel(featured.severity)}</span>
			<span class="time">{formatClock(featured.at)}</span>
			<span class="stack">{featured.stack}</span>
			<span class="arrow" aria-hidden="true">›</span>
			<span class="target">{featured.target}</span>
			<span class="msg">{featured.message}</span>
			{#if featured.action}
				<span class="action">{featured.action}</span>
			{/if}
		</button>
		<div class="progress" aria-hidden="true">
			<i style={`width:${progress.toFixed(1)}%`}></i>
		</div>
		<div class="paginator">
			<button
				type="button"
				class="paginate"
				onclick={() => { activeIndex = (activeIndex - 1 + sortedEvents.length) % sortedEvents.length; progress = 0; }}
				disabled={sortedEvents.length <= 1}
				aria-label="이전 이벤트"
			>‹</button>
			<small>{activeIndex + 1} / {sortedEvents.length}</small>
			<button
				type="button"
				class="paginate"
				onclick={() => { advance(); }}
				disabled={sortedEvents.length <= 1}
				aria-label="다음 이벤트"
			>›</button>
		</div>
	{:else}
		<div class="empty">
			<span class="ok-dot"></span>
			<span>주의가 필요한 이벤트가 없습니다 · 서버 상태 양호</span>
		</div>
	{/if}
</section>

<style>
	.ticker {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 7px 14px;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: linear-gradient(90deg, rgba(15, 23, 42, 0.85), rgba(15, 23, 42, 0.65));
		min-height: 46px;
		position: relative;
		overflow: hidden;
	}

	.ticker.hovered {
		border-color: rgba(48, 213, 200, 0.3);
	}

	.counts {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		flex: 0 0 auto;
		padding-right: 12px;
		border-right: 1px solid rgba(100, 116, 139, 0.25);
	}

	.live-dot {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: #34d399;
		box-shadow: 0 0 10px rgba(52, 211, 153, 0.6);
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.55; transform: scale(0.85); }
		50% { opacity: 1; transform: scale(1.18); }
	}

	.title {
		display: inline-flex;
		align-items: center;
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 850;
		letter-spacing: 0.02em;
	}

	.count {
		display: inline-flex;
		align-items: center;
		padding: 2px 9px;
		border-radius: 999px;
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.02em;
	}

	.count.critical {
		background: rgba(248, 113, 113, 0.18);
		color: #f87171;
		border: 1px solid rgba(248, 113, 113, 0.4);
	}

	.count.warn {
		background: rgba(251, 191, 36, 0.18);
		color: #fbbf24;
		border: 1px solid rgba(251, 191, 36, 0.4);
	}

	.count.info {
		background: rgba(96, 165, 250, 0.18);
		color: #60a5fa;
		border: 1px solid rgba(96, 165, 250, 0.4);
	}

	.featured {
		flex: 1 1 auto;
		min-width: 0;
		display: grid;
		grid-template-columns: auto auto auto auto auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 8px;
		padding: 0 4px;
		border: none;
		background: transparent;
		color: var(--text-primary);
		font-size: 12px;
		text-align: left;
		cursor: pointer;
		overflow: hidden;
		animation: fade-in 320ms ease;
	}

	.featured:disabled {
		cursor: default;
	}

	@keyframes fade-in {
		from { opacity: 0; transform: translateX(8px); }
		to { opacity: 1; transform: translateX(0); }
	}

	.sev-pill {
		display: inline-flex;
		padding: 2px 9px;
		border-radius: 999px;
		font-size: 10px;
		font-weight: 800;
	}

	.sev-pill.critical {
		background: rgba(248, 113, 113, 0.22);
		color: #f87171;
	}

	.sev-pill.warn {
		background: rgba(251, 191, 36, 0.22);
		color: #fbbf24;
	}

	.sev-pill.info {
		background: rgba(96, 165, 250, 0.22);
		color: #60a5fa;
	}

	.time {
		color: var(--text-muted);
		font-family: 'JetBrains Mono', 'Consolas', monospace;
		font-size: 11px;
		font-weight: 800;
	}

	.stack {
		color: var(--text-secondary);
		font-size: 11px;
		font-weight: 700;
		max-width: 130px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.arrow {
		color: var(--text-muted);
		font-size: 14px;
		font-weight: 800;
		line-height: 1;
	}

	.target {
		color: #30d5c8;
		font-size: 12px;
		font-weight: 900;
		max-width: 220px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.msg {
		color: var(--text-secondary);
		font-size: 12px;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.action {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		padding: 2px 8px;
		border-radius: 999px;
		background: rgba(15, 23, 42, 0.7);
		border: 1px solid rgba(100, 116, 139, 0.3);
		flex: 0 0 auto;
	}

	.progress {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		height: 2px;
		background: rgba(30, 41, 59, 0.6);
		overflow: hidden;
	}

	.progress i {
		display: block;
		height: 100%;
		background: linear-gradient(90deg, #30d5c8, #60a5fa);
		transition: width 80ms linear;
	}

	.paginator {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		flex: 0 0 auto;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		padding-left: 12px;
		border-left: 1px solid rgba(100, 116, 139, 0.25);
	}

	.paginate {
		width: 22px;
		height: 22px;
		border-radius: 6px;
		border: 1px solid rgba(100, 116, 139, 0.3);
		background: rgba(15, 23, 42, 0.55);
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 900;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		line-height: 1;
	}

	.paginate:hover:not(:disabled) {
		border-color: rgba(48, 213, 200, 0.45);
	}

	.paginate:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.empty {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		flex: 1;
		color: var(--text-muted);
		font-size: 12px;
		font-weight: 700;
	}

	.ok-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #34d399;
		box-shadow: 0 0 10px rgba(52, 211, 153, 0.6);
	}
</style>
