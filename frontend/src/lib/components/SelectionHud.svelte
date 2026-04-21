<script lang="ts">
	interface Container {
		id: string;
		shortId: string;
		names: string[];
		image: string;
		state: string;
		status: string;
		labels: any;
		networks?: string[];
		mounts?: { name: string; type: 'volume' }[];
	}

	export type HudSelection =
		| { kind: 'container'; container: Container }
		| {
				kind: 'stack';
				name: string;
				total: number;
				running: number;
				stopped: number;
		  }
		| {
				kind: 'network';
				name: string;
				memberCount: number;
				stacks: string[];
		  }
		| {
				kind: 'volume';
				name: string;
				memberCount: number;
				stacks: string[];
		  };

	let {
		selection = null,
		onClose = () => {},
		onOpenDetail = () => {},
	}: {
		selection: HudSelection | null;
		onClose: () => void;
		onOpenDetail: (container: Container) => void;
	} = $props();

	function containerName(c: Container): string {
		return c.names?.[0]?.replace('/', '') || c.shortId;
	}

	function stateLabel(state: string): string {
		if (state === 'running') return 'Running';
		if (state === 'exited') return 'Stopped';
		if (state === 'paused') return 'Paused';
		if (state === 'restarting') return 'Restarting';
		return state || '-';
	}

	function stateToneClass(state: string): string {
		if (state === 'running') return 'tone-running';
		if (state === 'exited') return 'tone-stopped';
		return 'tone-other';
	}
</script>

{#if selection}
	<div class="hud" role="dialog" aria-label="Selection details">
		<div class="hud-header">
			{#if selection.kind === 'container'}
				<span class="badge badge-container">CONTAINER</span>
			{:else if selection.kind === 'stack'}
				<span class="badge badge-stack">STACK</span>
			{:else if selection.kind === 'network'}
				<span class="badge badge-network">NETWORK</span>
			{:else if selection.kind === 'volume'}
				<span class="badge badge-volume">VOLUME</span>
			{/if}
			<button class="close-btn" onclick={onClose} aria-label="Close">
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12" />
				</svg>
			</button>
		</div>

		{#if selection.kind === 'container'}
			{@const c = selection.container}
			<div class="hud-title" title={containerName(c)}>{containerName(c)}</div>
			<dl class="hud-rows">
				<div class="row">
					<dt>State</dt>
					<dd class={stateToneClass(c.state)}>{stateLabel(c.state)}</dd>
				</div>
				<div class="row">
					<dt>Image</dt>
					<dd class="mono truncate" title={c.image}>{c.image || '-'}</dd>
				</div>
				{#if c.networks && c.networks.length}
					<div class="row">
						<dt>Networks</dt>
						<dd>{c.networks.length}</dd>
					</div>
				{/if}
				{#if c.mounts && c.mounts.length}
					<div class="row">
						<dt>Volumes</dt>
						<dd>{c.mounts.filter((m) => m.type === 'volume').length}</dd>
					</div>
				{/if}
			</dl>
			<button class="detail-btn" onclick={() => onOpenDetail(c)}>상세보기</button>
		{:else if selection.kind === 'stack'}
			<div class="hud-title" title={selection.name}>{selection.name}</div>
			<dl class="hud-rows">
				<div class="row">
					<dt>Containers</dt>
					<dd>{selection.total}</dd>
				</div>
				<div class="row">
					<dt>Running</dt>
					<dd class="tone-running">{selection.running}</dd>
				</div>
				<div class="row">
					<dt>Stopped</dt>
					<dd class="tone-stopped">{selection.stopped}</dd>
				</div>
			</dl>
		{:else if selection.kind === 'network'}
			<div class="hud-title mono" title={selection.name}>{selection.name}</div>
			<dl class="hud-rows">
				<div class="row">
					<dt>Members</dt>
					<dd>{selection.memberCount}</dd>
				</div>
				{#if selection.stacks.length}
					<div class="row">
						<dt>Stacks</dt>
						<dd class="truncate" title={selection.stacks.join(', ')}>
							{selection.stacks.join(', ')}
						</dd>
					</div>
				{/if}
			</dl>
		{:else if selection.kind === 'volume'}
			<div class="hud-title mono" title={selection.name}>{selection.name}</div>
			<dl class="hud-rows">
				<div class="row">
					<dt>Members</dt>
					<dd>{selection.memberCount}</dd>
				</div>
				{#if selection.stacks.length}
					<div class="row">
						<dt>Stacks</dt>
						<dd class="truncate" title={selection.stacks.join(', ')}>
							{selection.stacks.join(', ')}
						</dd>
					</div>
				{/if}
			</dl>
		{/if}
	</div>
{/if}

<style>
	.hud {
		position: absolute;
		left: 20px;
		bottom: 20px;
		min-width: 260px;
		max-width: 360px;
		background: rgba(13, 17, 23, 0.92);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 16px;
		color: var(--text-primary);
		font-size: 12px;
		backdrop-filter: blur(6px);
		pointer-events: auto;
		z-index: 20;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
	}

	.hud-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10px;
	}

	.badge {
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.08em;
		padding: 3px 8px;
		border-radius: 999px;
		border: 1px solid;
	}

	.badge-container {
		color: var(--accent);
		border-color: var(--accent);
		background: rgba(48, 213, 200, 0.08);
	}
	.badge-stack {
		color: #a78bfa;
		border-color: #a78bfa;
		background: rgba(167, 139, 250, 0.08);
	}
	.badge-network {
		color: #38bdf8;
		border-color: #38bdf8;
		background: rgba(56, 189, 248, 0.08);
	}
	.badge-volume {
		color: #fb923c;
		border-color: #fb923c;
		background: rgba(251, 146, 60, 0.08);
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--text-muted);
		cursor: pointer;
		padding: 2px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		transition: color 0.15s;
	}
	.close-btn:hover {
		color: var(--text-primary);
	}

	.hud-title {
		font-size: 14px;
		font-weight: 700;
		color: var(--text-primary);
		margin-bottom: 10px;
		word-break: break-all;
	}

	.hud-rows {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0 0 12px;
	}

	.row {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		font-size: 12px;
	}

	.row dt {
		color: var(--text-muted);
		font-weight: 500;
	}

	.row dd {
		margin: 0;
		color: var(--text-primary);
		font-weight: 600;
		text-align: right;
		min-width: 0;
	}

	.mono {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
	}

	.truncate {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 220px;
	}

	.tone-running {
		color: var(--accent);
	}
	.tone-stopped {
		color: var(--error);
	}
	.tone-other {
		color: #fbbf24;
	}

	.detail-btn {
		width: 100%;
		background: var(--accent);
		color: var(--accent-dark);
		border: none;
		border-radius: 8px;
		padding: 8px 12px;
		font-size: 12px;
		font-weight: 700;
		cursor: pointer;
		transition: opacity 0.15s;
	}
	.detail-btn:hover {
		opacity: 0.85;
	}
</style>
