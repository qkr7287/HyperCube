<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';

	type Workspace = {
		container_id: string;
		name: string;
		image: string;
		status: string;
		agent_hostname?: string;
		template_name?: string | null;
		workspace_kind: string;
		workspace_host_port?: number | null;
		workspace_base_url: string;
		workspace_runtime_expires_at?: string | null;
		workspace_token_expires_at?: string | null;
		workspace_health?: Record<string, any>;
		allocated_gpu_slice_ids?: number[];
		mounted_model_version_ids?: string[];
		mounted_model_versions?: Array<{
			id: string;
			asset_name: string;
			asset_slug: string;
			version: string;
		}>;
	};

	let loading = $state(false);
	let openingId = $state('');
	let errorMsg = $state('');
	let workspaces = $state<Workspace[]>([]);

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function load() {
		const t = token();
		if (!t) return;
		loading = true;
		errorMsg = '';
		try {
			const res = await fetch(`${base}/api/workspaces/?page_size=100&ordering=-last_seen`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const json = await res.json();
			workspaces = json.data?.results ?? [];
		} catch (error: any) {
			errorMsg = error?.message || '워크스페이스 목록을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	async function openWorkspace(workspace: Workspace) {
		const t = token();
		if (!t || openingId) return;
		openingId = workspace.container_id;
		errorMsg = '';
		try {
			const res = await fetch(`${base}/api/workspaces/${workspace.container_id}/open/`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${t}` },
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || json?.error || `HTTP ${res.status}`);
			const url = json.data?.url;
			if (url) window.open(`${base}${url}`, '_blank', 'noopener,noreferrer');
		} catch (error: any) {
			errorMsg = error?.message || 'Jupyter 열기에 실패했습니다.';
		} finally {
			openingId = '';
		}
	}

	function fmt(value?: string | null) {
		if (!value) return '-';
		try {
			return new Intl.DateTimeFormat('ko-KR', {
				month: '2-digit',
				day: '2-digit',
				hour: '2-digit',
				minute: '2-digit',
			}).format(new Date(value));
		} catch {
			return value;
		}
	}

	onMount(load);
</script>

<div class="page">
	<section class="page-header">
		<div>
			<p class="eyebrow">ML Workspace</p>
			<h1>워크스페이스</h1>
			<p class="subtitle">승인된 ML/Jupyter 컨테이너와 GPU, 런타임 상태를 한 화면에서 확인합니다.</p>
		</div>
		<button class="refresh-btn" onclick={load} disabled={loading}>
			{loading ? '새로고침 중...' : '새로고침'}
		</button>
	</section>

	{#if errorMsg}
		<div class="error">{errorMsg}</div>
	{/if}

	{#if !loading && workspaces.length === 0}
		<div class="empty">
			<div class="empty-title">열 수 있는 워크스페이스가 없습니다</div>
			<p>관리자 승인과 agent 생성 응답이 완료되면 여기에 표시됩니다.</p>
		</div>
	{:else}
		<div class="grid">
			{#each workspaces as workspace (workspace.container_id)}
				<article class="workspace-card">
					<div class="card-top">
						<div>
							<h2>{workspace.name}</h2>
							<p class="image">{workspace.image}</p>
						</div>
						<span class="status" data-status={workspace.status}>{workspace.status}</span>
					</div>

					<div class="meta-grid">
						<div>
							<span>서버</span>
							<strong>{workspace.agent_hostname ?? '-'}</strong>
						</div>
						<div>
							<span>템플릿</span>
							<strong>{workspace.template_name ?? '-'}</strong>
						</div>
						<div>
							<span>IDE</span>
							<strong>{workspace.workspace_kind || '-'}</strong>
						</div>
						<div>
							<span>만료</span>
							<strong>{fmt(workspace.workspace_runtime_expires_at)}</strong>
						</div>
					</div>

					<div class="chips">
						<span class="chip">GPU {workspace.allocated_gpu_slice_ids?.length ?? 0}</span>
						{#if workspace.mounted_model_versions?.length}
							{#each workspace.mounted_model_versions as model (model.id)}
								<span class="chip">{model.asset_name}:{model.version}</span>
							{/each}
						{:else}
							<span class="chip">Models {workspace.mounted_model_version_ids?.length ?? 0}</span>
						{/if}
						<span class="chip">Port {workspace.workspace_host_port ?? '-'}</span>
					</div>

					<div class="footer">
						<span class="base-url">{workspace.workspace_base_url || '-'}</span>
						<button
							class="open-btn"
							onclick={() => openWorkspace(workspace)}
							disabled={openingId === workspace.container_id || !workspace.workspace_host_port}
						>
							{openingId === workspace.container_id ? '여는 중...' : 'Jupyter 열기'}
						</button>
					</div>
				</article>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page {
		padding: clamp(14px, 1.4vw, 28px);
	}

	.page-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 14px;
		padding: 14px 16px;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--bg-card);
	}

	.eyebrow {
		margin: 0 0 4px;
		font-size: 11px;
		font-weight: 800;
		color: var(--accent);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	h1,
	h2,
	p {
		margin: 0;
	}

	h1 {
		font-size: 24px;
	}

	.subtitle,
	.image,
	.empty p {
		color: var(--text-secondary);
		font-size: 12px;
	}

	.refresh-btn,
	.open-btn {
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 8px 12px;
		font-weight: 800;
		font-family: inherit;
		cursor: pointer;
	}

	.refresh-btn {
		background: var(--bg-tab);
		color: var(--text-primary);
	}

	.open-btn {
		background: var(--accent);
		color: var(--bg-base);
		border-color: transparent;
	}

	.open-btn:disabled,
	.refresh-btn:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.error,
	.empty {
		margin-bottom: 14px;
		padding: 18px;
		border-radius: 10px;
		border: 1px solid var(--border);
		background: var(--bg-card);
	}

	.error {
		color: var(--error);
		font-size: 13px;
	}

	.empty-title {
		font-size: 17px;
		font-weight: 900;
		margin-bottom: 6px;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
		gap: 12px;
	}

	.workspace-card {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 14px;
		border-radius: 10px;
		border: 1px solid var(--border);
		background: var(--bg-card);
	}

	.card-top,
	.footer {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}

	h2 {
		font-size: 17px;
		font-weight: 900;
		color: var(--text-primary);
	}

	.image,
	.base-url {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.status,
	.chip {
		display: inline-flex;
		align-items: center;
		min-height: 24px;
		padding: 3px 8px;
		border-radius: 7px;
		background: rgba(48, 213, 200, 0.14);
		color: var(--accent);
		font-size: 11px;
		font-weight: 900;
	}

	.status[data-status='failed'],
	.status[data-status='dead'],
	.status[data-status='exited'] {
		background: rgba(239, 68, 68, 0.14);
		color: var(--error);
	}

	.meta-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 8px;
	}

	.meta-grid div {
		min-width: 0;
		padding: 9px;
		border-radius: 8px;
		border: 1px solid rgba(100, 116, 139, 0.16);
		background: rgba(2, 6, 12, 0.24);
	}

	.meta-grid span {
		display: block;
		margin-bottom: 3px;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 900;
	}

	.meta-grid strong {
		display: block;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 12px;
		color: var(--text-primary);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.base-url {
		min-width: 0;
		color: var(--text-muted);
		font-size: 11px;
		align-self: center;
	}

	@media (max-width: 760px) {
		.page-header,
		.card-top,
		.footer {
			flex-direction: column;
			align-items: stretch;
		}

		.grid,
		.meta-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
