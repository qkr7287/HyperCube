<script lang="ts">
	import { onDestroy } from 'svelte';
	import { statusEvents, type AgentStatusEvent } from '$lib/stores/global-events';

	const TOAST_TTL_MS = 8000;

	type ToastView = AgentStatusEvent & { dismissAt: number };
	let visible: ToastView[] = $state([]);

	let lastEventCount = 0;
	let timers = new Map<string, ReturnType<typeof setTimeout>>();

	const unsub = statusEvents.subscribe((events) => {
		// 새로 추가된 이벤트만 toast로 띄움 (page mount 시 이전 history는 무시)
		if (events.length > lastEventCount) {
			const fresh = events.slice(0, events.length - lastEventCount);
			fresh.forEach((evt) => addToast(evt));
		}
		lastEventCount = events.length;
	});

	function addToast(evt: AgentStatusEvent) {
		const key = `${evt.server_id}-${evt.receivedAt}`;
		const view: ToastView = { ...evt, dismissAt: evt.receivedAt + TOAST_TTL_MS };
		visible = [view, ...visible].slice(0, 5);
		const t = setTimeout(() => dismiss(key), TOAST_TTL_MS);
		timers.set(key, t);
	}

	function dismiss(key: string) {
		const [server_id, receivedAtStr] = key.split('-');
		const receivedAt = Number(receivedAtStr);
		visible = visible.filter((v) => !(v.server_id === server_id && v.receivedAt === receivedAt));
		const t = timers.get(key);
		if (t) {
			clearTimeout(t);
			timers.delete(key);
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
	{#each visible as toast (toast.server_id + '-' + toast.receivedAt)}
		<div class="toast" class:offline={toast.status === 'offline'} class:online={toast.status === 'online'}>
			<div class="toast-header">
				<span class="toast-icon">{toast.status === 'online' ? '🟢' : '🔴'}</span>
				<span class="toast-title">
					{toast.hostname}
					{toast.status === 'online' ? '재연결' : '연결 끊김'}
				</span>
				<button class="toast-close" onclick={() => dismiss(toast.server_id + '-' + toast.receivedAt)} aria-label="Close">×</button>
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
