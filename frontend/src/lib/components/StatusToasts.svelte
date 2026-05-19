<script module lang="ts">
	// 한 번 toast 로 띄운 이벤트 키를 기록. module scope 라 page 이동으로
	// component 가 remount 돼도 dedup 이 유지된다 — 같은 agent_status_change
	// 이벤트가 두 번 toast 되는 일을 막음.
	const seenLocally = new Set<string>();
</script>

<script lang="ts">
	import { onDestroy } from 'svelte';
	import { statusEvents, type AgentStatusEvent } from '$lib/stores/global-events';

	const TOAST_TTL_MS = 8000;
	// 라이브 이벤트로 간주할 receivedAt 신선도 (epoch ms 기준).
	// 이보다 오래된 이벤트는 seed/historical 로 보고 toast 를 띄우지 않는다.
	// 페이지 이동마다 component remount → store 첫 emission 으로 과거 offline
	// 전환들이 다시 toast 로 뜨던 회귀를 막는다.
	const FRESH_WINDOW_MS = 5000;

	let nextLocalId = 1;
	type ToastView = AgentStatusEvent & { localId: number };
	let visible: ToastView[] = $state([]);

	let timers = new Map<number, ReturnType<typeof setTimeout>>();

	function eventKey(evt: AgentStatusEvent): string {
		return `${evt.server_id}:${evt.status}:${evt.receivedAt}`;
	}

	const unsub = statusEvents.subscribe((events) => {
		const now = Date.now();
		// 신선한 이벤트만 toast. 동일 이벤트 중복도 차단.
		for (const evt of events) {
			if (now - evt.receivedAt > FRESH_WINDOW_MS) continue;
			const key = eventKey(evt);
			if (seenLocally.has(key)) continue;
			seenLocally.add(key);
			addToast(evt);
		}
	});

	function addToast(evt: AgentStatusEvent) {
		const localId = nextLocalId++;
		const view: ToastView = { ...evt, localId };
		visible = [view, ...visible].slice(0, 5);
		const t = setTimeout(() => dismiss(localId), TOAST_TTL_MS);
		timers.set(localId, t);
	}

	function dismiss(localId: number) {
		visible = visible.filter((v) => v.localId !== localId);
		const t = timers.get(localId);
		if (t) {
			clearTimeout(t);
			timers.delete(localId);
		}
	}

	function formatDuration(secs: number | null | undefined): string {
		if (secs == null || secs < 0) return '';
		if (secs < 60) return `${secs}초`;
		if (secs < 3600) return `${Math.round(secs / 60)}분`;
		if (secs < 86400) {
			const h = Math.floor(secs / 3600);
			const m = Math.round((secs % 3600) / 60);
			return m > 0 ? `${h}시간 ${m}분` : `${h}시간`;
		}
		const d = Math.floor(secs / 86400);
		const h = Math.round((secs % 86400) / 3600);
		return h > 0 ? `${d}일 ${h}시간` : `${d}일`;
	}

	function formatTime(iso: string): string {
		try {
			const d = new Date(iso);
			return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
		} catch {
			return iso;
		}
	}

	onDestroy(() => {
		unsub();
		timers.forEach((t) => clearTimeout(t));
		timers.clear();
	});
</script>

<div class="toast-container">
	{#each visible as toast (toast.localId)}
		<div class="toast" class:offline={toast.status === 'offline'} class:online={toast.status === 'online'}>
			<div class="toast-header">
				<span class="toast-icon">{toast.status === 'online' ? '🟢' : '🔴'}</span>
				<span class="toast-title">
					{toast.hostname}
					{toast.status === 'online' ? '재연결' : '연결 끊김'}
				</span>
				<button class="toast-close" onclick={() => dismiss(toast.localId)} aria-label="Close">×</button>
			</div>
			<div class="toast-body">
				{#if toast.status === 'offline'}
					<div>마지막 데이터 {formatTime(toast.last_seen_at)}</div>
				{:else}
					<div>마지막 데이터 {formatTime(toast.last_seen_at)}</div>
					{#if toast.previous_offline_seconds}
						<div class="dim">{formatDuration(toast.previous_offline_seconds)} 만에 복귀</div>
					{/if}
				{/if}
			</div>
		</div>
	{/each}
</div>

<style>
	.toast-container {
		position: fixed;
		top: 20px;
		right: 20px;
		z-index: 1000;
		display: flex;
		flex-direction: column;
		gap: 10px;
		pointer-events: none;
	}
	.toast {
		min-width: 300px;
		max-width: 400px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-left-width: 4px;
		border-radius: var(--radius-md);
		padding: 12px 14px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
		pointer-events: auto;
		animation: slideIn 0.25s ease-out;
	}
	.toast.offline {
		border-left-color: var(--error);
	}
	.toast.online {
		border-left-color: var(--accent);
	}
	.toast-header {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 6px;
	}
	.toast-icon {
		font-size: 14px;
	}
	.toast-title {
		flex: 1;
		font-size: 13px;
		font-weight: 600;
		color: var(--text-primary);
	}
	.toast-close {
		background: none;
		border: none;
		color: var(--text-secondary);
		font-size: 18px;
		line-height: 1;
		cursor: pointer;
		padding: 0 4px;
	}
	.toast-close:hover {
		color: var(--text-primary);
	}
	.toast-body {
		font-size: 11px;
		color: var(--text-secondary);
		line-height: 1.5;
	}
	.toast-body .dim {
		color: var(--text-muted);
	}
	@keyframes slideIn {
		from {
			transform: translateX(20px);
			opacity: 0;
		}
		to {
			transform: translateX(0);
			opacity: 1;
		}
	}
</style>
