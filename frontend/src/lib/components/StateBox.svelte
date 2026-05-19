<!--
  StateBox — 페이지·패널 안에서 loading / empty / error 표현을 통일.

  사용 예시:
    <StateBox kind="loading" message="불러오는 중..." />
    <StateBox kind="empty"   message="표시할 이벤트가 없습니다." icon="📭" />
    <StateBox kind="error"   message={errorMsg} action={retry} actionLabel="다시 시도" />

  variant:
    - compact=true: padding 축소 (panel 안에서 쓸 때).
    - inline=true: text 만 (배경/테두리 제거, panel 의 inline 안내용).
-->
<script lang="ts">
	type Kind = 'loading' | 'empty' | 'error';

	let {
		kind = 'empty' as Kind,
		message = '',
		icon = '',
		action = null as null | (() => void),
		actionLabel = '',
		compact = false,
		inline = false,
	}: {
		kind?: Kind;
		message?: string;
		icon?: string;
		action?: null | (() => void);
		actionLabel?: string;
		compact?: boolean;
		inline?: boolean;
	} = $props();
</script>

<div
	class="state-box"
	class:loading={kind === 'loading'}
	class:error={kind === 'error'}
	class:compact
	class:inline
	role={kind === 'error' ? 'alert' : 'status'}
>
	{#if kind === 'loading'}
		<span class="spinner" aria-hidden="true"></span>
	{:else if icon}
		<span class="icon" aria-hidden="true">{icon}</span>
	{/if}
	<span class="msg">{message}</span>
	{#if action && actionLabel}
		<button type="button" class="action" onclick={action}>{actionLabel}</button>
	{/if}
</div>

<style>
	.state-box {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: center;
		gap: 8px;
		padding: clamp(14px, 1vw, 18px) clamp(16px, 1.2vw, 22px);
		min-height: 56px;
		border-radius: var(--radius-md);
		background: var(--state-box-bg);
		border: 1px solid var(--state-box-border);
		color: var(--text-secondary);
		font-size: 13px;
		font-weight: 600;
		text-align: center;
	}

	.state-box.compact {
		padding: clamp(8px, 0.6vw, 12px) clamp(10px, 0.8vw, 14px);
		min-height: 0;
		font-size: 12px;
	}

	.state-box.inline {
		background: transparent;
		border: none;
		padding: 0;
		min-height: 0;
		color: var(--text-muted);
		font-style: italic;
		font-weight: 500;
		font-size: 12px;
	}

	.state-box.error {
		background: var(--state-error-bg);
		border-color: var(--state-error-border);
		color: var(--state-error-text);
		font-weight: 700;
	}

	.icon {
		font-size: 18px;
		line-height: 1;
		opacity: 0.85;
	}

	.spinner {
		width: 14px;
		height: 14px;
		border: 2px solid rgba(48, 213, 200, 0.25);
		border-top-color: var(--state-loading-spinner);
		border-radius: 50%;
		animation: state-box-spin 0.7s linear infinite;
	}

	.msg {
		white-space: pre-line;
	}

	.action {
		margin-left: 4px;
		padding: 5px 12px;
		border-radius: var(--radius-sm);
		background: rgba(48, 213, 200, 0.16);
		border: 1px solid rgba(48, 213, 200, 0.38);
		color: var(--accent);
		font: inherit;
		font-size: 12px;
		font-weight: 800;
		cursor: pointer;
		transition: background-color var(--ease-fast), border-color var(--ease-fast);
	}

	.action:hover {
		background: rgba(48, 213, 200, 0.26);
		border-color: rgba(48, 213, 200, 0.55);
	}

	.action:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	@keyframes state-box-spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
