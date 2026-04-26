<script lang="ts">
	import type { Server2dSortDir } from '$lib/stores/server2d-view.svelte';

	let {
		value = 'desc' as Server2dSortDir,
		onChange = (_next: Server2dSortDir) => {},
	}: {
		value?: Server2dSortDir;
		onChange?: (next: Server2dSortDir) => void;
	} = $props();

	function set(next: Server2dSortDir) {
		if (next !== value) onChange(next);
	}
</script>

<div class="dir-toggle" role="group" aria-label="정렬 방향">
	<button
		type="button"
		class="seg"
		class:active={value === 'desc'}
		title="내림차순 (큰 값이 위)"
		aria-label="내림차순 정렬"
		onclick={() => set('desc')}
	>
		<svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true">
			<path d="M3 6h18v2H3zM6 11h12v2H6zM9 16h6v2H9z"/>
		</svg>
		<span>내림</span>
	</button>
	<button
		type="button"
		class="seg"
		class:active={value === 'asc'}
		title="오름차순 (작은 값이 위)"
		aria-label="오름차순 정렬"
		onclick={() => set('asc')}
	>
		<svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true">
			<path d="M9 6h6v2H9zM6 11h12v2H6zM3 16h18v2H3z"/>
		</svg>
		<span>오름</span>
	</button>
</div>

<style>
	.dir-toggle {
		display: inline-flex;
		align-items: center;
		gap: 0;
		border: 1px solid rgba(100, 116, 139, 0.32);
		border-radius: 999px;
		padding: 2px;
		background: rgba(15, 23, 42, 0.7);
		flex: 0 0 auto;
	}

	.seg {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 3px;
		height: 22px;
		padding: 0 9px;
		border: none;
		border-radius: 999px;
		background: transparent;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.02em;
		cursor: pointer;
		white-space: nowrap;
		transition: background-color 0.14s ease, color 0.14s ease;
	}

	.seg:hover:not(.active) {
		color: var(--text-secondary);
	}

	.seg.active {
		background: rgba(48, 213, 200, 0.22);
		color: #30d5c8;
		box-shadow: inset 0 0 0 1px rgba(48, 213, 200, 0.4);
	}

	.seg svg {
		flex: 0 0 auto;
	}
</style>
