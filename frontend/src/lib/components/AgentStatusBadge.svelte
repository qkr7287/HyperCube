<script lang="ts">
	import { onDestroy } from 'svelte';
	import { activeAgentIds, statusEvents, type AgentStatusEvent } from '$lib/stores/global-events';

	let {
		totalKnown = 0,
	}: {
		totalKnown: number; // DB에 등록된 (archived 제외) 총 Agent 수
	} = $props();

	let active = $state(0);
	let recent: AgentStatusEvent[] = $state([]);
	let panelOpen = $state(false);

	const unsub1 = activeAgentIds.subscribe((set) => {
		active = set.size;
	});
	const unsub2 = statusEvents.subscribe((list) => {
		recent = list.slice(0, 8);
	});

	onDestroy(() => {
		unsub1();
		unsub2();
	});

	let offline = $derived(Math.max(0, totalKnown - active));

	function togglePanel(e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		panelOpen = !panelOpen;
	}

	function closePanel() {
		panelOpen = false;
	}

	function formatTime(iso: string): string {
		try {
			const d = new Date(iso);
			return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
		} catch {
			return iso;
		}
	}

	function relativeAge(receivedAt: number): string {
		const sec = Math.floor((Date.now() - receivedAt) / 1000);
		if (sec < 60) return `${sec}초 전`;
		if (sec < 3600) return `${Math.floor(sec / 60)}분 전`;
		if (sec < 86400) return `${Math.floor(sec / 3600)}시간 전`;
		return `${Math.floor(sec / 86400)}일 전`;
	}
</script>

<div class="status-badge-wrap">
	<button class="status-badge" class:has-offline={offline > 0} onclick={togglePanel} title="Agent 상태">
		<span class="dot" class:online={offline === 0 && active > 0} class:warn={offline > 0}></span>
		<span class="count">{active} / {totalKnown}</span>
		{#if offline > 0}
			<span class="offline-text">{offline} offline</span>
		{/if}
	</button>

	{#if panelOpen}
		<div class="status-panel">
			<div class="panel-head">
				<div class="panel-title">최근 상태 변화</div>
				<button class="panel-close" onclick={closePanel} aria-label="닫기">✕</button>
			</div>
			{#if recent.length === 0}
				<div class="empty">아직 이벤트가 없습니다.</div>
			{:else}
				<div class="event-list">
					{#each recent as evt (evt.server_id + '-' + evt.receivedAt)}
						<div class="event-row" class:offline={evt.status === 'offline'}>
							<span class="evt-icon">{evt.status === 'online' ? '🟢' : '🔴'}</span>
							<div class="evt-body">
								<div class="evt-line1">
									<span class="evt-host">{evt.hostname}</span>
									<span class="evt-status">{evt.status === 'online' ? '재연결' : '연결 끊김'}</span>
								</div>
								<div class="evt-line2">
									{relativeAge(evt.receivedAt)} · 마지막 데이터 {formatTime(evt.last_seen_at)}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.status-badge-wrap {
		position: relative;
	}
	.status-badge {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		color: var(--text-primary);
		padding: 4px 10px;
		border-radius: var(--radius-full);
		font-size: 12px;
		font-family: inherit;
		cursor: pointer;
		transition: border-color 0.15s, background 0.15s;
	}
	.status-badge:hover {
		border-color: var(--accent);
	}
	.status-badge.has-offline {
		border-color: var(--error);
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--text-muted);
	}
	.dot.online {
		background: var(--accent);
		box-shadow: 0 0 6px rgba(48, 213, 200, 0.6);
	}
	.dot.warn {
		background: var(--error);
		box-shadow: 0 0 6px rgba(239, 68, 68, 0.6);
	}
	.count {
		font-weight: 600;
	}
	.offline-text {
		color: var(--error);
		font-size: 11px;
	}
	.status-panel {
		position: absolute;
		top: calc(100% + 6px);
		right: 0;
		min-width: 320px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		box-shadow: 0 12px 28px rgba(0, 0, 0, 0.5);
		padding: 12px;
		/* 대시보드 다른 요소에 가려지지 않도록 확실히 위로. */
		z-index: 9999;
	}
	.panel-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;
	}
	.panel-title {
		font-size: 12px;
		font-weight: 700;
		color: var(--text-secondary);
	}
	.panel-close {
		width: 20px;
		height: 20px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: 0;
		background: transparent;
		color: var(--text-muted);
		cursor: pointer;
		font-size: 13px;
		border-radius: 4px;
	}
	.panel-close:hover {
		background: var(--bg-tab);
		color: var(--text-primary);
	}
	.empty {
		font-size: 12px;
		color: var(--text-muted);
		text-align: center;
		padding: 16px 0;
	}
	.event-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
		max-height: 320px;
		overflow-y: auto;
	}
	.event-row {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		padding: 8px;
		border-radius: var(--radius-sm);
		background: var(--bg-tab);
	}
	.evt-icon {
		font-size: 14px;
		flex-shrink: 0;
	}
	.evt-body {
		flex: 1;
		min-width: 0;
	}
	.evt-line1 {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-primary);
	}
	.evt-status {
		color: var(--text-secondary);
		font-weight: 400;
		font-size: 11px;
	}
	.event-row.offline .evt-status {
		color: var(--error);
	}
	.evt-line2 {
		font-size: 10px;
		color: var(--text-muted);
		margin-top: 2px;
	}
</style>
