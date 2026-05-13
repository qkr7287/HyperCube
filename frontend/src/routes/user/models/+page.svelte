<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';

	type ModelAsset = {
		id: string;
		name: string;
		slug: string;
		description: string;
		visibility: string;
		framework: string;
		task: string;
		version_count: number;
	};

	type ModelVersion = {
		id: string;
		asset: string;
		asset_name: string;
		asset_slug: string;
		version: string;
		original_filename: string;
		size_bytes: number;
		sha256: string;
		status: string;
		created_at: string;
	};

	let loading = $state(false);
	let busy = $state(false);
	let errorMsg = $state('');
	let assets = $state<ModelAsset[]>([]);
	let versions = $state<ModelVersion[]>([]);
	let selectedAssetId = $state('');
	let newName = $state('');
	let newSlug = $state('');
	let newFramework = $state('');
	let newTask = $state('');
	let uploadVersion = $state('v1');
	let uploadFile = $state<File | null>(null);

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
			const [assetRes, versionRes] = await Promise.all([
				fetch(`${base}/api/model-assets/?page_size=100&ordering=name`, {
					headers: { Authorization: `Bearer ${t}` },
				}),
				fetch(`${base}/api/model-versions/?page_size=100&ordering=-created_at`, {
					headers: { Authorization: `Bearer ${t}` },
				}),
			]);
			const assetJson = await assetRes.json().catch(() => ({}));
			const versionJson = await versionRes.json().catch(() => ({}));
			if (!assetRes.ok) throw new Error(assetJson?.detail || `HTTP ${assetRes.status}`);
			if (!versionRes.ok) throw new Error(versionJson?.detail || `HTTP ${versionRes.status}`);
			assets = assetJson.data?.results ?? [];
			versions = versionJson.data?.results ?? [];
			if (!selectedAssetId && assets.length) selectedAssetId = assets[0].id;
		} catch (error: any) {
			errorMsg = error?.message || '모델 목록을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	async function createAsset() {
		const t = token();
		if (!t || busy || !newName || !newSlug) return;
		busy = true;
		errorMsg = '';
		try {
			const res = await fetch(`${base}/api/model-assets/`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${t}`,
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					name: newName,
					slug: newSlug,
					visibility: 'private',
					framework: newFramework,
					task: newTask,
				}),
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || json?.error || `HTTP ${res.status}`);
			newName = '';
			newSlug = '';
			newFramework = '';
			newTask = '';
			await load();
		} catch (error: any) {
			errorMsg = error?.message || '모델 등록에 실패했습니다.';
		} finally {
			busy = false;
		}
	}

	async function upload() {
		const t = token();
		if (!t || busy || !selectedAssetId || !uploadFile || !uploadVersion) return;
		busy = true;
		errorMsg = '';
		try {
			const form = new FormData();
			form.append('version', uploadVersion);
			form.append('file', uploadFile);
			const res = await fetch(`${base}/api/model-assets/${selectedAssetId}/versions/upload/`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${t}` },
				body: form,
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || json?.error || `HTTP ${res.status}`);
			uploadFile = null;
			await load();
		} catch (error: any) {
			errorMsg = error?.message || '모델 업로드에 실패했습니다.';
		} finally {
			busy = false;
		}
	}

	function slugFromName() {
		if (!newName || newSlug) return;
		newSlug = newName
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-|-$/g, '');
	}

	function formatBytes(value: number) {
		if (!value) return '-';
		if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GB`;
		if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(2)} MB`;
		if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
		return `${value} B`;
	}

	onMount(load);
</script>

