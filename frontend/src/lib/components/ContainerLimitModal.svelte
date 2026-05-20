<!--
  ContainerLimitModal — 컨테이너 자원 한도 / 재시작 정책 수정.

  Portainer container settings parity. agent 의 dockerode container.update()
  는 재시작 없이 즉시 적용 (memory/cpuQuota/restartPolicy).

  prefill: 현재 inspect 데이터에서 memory limit / cpu quota / restart policy
  가져옴 (props). 변경된 필드만 patch (server-side 가 partial 처리).
-->
<script lang="ts">
	import { browser } from '$app/environment';
	import { base } from '$app/paths';

	type RestartPolicy = 'no' | 'on-failure' | 'unless-stopped' | 'always';

	let {
		open = false,
		containerId,
		inspectData = null as any,
		onclose = () => {},
		onsaved = () => {},
	}: {
		open?: boolean;
		containerId: string;
		inspectData?: any;
		onclose?: () => void;
		onsaved?: () => void;
	} = $props();

	// prefill — inspect 데이터의 hostConfig 영역에서 가져옴
	let memoryMb = $state<number | ''>('');
	let cpuPercent = $state<number | ''>('');
	let restartPolicy = $state<RestartPolicy>('no');
	let restartMaxRetry = $state<number | ''>('');

	let busy = $state(false);
	let errorMsg = $state('');

	$effect(() => {
		// inspect 또는 open 변화 시 prefill
		if (!open || !inspectData) return;
		const hc = inspectData?.hostConfig || inspectData?.HostConfig || {};
		const memBytes: number = hc.Memory ?? hc.memory ?? 0;
		const cpuQuota: number = hc.CpuQuota ?? hc.cpuQuota ?? 0;
		const cpuPeriod: number = hc.CpuPeriod ?? hc.cpuPeriod ?? 100000;
		memoryMb = memBytes > 0 ? Math.round(memBytes / (1024 * 1024)) : 0;
		cpuPercent = cpuQuota > 0 && cpuPeriod > 0 ? Math.round((cpuQuota / cpuPeriod) * 100) : 0;
		const rp = (hc.RestartPolicy?.Name || hc.restartPolicy?.name || 'no') as RestartPolicy;
		restartPolicy = ['no', 'on-failure', 'unless-stopped', 'always'].includes(rp) ? rp : 'no';
		restartMaxRetry = hc.RestartPolicy?.MaximumRetryCount ?? 0;
		errorMsg = '';
	});

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function save() {
		const t = token();
		if (!t) {
			errorMsg = '로그인이 필요합니다.';
			return;
		}
		// CPU·메모리는 한도 필수 — 0(무제한) 은 허용 안 함. 빈 값은 변경하지 않음.
		if (memoryMb !== '' && Number(memoryMb) < 1) {
			errorMsg = '메모리 한도는 1MB 이상이어야 합니다 (무제한 불가).';
			return;
		}
		if (cpuPercent !== '' && Number(cpuPercent) < 1) {
			errorMsg = 'CPU 한도는 1% 이상이어야 합니다 (무제한 불가).';
			return;
		}
		const body: Record<string, any> = {};
		if (memoryMb !== '') body.memory_mb = Number(memoryMb);
		if (cpuPercent !== '') body.cpu_percent = Number(cpuPercent);
		body.restart_policy = restartPolicy;
		if (restartPolicy === 'on-failure' && restartMaxRetry !== '') {
			body.restart_max_retry = Number(restartMaxRetry);
		}
		busy = true;
		errorMsg = '';
		try {
			const res = await fetch(`${base}/api/my-containers/${containerId}/update-limits/`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${t}`,
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(body),
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) {
				const msg = json?.error?.detail || json?.detail || `HTTP ${res.status}`;
				errorMsg = msg;
				return;
			}
			onsaved();
			onclose();
		} catch (e: any) {
			errorMsg = e?.message || String(e);
		} finally {
			busy = false;
		}
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="overlay" onclick={onclose}>
		<div class="dialog" onclick={(e) => e.stopPropagation()}>
			<h3>컨테이너 한도 수정</h3>
			<p class="hint">
				dockerode <code>container.update()</code> — 재시작 없이 즉시 적용. 빈 값은 변경하지
				않음. CPU·메모리는 한도 필수 (무제한 불가).
			</p>

			<div class="field">
				<label for="mem">메모리 한도 (MB)</label>
				<input id="mem" type="number" min="1" bind:value={memoryMb} placeholder="1 이상" disabled={busy} />
			</div>

			<div class="field">
				<label for="cpu">CPU 할당 (%, 100 = 1 core)</label>
				<input id="cpu" type="number" min="1" max="10000" bind:value={cpuPercent} placeholder="1 이상" disabled={busy} />
			</div>

			<div class="field">
				<label for="rp">재시작 정책</label>
				<select id="rp" bind:value={restartPolicy} disabled={busy}>
					<option value="no">no — 재시작 안 함</option>
					<option value="on-failure">on-failure — 비정상 종료 시</option>
					<option value="unless-stopped">unless-stopped — 사용자 중지 외 항상</option>
					<option value="always">always — 항상</option>
				</select>
			</div>

			{#if restartPolicy === 'on-failure'}
				<div class="field">
					<label for="mr">최대 재시도 횟수 (0 = 무제한)</label>
					<input id="mr" type="number" min="0" bind:value={restartMaxRetry} disabled={busy} />
				</div>
			{/if}

			{#if errorMsg}
				<div class="error">{errorMsg}</div>
			{/if}

			<div class="actions">
				<button class="btn cancel" onclick={onclose} disabled={busy}>취소</button>
				<button class="btn save" onclick={save} disabled={busy}>
					{busy ? '저장 중...' : '저장'}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 9999;
	}

	.dialog {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-panel);
		padding: 24px 26px;
		width: 100%;
		max-width: 460px;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
	}

	h3 {
		font-size: 16px;
		font-weight: 800;
		color: var(--text-primary);
		margin-bottom: 6px;
	}
	.hint {
		font-size: 12px;
		color: var(--text-muted);
		line-height: 1.45;
		margin-bottom: 18px;
	}
	.hint code {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 11px;
		color: var(--text-secondary);
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 5px;
		margin-bottom: 14px;
	}
	.field label {
		font-size: 11px;
		font-weight: 700;
		color: var(--text-secondary);
		letter-spacing: 0.02em;
	}
	.field input,
	.field select {
		padding: 7px 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: inherit;
		font-size: 13px;
	}
	.field input:focus-visible,
	.field select:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.error {
		padding: 8px 12px;
		border-radius: 8px;
		background: var(--state-error-bg);
		border: 1px solid var(--state-error-border);
		color: var(--state-error-text);
		font-size: 12px;
		font-weight: 700;
		margin-bottom: 14px;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		margin-top: 6px;
	}
	.btn {
		padding: 7px 16px;
		border-radius: 8px;
		font-size: 13px;
		font-weight: 700;
		cursor: pointer;
		border: 1px solid transparent;
		font-family: inherit;
		transition: background-color var(--ease-fast), border-color var(--ease-fast);
	}
	.btn.cancel {
		background: transparent;
		border-color: var(--border);
		color: var(--text-primary);
	}
	.btn.cancel:hover:not(:disabled) {
		border-color: var(--text-secondary);
	}
	.btn.save {
		background: var(--accent);
		color: var(--bg-base);
	}
	.btn.save:hover:not(:disabled) {
		opacity: 0.9;
	}
	.btn:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}
</style>
