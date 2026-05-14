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
		agentOnline = true,
		onActionDone = (_a: Action) => {},
		onError = (_msg: string) => {},
	}: {
		containerId: string;
		currentStatus: string;
		disabled?: boolean;
		agentOnline?: boolean;
		onActionDone?: (action: Action) => void;
		onError?: (msg: string) => void;
	} = $props();

	const ACTION_META: Record<Action, { label: string; icon: string; destructive?: boolean; needsConfirm?: boolean; help?: string }> = {
		start:    { label: '시작',     icon: '▶' },
		stop:     { label: '중지',     icon: '■', destructive: true,  needsConfirm: true,  help: '컨테이너에 SIGTERM을 보내 정상 종료를 시도합니다.' },
		restart:  { label: '재시작',   icon: '↻', destructive: false, needsConfirm: true,  help: '컨테이너를 멈추고 다시 시작합니다. 진행 중인 작업이 끊깁니다.' },
		pause:    { label: '일시정지', icon: '⏸' },
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
	let dangerExpanded = $state(false);

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
		if (meta.destructive) dangerExpanded = false;
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

	// 의도별 그룹: 실행(neutral) / 재시작(warn) / 종료(danger). 같은 위험도끼리 묶어
	// 색으로 즉시 인지 가능. 그룹 안 actions 는 현재 상태에 따라 자동 valid/invalid.
	const RUN_ACTIONS: Action[] = ['start', 'unpause', 'pause'];
	const RESTART_ACTIONS: Action[] = ['restart'];
	const KILL_ACTIONS: Action[] = ['stop', 'kill'];
	let visibleRunActions = $derived(RUN_ACTIONS.filter((action) => allowed.has(action)));
	let visibleRestartActions = $derived(RESTART_ACTIONS.filter((action) => allowed.has(action)));
	let visibleKillActions = $derived(KILL_ACTIONS.filter((action) => allowed.has(action)));
	let hasDangerAction = $derived(KILL_ACTIONS.some((action) => allowed.has(action)));

	$effect(() => {
		if (!hasDangerAction) dangerExpanded = false;
	});
</script>

<div class="actions" role="group" aria-label="컨테이너 컨트롤">
	{#if visibleRunActions.length > 0}
	<div class="group run">
		{#each visibleRunActions as action}
			{@const meta = ACTION_META[action]}
			{@const isBusy = busyAction === action}
			<button
				type="button"
				class="btn run"
				disabled={disabled || busyAction !== null || !agentOnline}
				onclick={() => handleClick(action)}
				title={!agentOnline ? 'Agent 오프라인 — 명령 발송 불가' : (meta.help || meta.label)}
			>
				<span class="icon">{meta.icon}</span>
				<span>{isBusy ? '처리 중...' : meta.label}</span>
			</button>
		{/each}
	</div>
	{/if}
	{#if visibleRestartActions.length > 0}
	<div class="group restart">
		{#each visibleRestartActions as action}
			{@const meta = ACTION_META[action]}
			{@const isBusy = busyAction === action}
			<button
				type="button"
				class="btn warn"
				disabled={disabled || busyAction !== null || !agentOnline}
				onclick={() => handleClick(action)}
				title={!agentOnline ? 'Agent 오프라인 — 명령 발송 불가' : (meta.help || meta.label)}
			>
				<span class="icon">{meta.icon}</span>
				<span>{isBusy ? '처리 중...' : meta.label}</span>
			</button>
		{/each}
	</div>
	{/if}
	{#if hasDangerAction}
	<div class="group kill" class:expanded={dangerExpanded}>
		<button
			type="button"
			class="btn danger-toggle"
			class:open={dangerExpanded}
			aria-expanded={dangerExpanded}
			disabled={disabled || busyAction !== null || !agentOnline || !hasDangerAction}
			onclick={() => (dangerExpanded = !dangerExpanded)}
			title={!agentOnline ? 'Agent 오프라인 - 명령을 보낼 수 없습니다' : '중지와 강제종료 옵션을 펼칩니다'}
		>
			<span class="icon">{dangerExpanded ? '▴' : '▾'}</span>
			<span>종료 옵션</span>
		</button>
		{#if dangerExpanded}
		{#each visibleKillActions as action}
			{@const meta = ACTION_META[action]}
			{@const isBusy = busyAction === action}
			<button
				type="button"
				class="btn danger"
				disabled={disabled || busyAction !== null || !agentOnline}
				onclick={() => handleClick(action)}
				title={!agentOnline ? 'Agent 오프라인 — 명령 발송 불가' : (meta.help || meta.label)}
			>
				<span class="icon">{meta.icon}</span>
				<span>{isBusy ? '처리 중...' : meta.label}</span>
			</button>
		{/each}
		{/if}
	</div>
	{/if}
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
	/* actions = 2-row layout:
	   row 1 (positive): run group (시작/재개/일시정지) + restart group (재시작)
	   row 2 (destructive): kill group (중지/강제종료)
	   각 그룹 색 stripe 로 위험도 시각적 분리 + ops-bar 가 stat orb 와 비례 잡힘. */
	.actions {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(82px, 1fr));
		align-items: stretch;
		gap: 4px;
		width: 100%;
		min-width: 0;
	}
	.group {
		display: inline-flex;
		align-items: center;
		gap: 2px;
		padding: 3px 3px 3px 7px;
		border-radius: 8px;
		position: relative;
		width: 100%;
		min-width: 0;
	}
	.group::before {
		content: '';
		position: absolute;
		left: 3px;
		top: 5px;
		bottom: 5px;
		width: 2px;
		border-radius: 2px;
	}
	/* kill 그룹은 row 2 풀폭. wrap break 강제. */
	.group.kill {
		flex-basis: auto;
		max-width: 100%;
	}
	.group.kill.expanded {
		grid-column: 1 / -1;
		flex-basis: 100%;
		flex-wrap: wrap;
	}
	.group.run {
		background: rgba(13, 17, 23, 0.46);
		border: 1px solid rgba(100, 116, 139, 0.18);
	}
	.group.run::before {
		background: rgba(156, 163, 175, 0.5);
	}
	.group.restart {
		background: rgba(251, 191, 36, 0.08);
		border: 1px solid rgba(251, 191, 36, 0.3);
	}
	.group.restart::before {
		background: rgba(251, 191, 36, 0.6);
	}
	.group.kill {
		background: rgba(239, 68, 68, 0.08);
		border: 1px solid rgba(239, 68, 68, 0.3);
	}
	.group.kill::before {
		background: rgba(239, 68, 68, 0.65);
	}

	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 4px;
		width: 100%;
		min-height: 40px;
		padding: 0 10px;
		border-radius: 8px;
		background: rgba(2, 6, 12, 0.22);
		border: 1px solid rgba(100, 116, 139, 0.1);
		color: var(--text-secondary);
		font-family: inherit;
		font-size: 12px;
		font-weight: 800;
		cursor: pointer;
		white-space: nowrap;
		transition: background 0.15s, border-color 0.15s, color 0.15s;
	}

	/* run (neutral) — 가벼운 hover, accent 톤 */
	.btn.run:hover:not(:disabled) {
		background: rgba(48, 213, 200, 0.16);
		border-color: rgba(48, 213, 200, 0.4);
		color: var(--accent);
	}
	/* warn — 노란 hover */
	.btn.warn:hover:not(:disabled) {
		background: rgba(251, 191, 36, 0.18);
		border-color: rgba(251, 191, 36, 0.5);
		color: #fde68a;
	}
	/* danger — 빨간 hover */
	.btn.danger:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.18);
		border-color: rgba(239, 68, 68, 0.5);
		color: #fca5a5;
	}
	.btn.danger-toggle {
		color: #fca5a5;
		border-color: rgba(239, 68, 68, 0.22);
	}
	.btn.danger-toggle.open {
		background: rgba(239, 68, 68, 0.16);
		border-color: rgba(239, 68, 68, 0.42);
	}

	.btn:disabled {
		opacity: 0.32;
		cursor: not-allowed;
		background: transparent;
		border-color: transparent;
	}

	.icon {
		font-size: 12px;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		opacity: 0.9;
	}
</style>
