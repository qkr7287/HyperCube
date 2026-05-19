<script lang="ts">
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import TemplatesPanel from '$lib/components/admin/TemplatesPanel.svelte';
	import ModelAssetsPanel from '$lib/components/admin/ModelAssetsPanel.svelte';

	type Tab = 'templates' | 'models';
	let tab = $state<Tab>('templates');

	$effect(() => {
		if (!browser) return;
		const t = $page.url.searchParams.get('tab');
		if (t === 'models' || t === 'templates') tab = t;
	});

	function setTab(next: Tab) {
		if (tab === next) return;
		tab = next;
		if (!browser) return;
		const url = new URL(window.location.href);
		url.searchParams.set('tab', next);
		goto(url.pathname + url.search, { replaceState: true, noScroll: true, keepFocus: true });
	}
</script>

<div class="tabs" role="tablist">
	<button
		role="tab"
		aria-selected={tab === 'templates'}
		class:active={tab === 'templates'}
		onclick={() => setTab('templates')}
	>
		컨테이너 템플릿
	</button>
	<button
		role="tab"
		aria-selected={tab === 'models'}
		class:active={tab === 'models'}
		onclick={() => setTab('models')}
	>
		모델 자산
	</button>
</div>

{#if tab === 'templates'}
	<TemplatesPanel />
{:else}
	<ModelAssetsPanel />
{/if}

<style>
	.tabs {
		display: flex;
		gap: 4px;
		padding: 16px 32px 0;
		border-bottom: 1px solid var(--border);
		background: var(--bg-base);
		position: sticky;
		top: 0;
		z-index: 10;
	}
	.tabs button {
		padding: 10px 16px;
		font: inherit;
		font-size: 13px;
		font-weight: 800;
		color: var(--text-secondary);
		background: transparent;
		border: none;
		border-bottom: 2px solid transparent;
		cursor: pointer;
		margin-bottom: -1px;
	}
	.tabs button:hover {
		color: var(--text-primary);
	}
	.tabs button.active {
		color: var(--accent);
		border-bottom-color: var(--accent);
	}
</style>
