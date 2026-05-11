<!--
  ConsoleModal — ConsolePanel 을 풀스크린 overlay 로 띄움. ops-bar 의 "콘솔"
  버튼에서 호출. modal 안에서 xterm 큰 영역 사용 + ESC / × 로 닫기.
-->
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import ConsolePanel from './ConsolePanel.svelte';

	let {
		open = false,
		agentId,
		containerId,
		onclose = () => {},
	}: {
		open?: boolean;
		agentId: string;
		containerId: string;
		onclose?: () => void;
	} = $props();

	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) onclose();
	}

	onMount(() => {
		if (typeof window !== 'undefined') window.addEventListener('keydown', onKey);
	});
	onDestroy(() => {
		if (typeof window !== 'undefined') window.removeEventListener('keydown', onKey);
	});
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="overlay" onclick={onclose}>
		<div class="modal" onclick={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h3>›_ 콘솔 (exec)</h3>
				<span class="hint">컨테이너 내부에 shell. ESC 또는 우측 × 로 닫기.</span>
				<button class="close" onclick={onclose} aria-label="닫기">×</button>
			</div>
			<div class="modal-body">
				<!-- ConsolePanel 의 startOpen 으로 즉시 세션 시작.
				     modal 이 열리는 순간 사용자가 console 의도를 명확히 한 것이므로
				     placeholder 클릭 한 번 더 요구하지 않는다. -->
				<ConsolePanel {agentId} {containerId} startOpen={true} />
			</div>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.7);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 9990;
		padding: clamp(16px, 2vw, 48px);
	}

	.modal {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-panel);
		width: 100%;
		max-width: 1280px;
		height: 100%;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 30px 80px rgba(0, 0, 0, 0.5);
		overflow: hidden;
	}

	.modal-header {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 10px 16px;
		border-bottom: 1px solid var(--border);
		background: rgba(13, 17, 23, 0.5);
	}
	.modal-header h3 {
		font-size: 14px;
		font-weight: 800;
		color: var(--text-primary);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}
	.hint {
		font-size: 11px;
		color: var(--text-muted);
	}
	.close {
		margin-left: auto;
		padding: 4px 10px;
		border-radius: 6px;
		background: transparent;
		border: 1px solid var(--border);
		color: var(--text-secondary);
		font-size: 16px;
		font-weight: 700;
		line-height: 1;
		cursor: pointer;
	}
	.close:hover {
		border-color: var(--accent);
		color: var(--accent);
	}

	.modal-body {
		flex: 1 1 0;
		min-height: 0;
		padding: 12px;
		display: flex;
		flex-direction: column;
	}
	/* ConsolePanel 의 .panel 자체 padding 은 그대로. modal-body 가 stretch 라
	   xterm termbox 가 큰 영역 차지. */
	.modal-body :global(.panel) {
		flex: 1 1 0;
		min-height: 0;
		display: flex;
		flex-direction: column;
		margin-top: 0;
	}
	.modal-body :global(.termbox) {
		flex: 1 1 0;
		min-height: 0;
		height: auto;
	}
</style>
