<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { browser } from '$app/environment';

	type ModelAsset = {
		id: string;
		owner: number;
		owner_username: string;
		name: string;
		slug: string;
		description: string;
		visibility: 'private' | 'shared';
		framework: string;
		task: string;
		tags: string[];
		version_count: number;
		created_at: string;
		updated_at: string;
	};

	type ModelVersion = {
		id: string;
		asset: string;
		asset_slug: string;
		version: string;
		original_filename: string;
		size_bytes: number;
		sha256: string;
		status: string;
		uploaded_by_username: string | null;
		created_at: string;
	};

	type Template = {
		id: string;
		name: string;
		default_model_version_ids?: string[];
	};

	let assets = $state<ModelAsset[]>([]);
	let versions = $state<ModelVersion[]>([]);
	let templates = $state<Template[]>([]);
	let loading = $state(false);
	let errorMsg = $state('');
	let visibilityFilter = $state<'all' | 'shared' | 'private'>('all');
	let busyId = $state('');
	let expandedId = $state<string | null>(null);

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
			const [assetRes, versionRes, tplRes] = await Promise.all([
				fetch(`${base}/api/model-assets/?page_size=200&ordering=-created_at`, {
					headers: { Authorization: `Bearer ${t}` },
				}),
				fetch(`${base}/api/model-versions/?page_size=500&ordering=-created_at`, {
					headers: { Authorization: `Bearer ${t}` },
				}),
				fetch(`${base}/api/templates/?page_size=200`, {
					headers: { Authorization: `Bearer ${t}` },
				}),
			]);
			const aj = await assetRes.json();
			const vj = await versionRes.json();
			const tj = await tplRes.json();
			if (!assetRes.ok) throw new Error(aj?.detail || `HTTP ${assetRes.status}`);
			assets = aj?.data?.results ?? [];
			versions = vj?.data?.results ?? [];
			templates = tj?.data?.results ?? [];
		} catch (error: any) {
			errorMsg = error?.message || '모델 자산을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	async function deleteAsset(asset: ModelAsset) {
		if (busyId) return;
		if (!confirm(`모델 자산 "${asset.name}" 을(를) 삭제합니다. 이 자산의 모든 버전과 파일이 사라지며, 이를 default model로 묶고 있는 템플릿은 해당 참조를 잃습니다. 계속하시겠습니까?`))
			return;
		const t = token();
		if (!t) return;
		busyId = asset.id;
		try {
			const res = await fetch(`${base}/api/model-assets/${asset.id}/`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${t}` },
			});
			if (!res.ok) {
				const j = await res.json().catch(() => ({}));
				throw new Error(j?.detail || `HTTP ${res.status}`);
			}
			await load();
		} catch (error: any) {
			errorMsg = error?.message || '삭제에 실패했습니다.';
		} finally {
			busyId = '';
		}
	}

	function versionsFor(assetId: string): ModelVersion[] {
		return versions.filter((v) => v.asset === assetId);
	}

	function totalSize(assetId: string): number {
		return versionsFor(assetId).reduce((s, v) => s + (v.size_bytes || 0), 0);
	}

	function templatesUsing(assetId: string): Template[] {
		const versionIds = new Set(versionsFor(assetId).map((v) => v.id));
		return templates.filter((tpl) =>
			(tpl.default_model_version_ids ?? []).some((id) => versionIds.has(id)),
		);
	}

	function formatBytes(bytes: number): string {
		if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
		if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
		if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${bytes} B`;
	}

	function formatTime(iso: string): string {
		try {
			return new Date(iso).toLocaleString('ko-KR');
		} catch {
			return iso;
		}
	}

	function toggleExpanded(id: string) {
		expandedId = expandedId === id ? null : id;
	}

	let visibleAssets = $derived(
		visibilityFilter === 'all' ? assets : assets.filter((a) => a.visibility === visibilityFilter),
	);

	onMount(load);
</script>

<div class="page">
	<div class="page-header">
		<div>
			<h1>모델 자산</h1>
			<p class="subtitle">
				등록된 ModelAsset · ModelVersion 카탈로그. 사용자 요청을 승인하거나 wizard로 직접 등록한
				결과가 여기에 모입니다. 자산을 삭제하면 모든 버전과 파일이 함께 사라지므로 사용 중인
				템플릿이 있는지 확인 후 처리하세요.
			</p>
		</div>
		<div class="controls">
			<div class="filter-group">
				<button class="filter-btn" class:active={visibilityFilter === 'all'} onclick={() => (visibilityFilter = 'all')}>전체</button>
				<button class="filter-btn" class:active={visibilityFilter === 'shared'} onclick={() => (visibilityFilter = 'shared')}>shared</button>
				<button class="filter-btn" class:active={visibilityFilter === 'private'} onclick={() => (visibilityFilter = 'private')}>private</button>
			</div>
			<button class="refresh-btn" onclick={load} disabled={loading}>
				{loading ? '불러오는 중…' : '새로고침'}
			</button>
		</div>
	</div>

	{#if errorMsg}
		<div class="error-box">{errorMsg}</div>
	{/if}

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th></th>
					<th>이름 / slug</th>
					<th>분류</th>
					<th>가시성</th>
					<th class="num">버전</th>
					<th class="num">총 용량</th>
					<th>사용 템플릿</th>
					<th>등록자</th>
					<th>등록일</th>
					<th class="col-actions"></th>
				</tr>
			</thead>
			<tbody>
				{#if !loading && visibleAssets.length === 0}
					<tr class="empty-row">
						<td colspan="10">
							<div class="empty-inline">
								<div class="empty-icon">📦</div>
								<div class="empty-text">등록된 모델 자산이 없습니다.</div>
							</div>
						</td>
					</tr>
				{:else}
					{#each visibleAssets as a (a.id)}
						{@const using = templatesUsing(a.id)}
						{@const expanded = expandedId === a.id}
						<tr class:expanded>
							<td>
								<button class="toggle" aria-label="버전 토글" onclick={() => toggleExpanded(a.id)}>
									{expanded ? '▾' : '▸'}
								</button>
							</td>
							<td>
								<div class="cell-name">
									<strong>{a.name}</strong>
									<span class="mono">{a.slug}</span>
									{#if a.description}<em>{a.description}</em>{/if}
								</div>
							</td>
							<td>
								<div class="chips">
									{#if a.framework}<span class="chip">{a.framework}</span>{/if}
									{#if a.task}<span class="chip">{a.task}</span>{/if}
								</div>
							</td>
							<td>
								<span class="vis vis-{a.visibility}">{a.visibility}</span>
							</td>
							<td class="num">{a.version_count}</td>
							<td class="num">{formatBytes(totalSize(a.id))}</td>
							<td>
								{#if using.length === 0}
									<span class="muted">-</span>
								{:else}
									<div class="using">
										{#each using as tpl (tpl.id)}
											<span class="chip chip-tpl" title={tpl.name}>{tpl.name}</span>
										{/each}
									</div>
								{/if}
							</td>
							<td>{a.owner_username}</td>
							<td class="ts">{formatTime(a.created_at)}</td>
							<td class="col-actions">
								<button class="danger" disabled={busyId === a.id} onclick={() => deleteAsset(a)}>
									{busyId === a.id ? '삭제 중…' : '삭제'}
								</button>
							</td>
						</tr>
						{#if expanded}
							<tr class="version-row">
								<td></td>
								<td colspan="9">
									<table class="version-table">
										<thead>
											<tr>
												<th>버전</th>
												<th>파일명</th>
												<th class="num">크기</th>
												<th>SHA256</th>
												<th>상태</th>
												<th>업로더</th>
												<th>등록일</th>
											</tr>
										</thead>
										<tbody>
											{#each versionsFor(a.id) as v (v.id)}
												<tr>
													<td><strong>{v.version}</strong></td>
													<td class="mono small">{v.original_filename || '-'}</td>
													<td class="num">{formatBytes(v.size_bytes)}</td>
													<td class="mono small" title={v.sha256}>{(v.sha256 || '').slice(0, 16) || '-'}</td>
													<td><span class="status-{v.status}">{v.status}</span></td>
													<td>{v.uploaded_by_username ?? '-'}</td>
													<td class="ts">{formatTime(v.created_at)}</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</td>
							</tr>
						{/if}
					{/each}
				{/if}
			</tbody>
		</table>
	</div>
</div>

<style>
	/* Layout-level :global() controls .page / .page-header / h1 / .subtitle /
	   .controls / .filter-group / .filter-btn / .refresh-btn / .error-box /
	   .empty / .table-wrap / table / thead / tbody / .chip so this panel
	   only declares panel-specific styling. */
	tbody tr.expanded {
		background: rgba(77, 191, 179, 0.04);
	}
	.ts {
		white-space: nowrap;
		color: var(--text-secondary);
	}
	.mono {
		font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
		color: var(--text-muted);
	}
	.small {
		font-size: 11.5px;
	}

	.cell-name {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.cell-name strong {
		color: var(--text-primary);
		font-size: 13.5px;
	}
	.cell-name em {
		font-style: normal;
		color: var(--text-muted);
		font-size: 11.5px;
	}

	.chips,
	.using {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}
	/* .chip is provided by admin layout :global(). The template-name
	   variant needs case preserved; bump specificity with parent class
	   so it wins against the layout's .admin-body .chip rule. */
	.using .chip.chip-tpl {
		text-transform: none;
		letter-spacing: 0;
		color: var(--accent);
		background: rgba(77, 191, 179, 0.10);
		max-width: 240px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.muted {
		color: var(--text-muted);
	}

	.vis {
		padding: 2px 8px;
		border-radius: 5px;
		font-weight: 800;
		font-size: 11px;
	}
	.vis-shared {
		color: var(--accent);
		background: rgba(77, 191, 179, 0.12);
	}
	.vis-private {
		color: var(--text-muted);
		background: rgba(100, 116, 139, 0.18);
	}

	.col-actions {
		white-space: nowrap;
		text-align: right;
	}
	button.danger {
		background: transparent;
		border: 1px solid rgba(239, 68, 68, 0.45);
		color: var(--error);
		padding: 5px 10px;
		font-size: 11.5px;
		border-radius: var(--radius-sm);
		cursor: pointer;
		font-family: inherit;
	}
	button.danger:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.10);
	}
	button.danger:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.toggle {
		background: transparent;
		border: none;
		color: var(--text-secondary);
		font: inherit;
		cursor: pointer;
		padding: 0 4px;
	}
	.toggle:hover {
		color: var(--accent);
	}

	tr.version-row td {
		background: rgba(13, 17, 23, 0.4);
		padding: 10px 12px 14px;
	}
	.version-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 12px;
	}
	.version-table thead th {
		background: transparent;
		border-bottom: 1px solid rgba(100, 116, 139, 0.18);
		padding: 6px 10px;
		position: static;
	}
	.version-table tbody td {
		padding: 6px 10px;
		border-bottom: none;
	}

	.status-available {
		color: var(--accent);
		font-weight: 800;
	}
	.status-failed {
		color: var(--error);
		font-weight: 800;
	}
</style>
