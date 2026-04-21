<script lang="ts">
	interface Tab {
		value: string;
		label: string;
		count: number;
	}

	let {
		tabs = [] as Tab[],
		active = 'all',
		onchange = (_value: string) => {},
	} = $props();
</script>

<div class="tab-bar">
	{#each tabs as tab (tab.value)}
		<button
			class="tab"
			class:active={active === tab.value}
			onclick={() => onchange(tab.value)}
		>
			{tab.label}
			<span class="tab-count">{tab.count}</span>
		</button>
	{/each}
</div>

<style>
	.tab-bar {
		display: flex;
		gap: 2px;
		background: var(--bg-tab);
		border-radius: 10px;
		padding: 3px;
	}

	.tab {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 7px 16px;
		border: none;
		border-radius: 8px;
		background: transparent;
		color: var(--text-secondary);
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.15s;
	}

	.tab:hover {
		color: var(--text-primary);
	}

	.tab.active {
		background: var(--bg-card);
		color: var(--accent);
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
	}

	.tab-count {
		font-size: 11px;
		font-weight: 700;
		padding: 1px 7px;
		border-radius: 9999px;
		background: rgba(100, 116, 139, 0.15);
		color: inherit;
	}

	.tab.active .tab-count {
		background: rgba(48, 213, 200, 0.15);
		color: var(--accent);
	}
</style>
