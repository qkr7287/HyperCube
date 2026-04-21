<script lang="ts">
	let {
		open = false,
		title = 'Confirm',
		message = '',
		confirmLabel = 'Confirm',
		confirmVariant = 'primary' as 'primary' | 'danger',
		onconfirm = () => {},
		oncancel = () => {},
	} = $props();
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="overlay" onclick={oncancel}>
		<div class="dialog" onclick={(e) => e.stopPropagation()}>
			<h3 class="dialog-title">{title}</h3>
			<p class="dialog-message">{message}</p>
			<div class="dialog-actions">
				<button class="btn btn-cancel" onclick={oncancel}>Cancel</button>
				<button
					class="btn btn-confirm {confirmVariant}"
					onclick={onconfirm}
				>
					{confirmLabel}
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
		border-radius: 12px;
		padding: 28px;
		width: 100%;
		max-width: 420px;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
	}

	.dialog-title {
		font-size: 17px;
		font-weight: 700;
		color: var(--text-primary);
		margin-bottom: 12px;
	}

	.dialog-message {
		font-size: 14px;
		color: var(--text-secondary);
		line-height: 1.5;
		margin-bottom: 24px;
	}

	.dialog-actions {
		display: flex;
		justify-content: flex-end;
		gap: 10px;
	}

	.btn {
		padding: 8px 20px;
		border-radius: 8px;
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
		border: 1px solid transparent;
		transition: all 0.15s;
	}

	.btn-cancel {
		background: transparent;
		border: 1px solid var(--border);
		color: var(--text-primary);
	}
	.btn-cancel:hover {
		border-color: var(--text-secondary);
	}

	.btn-confirm.primary {
		background: var(--accent);
		color: var(--bg-base);
	}
	.btn-confirm.primary:hover {
		opacity: 0.9;
	}

	.btn-confirm.danger {
		background: var(--error);
		color: #fff;
	}
	.btn-confirm.danger:hover {
		opacity: 0.9;
	}
</style>
