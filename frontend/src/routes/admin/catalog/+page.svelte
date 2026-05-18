<script lang="ts">
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import TemplatesPanel from '$lib/components/admin/TemplatesPanel.svelte';
	import ModelAssetsPanel from '$lib/components/admin/ModelAssetsPanel.svelte';
	import UploadModelWizard from '$lib/components/UploadModelWizard.svelte';

	type Tab = 'templates' | 'models';
	let tab = $state<Tab>('templates');
	let wizardOpen = $state(false);
	let lastRegistered = $state<string | null>(null);
	let reloadKey = $state(0);

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

<div class="bar">
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
	<button class="register" onclick={() => (wizardOpen = true)}>+ 모델 + 템플릿 등록</button>
</div>

{#if lastRegistered}
	<div class="success" role="status">
		<strong>{lastRegistered}</strong> 등록 완료. 사용자가 새 요청 모달에서 바로 선택할 수 있습니다.
		<button class="success-close" onclick={() => (lastRegistered = null)} aria-label="닫기">×</button>
	</div>
{/if}

{#key reloadKey}
	{#if tab === 'templates'}
		<TemplatesPanel />
	{:else}
		<ModelAssetsPanel />
	{/if}
{/key}

<UploadModelWizard
	open={wizardOpen}
	mode="admin"
	onClose={() => (wizardOpen = false)}
	onSubmitted={(result) => {
		lastRegistered = result.templateName ?? null;
		reloadKey++;
	}}
/>

<style>
	.bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 16px;
		padding: 16px 32px 0;
		border-bottom: 1px solid var(--border);
		background: var(--bg-base);
		position: sticky;
		top: 0;
		z-index: 10;
	}
	.tabs {
		display: flex;
		gap: 4px;
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
	.register {
		padding: 7px 14px;
		font: inherit;
		font-size: 12px;
		font-weight: 800;
		background: var(--accent);
		border: 1px solid transparent;
		color: var(--bg-base);
		border-radius: var(--radius-sm);
		cursor: pointer;
		margin-bottom: 6px;
	}
	.register:hover {
		filter: brightness(1.1);
	}
	.success {
		position: relative;
		margin: 12px 32px 0;
		background: rgba(77, 191, 179, 0.10);
		border: 1px solid rgba(77, 191, 179, 0.4);
		color: var(--text-primary);
		padding: 10px 36px 10px 14px;
		border-radius: var(--radius-sm);
		font-size: 13px;
	}
	.success-close {
		position: absolute;
		right: 8px;
		top: 50%;
		transform: translateY(-50%);
		width: 24px;
		height: 24px;
		padding: 0;
		background: transparent;
		border: none;
		color: var(--text-muted);
		font-size: 16px;
		cursor: pointer;
	}
</style>