<div class="page">
	<section class="page-header">
		<div>
			<p class="eyebrow">Model Catalog</p>
			<h1>모델</h1>
			<p class="subtitle">외부 URL 없이 HyperCube 로컬 저장소에 모델 파일을 등록하고 버전을 관리합니다.</p>
		</div>
		<button class="refresh-btn" onclick={load} disabled={loading}>
			{loading ? '새로고침 중...' : '새로고침'}
		</button>
	</section>

	{#if errorMsg}
		<div class="error">{errorMsg}</div>
	{/if}

	<section class="toolbar">
		<div class="panel">
			<h2>모델 등록</h2>
			<div class="form-grid create-grid">
				<input bind:value={newName} onblur={slugFromName} placeholder="모델 이름" />
				<input bind:value={newSlug} placeholder="slug" />
				<input bind:value={newFramework} placeholder="framework" />
				<input bind:value={newTask} placeholder="task" />
				<button onclick={createAsset} disabled={busy || !newName || !newSlug}>등록</button>
			</div>
		</div>
		<div class="panel">
			<h2>버전 업로드</h2>
			<div class="form-grid upload-grid">
				<select bind:value={selectedAssetId}>
					<option value="" disabled>모델 선택</option>
					{#each assets as asset (asset.id)}
						<option value={asset.id}>{asset.name}</option>
					{/each}
				</select>
				<input bind:value={uploadVersion} placeholder="version" />
				<input
					type="file"
					onchange={(event) => {
						uploadFile = event.currentTarget.files?.[0] ?? null;
					}}
				/>
				<button onclick={upload} disabled={busy || !selectedAssetId || !uploadFile}>업로드</button>
			</div>
		</div>
	</section>

	<section class="content-grid">
		<div>
			<div class="section-head">
				<h2>모델 자산</h2>
				<span>{assets.length} assets</span>
			</div>
			<div class="grid">
				{#each assets as asset (asset.id)}
					<article class="model-card">
						<div class="card-top">
							<div>
								<h3>{asset.name}</h3>
								<p>{asset.slug}</p>
							</div>
							<span class="pill">{asset.visibility}</span>
						</div>
						<div class="meta">
							<span>{asset.framework || '-'}</span>
							<span>{asset.task || '-'}</span>
							<span>{asset.version_count} versions</span>
						</div>
						{#if asset.description}
							<p class="desc">{asset.description}</p>
						{/if}
					</article>
				{/each}
			</div>
			{#if !loading && assets.length === 0}
				<div class="empty">등록된 모델이 없습니다.</div>
			{/if}
		</div>

		<div>
			<div class="section-head">
				<h2>최근 버전</h2>
				<span>{versions.length} versions</span>
			</div>
			<div class="version-list">
				{#each versions as version (version.id)}
					<article class="version-row">
						<div>
							<strong>{version.asset_name}:{version.version}</strong>
							<span>{version.original_filename} · {formatBytes(version.size_bytes)}</span>
						</div>
						<code title={version.sha256}>{version.sha256.slice(0, 12)}</code>
					</article>
				{/each}
			</div>
			{#if !loading && versions.length === 0}
				<div class="empty">업로드된 버전이 없습니다.</div>
			{/if}
		</div>
	</section>
</div>

<style>
	.page {
		padding: clamp(14px, 1.4vw, 28px);
	}

	.page-header,
	.toolbar,
	.card-top,
	.meta,
	.section-head,
	.version-row {
		display: flex;
		gap: 12px;
	}

	.page-header,
	.section-head {
		align-items: center;
		justify-content: space-between;
	}

	.page-header {
		margin-bottom: 14px;
		padding: 14px 16px;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--bg-card);
	}

	.eyebrow {
		margin: 0 0 4px;
		font-size: 11px;
		font-weight: 900;
		color: var(--accent);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	h1,
	h2,
	h3,
	p {
		margin: 0;
	}

	h1 {
		font-size: 24px;
	}

	h2 {
		font-size: 15px;
	}

	h3 {
		font-size: 15px;
		color: var(--text-primary);
	}

	.subtitle,
	.model-card p,
	.empty,
	.version-row span,
	.section-head span {
		color: var(--text-secondary);
		font-size: 12px;
	}

	.toolbar {
		align-items: stretch;
		margin-bottom: 14px;
	}

	.panel,
	.model-card,
	.version-row,
	.error,
	.empty {
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--bg-card);
	}

	.panel {
		flex: 1;
		padding: 12px;
	}

	.form-grid {
		display: grid;
		gap: 8px;
		margin-top: 10px;
	}

	.create-grid {
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(120px, 0.6fr) minmax(120px, 0.6fr) auto;
	}

	.upload-grid {
		grid-template-columns: minmax(0, 1.2fr) minmax(90px, 0.5fr) minmax(0, 1fr) auto;
	}

	input,
	select,
	button {
		min-height: 36px;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--bg-base);
		color: var(--text-primary);
		font: inherit;
	}

	input,
	select {
		padding: 0 10px;
	}

	button {
		padding: 0 12px;
		background: var(--accent);
		color: var(--bg-base);
		font-weight: 900;
		cursor: pointer;
	}

	button:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.error,
	.empty {
		padding: 14px;
		margin-bottom: 14px;
	}

	.error {
		color: var(--error);
	}

	.content-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
		gap: 14px;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 12px;
		margin-top: 10px;
	}

	.model-card,
	.version-row {
		padding: 14px;
	}

	.card-top,
	.version-row {
		justify-content: space-between;
		align-items: flex-start;
	}

	.pill,
	.meta span {
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

	.meta {
		flex-wrap: wrap;
		margin-top: 10px;
	}

	.desc {
		margin-top: 10px;
	}

	.version-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-top: 10px;
	}

	.version-row div {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.version-row strong,
	.version-row span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	code {
		color: var(--text-muted);
		font-size: 11px;
	}

	@media (max-width: 980px) {
		.page-header,
		.toolbar {
			flex-direction: column;
			align-items: stretch;
		}

		.content-grid,
		.create-grid,
		.upload-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
