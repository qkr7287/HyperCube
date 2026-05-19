<!--
  TabbedContextPanel — 프로세스/런타임/설정/이벤트/Inspect 등 컨테이너 상세 보조 정보를
  하나의 카드에 탭으로 통합한다.

  의도적으로 generic 한 shell. 각 탭 본문은 부모 페이지에서 svelte 5 snippet 으로
  주입하므로 이 컴포넌트는 탭 전환/뱃지/스타일만 책임진다.

  사용 예시:
    {#snippet processTab()}<ProcessTopPanel ... />{/snippet}
    <TabbedContextPanel tabs={[
      { key: 'process', label: '프로세스', content: processTab, badge: ... },
      ...
    ]} />

  비활성 탭은 mount 자체가 되지 않아 (each → if 만 render) polling/리소스 절약.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';

	export type Tab = {
		key: string;
		label: string;
		content: Snippet;
		badge?: string | number | null;
		title?: string;
	};

	let {
		tabs,
		defaultTab,
	}: {
		tabs: Tab[];
		defaultTab?: string;
	} = $props();

	let active = $state<string>(defaultTab ?? tabs[0]?.key ?? '');

	// tabs 가 바뀌어 active key 가 사라지면 첫 번째로 fallback.
	$effect(() => {
		if (!tabs.find((t) => t.key === active)) {
			active = tabs[0]?.key ?? '';
		}
	});

	function activate(key: string) {
		active = key;
	}
</script>

<section class="panel">
	<div class="tab-bar" role="tablist">
		{#each tabs as tab (tab.key)}
			<button
				type="button"
				role="tab"
				class="tab-btn"
				class:active={active === tab.key}
				aria-selected={active === tab.key}
				aria-controls={`tab-panel-${tab.key}`}
				title={tab.title ?? tab.label}
				onclick={() => activate(tab.key)}
			>
				<span class="tab-label">{tab.label}</span>
				{#if tab.badge != null && String(tab.badge) !== ''}
					<span class="tab-badge">{tab.badge}</span>
				{/if}
			</button>
		{/each}
	</div>

	<div class="tab-body">
		{#each tabs as tab (tab.key)}
			{#if active === tab.key}
				<div
					id={`tab-panel-${tab.key}`}
					role="tabpanel"
					class="tab-panel"
					aria-label={tab.label}
				>
					{@render tab.content()}
				</div>
			{/if}
		{/each}
	</div>
</section>

<style>
	.panel {
		background:
			linear-gradient(180deg, rgba(21, 27, 38, 0.98), rgba(15, 20, 29, 0.98)),
			rgba(18, 23, 32, 0.96);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: var(--radius-panel);
		padding: clamp(5px, 0.45vw, 8px);
		margin-top: 0;
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		height: 100%;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
		position: relative;
		box-shadow:
			0 8px 24px rgba(0, 0, 0, 0.16),
			inset 0 1px 0 rgba(255, 255, 255, 0.025);
	}
	.panel::before {
		content: '';
		position: absolute;
		inset: 0 0 auto;
		height: 2px;
		background: linear-gradient(90deg, rgba(96, 165, 250, 0.6), rgba(48, 213, 200, 0.18));
		opacity: 0.75;
	}

	.tab-bar {
		display: flex;
		gap: 2px;
		padding: 3px;
		margin-bottom: 6px;
		background: rgba(2, 6, 12, 0.42);
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-radius: 9px;
		flex: 0 0 auto;
		min-width: 0;
		overflow-x: auto;
		scrollbar-width: none;
	}
	.tab-bar::-webkit-scrollbar { display: none; }

	.tab-btn {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 5px 10px;
		border: none;
		background: transparent;
		color: var(--text-muted);
		font: inherit;
		font-size: 11.5px;
		font-weight: 750;
		letter-spacing: 0.01em;
		border-radius: 7px;
		cursor: pointer;
		white-space: nowrap;
		transition:
			background-color var(--ease-fast),
			color var(--ease-fast);
	}
	.tab-btn:hover {
		color: var(--text-secondary);
		background: rgba(48, 213, 200, 0.06);
	}
	.tab-btn.active {
		background: rgba(48, 213, 200, 0.18);
		color: var(--accent);
		box-shadow: inset 0 0 0 1px rgba(48, 213, 200, 0.32);
	}

	.tab-badge {
		font-size: 9.5px;
		font-weight: 800;
		padding: 1px 6px;
		border-radius: 999px;
		background: rgba(100, 116, 139, 0.28);
		color: var(--text-primary);
		font-variant-numeric: tabular-nums;
		min-width: 16px;
		text-align: center;
	}
	.tab-btn.active .tab-badge {
		background: rgba(48, 213, 200, 0.32);
		color: #0f172a;
	}

	.tab-body {
		flex: 1 1 0;
		min-height: 0;
		min-width: 0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	.tab-panel {
		flex: 1 1 0;
		min-height: 0;
		min-width: 0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}
	/* 탭 안에 들어가는 컴포넌트(panel) 들은 자기 카드 chrome 을 가지고 있는데
	   탭이 이미 panel chrome 을 제공하므로 시각적으로 이중 테두리가 됨.
	   1) 안쪽 panel 의 border / shadow / 배경을 무력화하고
	   2) header 의 bottom border 만 keep (탭 안에서도 헤더는 보여야 함). */
	.tab-panel :global(.panel) {
		background: transparent;
		border: none;
		box-shadow: none;
		padding: 0;
		border-radius: 0;
		height: 100%;
		width: 100%;
	}
	.tab-panel :global(.panel::before) {
		display: none;
	}
</style>
