<!--
  ContainerActions — 컨테이너 라이프사이클 컨트롤 버튼.

  현재 status 에 따라 valid action 만 enabled. 파괴적 동작(stop/restart/kill)
  은 ConfirmDialog 를 거친다. 성공 시 onActionDone(action) 호출 → 호출처가
  detail/metrics reload.
-->
<script lang="ts">
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import ConfirmDialog from './ConfirmDialog.svelte';

	type Action = 'start' | 'stop' | 'restart' | 'pause' | 'unpause' | 'kill';

	let {
		containerId,
		currentStatus,
		disabled = false,
		onActionDone = (_a: Action) => {},
		onError = (_msg: string) => {},
	}: {
		containerId: string;
		currentStatus: string;
		disabled?: boolean;
		onActionDone?: (action: Action) => void;
		onError?: (msg: string) => void;
	} = $props();

	const ACTION_META: Record<Action, { label: string; icon: string; destructive?: boolean; needsConfirm?: boolean; help?: string }> = {
		start:    { label: '시작',     icon: '▶' },
		stop:     { label: '중지',     icon: '■', destructive: true,  needsConfirm: true,  help: '컨테이너에 SIGTERM을 보내 정상 종료를 시도합니다.' },
		restart:  { label: '재시작',   icon: '↻', destructive: false, needsConfirm: true,  help: '컨테이너를 멈추고 다시 시작합니다. 진행 중인 작업이 끊깁니다.' },
		pause:    { label: '일시정지', icon: '❚❚' },
		unpause:  { label: '재개',     icon: '▶' },
		kill:     { label: '강제종료', icon: '✕', destructive: true,  needsConfirm: true,  help: 'SIGKILL로 즉시 종료합니다. 데이터 손실 가능.' },
	};

	function validActions(status: string): Set<Action> {
		const s = (status || '').toLowerCase();
		if (s === 'running')   return new Set<Action>(['stop', 'restart', 'pause', 'kill']);
		if (s === 'paused')    return new Set<Action>(['unpause', 'stop', 'restart', 'kill']);
		if (['stopped', 'exited', 'created', 'dead'].includes(s)) return new Set<Action>(['start']);
		return new Set<Action>(); // restarting → 모든 버튼 disabled
	}

	let allowed = $derived(validActions(currentStatus));
	let busyAction = $state<Action | null>(null);
	let pendingAction = $state<Action | null>(null);

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function callControl(action: Action) {
		const t = token();
		if (!t) {
			onError('로그인이 필요합니다.');
			return;
		}
		busyAction = action;
		try {
			const response = await fetch(`${base}/api/my-containers/${containerId}/control/`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${t}`,
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({ action }),
			});
			const json = await response.json().catch(() => ({}));
			if (!response.ok) {
				const msg = json?.error?.detail || json?.detail || `HTTP ${response.status}`;
				onError(`'${ACTION_META[action].label}' 실패: ${msg}`);
				return;
			}
			onActionDone(action);
		} catch (err: any) {
			onError(`'${ACTION_META[action].label}' 실패: ${err?.message || err}`);
		} finally {
			busyAction = null;
		}
	}

	function handleClick(action: Action) {
		if (disabled || busyAction || !allowed.has(action)) return;
		const meta = ACTION_META[action];
		if (meta.needsConfirm) {
			pendingAction = action;
			return;
		}
		callControl(action);
	}

	function confirmPending() {
		if (!pendingAction) return;
		const a = pendingAction;
		pendingAction = null;
		callControl(a);
	}

	function cancelPending() {
		pendingAction = null;
	}

	let confirmTitle = $derived(pendingAction ? `${ACTION_META[pendingAction].label}` : '');
	let confirmMessage = $derived(pendingAction ? (ACTION_META[pendingAction].help || `${ACTION_META[pendingAction].label} 하시겠습니까?`) : '');
	let confirmVariant = $derived<'primary' | 'danger'>(pendingAction && ACTION_META[pendingAction].destructive ? 'danger' : 'primary');
	const ACTION_ORDER: Action[] = ['start', 'unpause', 'pause', 'restart', 'stop', 'kill'];
</script>

<div class="actions" role="group" aria-label="컨테이너 컨트롤">
	{#each ACTION_ORDER as action}
		{@const meta = ACTION_META[action]}
		{@const isAllowed = allowed.has(action)}
		{@const isBusy = busyAction === action}
		<button
			type="button"
			class="btn"
			class:destructive={meta.destructive}
			disabled={disabled || !isAllowed || busyAction !== null}
			onclick={() => handleClick(action)}
			title={meta.help || meta.label}
		>
			<span class="icon">{meta.icon}</span>
			<span>{isBusy ? '처리 중...' : meta.label}</span>
		</button>
	{/each}
</div>

<ConfirmDialog
	open={pendingAction !== null}
	title={confirmTitle}
	message={confirmMessage}
	confirmLabel={pendingAction ? ACTION_META[pendingAction].label : ''}
	confirmVariant={confirmVariant}
	busy={busyAction !== null}
	onconfirm={confirmPending}
	oncancel={cancelPending}
/>

<style>
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 8px 14px;
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: inherit;
		font-size: 12px;
		font-weight: 700;
		cursor: pointer;
		transition: background 0.15s, border-color 0.15s, color 0.15s;
	}

	.btn:hover:not(:disabled) {
		background: rgba(48, 213, 200, 0.14);
		border-color: rgba(48, 213, 200, 0.4);
		color: var(--accent);
	}

	.btn.destructive:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.16);
		border-color: rgba(239, 68, 68, 0.4);
		color: #fca5a5;
	}

	.btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.icon {
		font-size: 11px;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}
</style>
