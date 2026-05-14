<script lang="ts">
	import { browser } from '$app/environment';
	import { base } from '$app/paths';

	type Prefill = {
		templateId?: string | null;
		agentId?: string | null;
		customName?: string | null;
		selectedImage?: string | null;
	} | null;

	let {
		open = false,
		prefill = null as Prefill,
		onClose = () => {},
		onSubmitted = () => {},
	}: {
		open?: boolean;
		prefill?: Prefill;
		onClose?: () => void;
		onSubmitted?: () => void;
	} = $props();

	type Template = {
		id: string;
		name: string;
		kind: string;
		category?: string;
		image: string;
		image_options: Array<{ label: string; image: string }>;
		env_schema: Array<Record<string, any>>;
		port_schema: Array<Record<string, any>>;
		description: string;
		requires_gpu?: boolean;
		workspace_enabled?: boolean;
		workspace_kind?: string;
		default_max_runtime_hours?: number | null;
	};

	type Agent = {
		id: string;
		hostname: string;
		ip_address: string;
		is_active: boolean;
	};

	type GpuSlice = {
		id: number;
		kind: string;
		device_id: string;
		label?: string;
		mig_profile?: string;
		memory_mb: number;
		status: string;
		allow_shared?: boolean;
		gpuName?: string;
		gpuIndex?: number;
	};

	type GpuDevice = {
		id: number;
		index: number;
		name: string;
		uuid: string;
		total_memory_mb: number;
		status: string;
		slices: GpuSlice[];
	};

	type ModelVersion = {
		id: string;
		asset: string;
		asset_name: string;
		asset_slug: string;
		version: string;
		size_bytes: number;
		sha256: string;
		status: string;
	};

	type CacheStatus = {
		version: string;
		status: string;
		mountPath?: string;
		prepareJob?: {
			id: string;
			status: string;
			progressPercent?: number | null;
			progressMessage?: string;
		} | null;
	};

	let templates = $state<Template[]>([]);
	let agents = $state<Agent[]>([]);
	let gpuDevices = $state<GpuDevice[]>([]);
	let modelVersions = $state<ModelVersion[]>([]);
	let cacheStatuses = $state<Record<string, CacheStatus>>({});
	let selectedTemplate = $state<Template | null>(null);
	let selectedAgent = $state('');
	let selectedGpuSliceIds = $state<number[]>([]);
	let gpuShareOk = $state(false);
	let selectedModelVersionIds = $state<string[]>([]);
	let selectedImage = $state('');
	let customName = $state('');
	let envValues = $state<Record<string, string>>({});
	let portValues = $state<Record<number, number>>({});
	let requestedMaxRuntimeHours = $state<number | null>(null);
	let templateTab = $state<'ml' | 'general'>('ml');
	let busy = $state(false);
	let loading = $state(false);
	let gpuLoading = $state(false);
	let cacheLoading = $state(false);
	let errorMsg = $state('');
	let lastGpuAgent = '';
	let lastCacheKey = '';

	let visibleTemplates = $derived(
		templates.filter((tpl) => (templateTab === 'ml' ? tpl.category === 'ml' : tpl.category !== 'ml')),
	);

	let gpuSlices = $derived(
		gpuDevices.flatMap((device) =>
			(device.slices ?? []).map((slice) => ({
				...slice,
				gpuName: device.name,
				gpuIndex: device.index,
			})),
		),
	);
	let selectedGpuSlice = $derived(gpuSlices.find((slice) => selectedGpuSliceIds.includes(slice.id)) ?? null);
	let selectedGpuCanShare = $derived(Boolean(selectedGpuSlice?.allow_shared));

	let canSubmit = $derived(
		!!selectedTemplate &&
			!!selectedAgent &&
			(!selectedTemplate.requires_gpu || selectedGpuSliceIds.length > 0) &&
			!busy,
	);

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	$effect(() => {
		if (!open) return;
		resetForm();
		loadData().then(() => {
			if (prefill) applyPrefill(prefill);
		});
	});

	function applyPrefill(p: Exclude<Prefill, null>) {
		if (p.agentId) selectedAgent = p.agentId;
		if (p.templateId) {
			const tpl = templates.find((t) => t.id === p.templateId);
			if (tpl) selectTemplate(tpl);
		}
		if (p.customName) customName = p.customName;
		if (p.selectedImage) selectedImage = p.selectedImage;
	}

	$effect(() => {
		if (!open || !selectedAgent || selectedAgent === lastGpuAgent) return;
		lastGpuAgent = selectedAgent;
		selectedGpuSliceIds = [];
		gpuShareOk = false;
		loadGpuInventory(selectedAgent);
	});

	$effect(() => {
		if (!selectedGpuCanShare && gpuShareOk) gpuShareOk = false;
	});

	$effect(() => {
		const key = `${selectedAgent}:${modelVersions.map((version) => version.id).join(',')}`;
		if (!open || !selectedAgent || modelVersions.length === 0 || key === lastCacheKey) return;
		lastCacheKey = key;
		loadCacheStatus();
	});

	function resetForm() {
		selectedTemplate = null;
		selectedAgent = '';
		selectedGpuSliceIds = [];
		gpuShareOk = false;
		selectedModelVersionIds = [];
		selectedImage = '';
		customName = '';
		envValues = {};
		portValues = {};
		requestedMaxRuntimeHours = null;
		templateTab = 'ml';
		gpuDevices = [];
		cacheStatuses = {};
		errorMsg = '';
		lastGpuAgent = '';
		lastCacheKey = '';
	}

	async function loadData() {
		const t = token();
		if (!t) return;
		loading = true;
		try {
			const [tplRes, agentRes, modelRes] = await Promise.all([
				fetch(`${base}/api/templates/?page_size=100`, { headers: { Authorization: `Bearer ${t}` } }),
				fetch(`${base}/api/agents/?status=approved&active=true`, { headers: { Authorization: `Bearer ${t}` } }),
				fetch(`${base}/api/model-versions/?page_size=100&ordering=-created_at`, {
					headers: { Authorization: `Bearer ${t}` },
				}),
			]);

			const tplJson = await tplRes.json().catch(() => ({}));
			const agentJson = await agentRes.json().catch(() => ({}));
			const modelJson = await modelRes.json().catch(() => ({}));

			if (!tplRes.ok) throw new Error(humanizeError(tplJson, '템플릿을 불러오지 못했습니다.'));
			if (!agentRes.ok) throw new Error(humanizeError(agentJson, '서버 목록을 불러오지 못했습니다.'));
			if (!modelRes.ok) throw new Error(humanizeError(modelJson, '모델 목록을 불러오지 못했습니다.'));

			templates = tplJson.data?.results ?? [];
			agents = agentJson.data?.results ?? [];
			modelVersions = modelJson.data?.results ?? [];

			if (agents.length === 1) selectedAgent = agents[0].id;
			if (!templates.some((tpl) => tpl.category === 'ml')) templateTab = 'general';
		} catch (error: any) {
			errorMsg = error?.message || '요청 정보를 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	async function loadGpuInventory(agentId: string) {
		const t = token();
		if (!t) return;
		gpuLoading = true;
		try {
			const res = await fetch(`${base}/api/agents/${agentId}/gpus/`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(humanizeError(json, `GPU inventory 요청 실패 (${res.status})`));
			gpuDevices = json.data?.devices ?? [];
		} catch (error: any) {
			errorMsg = error?.message || 'GPU 정보를 불러오지 못했습니다.';
			gpuDevices = [];
		} finally {
			gpuLoading = false;
		}
	}

	async function loadCacheStatus() {
		const t = token();
		if (!t || !selectedAgent || modelVersions.length === 0) return;
		cacheLoading = true;
		try {
			const versionList = modelVersions.map((version) => version.id).join(',');
			const res = await fetch(
				`${base}/api/model-versions/cache-status/?agent=${selectedAgent}&versions=${encodeURIComponent(versionList)}`,
				{ headers: { Authorization: `Bearer ${t}` } },
			);
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(humanizeError(json, `모델 캐시 상태 요청 실패 (${res.status})`));
			cacheStatuses = Object.fromEntries((json.data?.results ?? []).map((row: CacheStatus) => [row.version, row]));
		} catch {
			cacheStatuses = {};
		} finally {
			cacheLoading = false;
		}
	}

	function selectTemplate(tpl: Template) {
		selectedTemplate = tpl;
		selectedImage = tpl.image || (tpl.image_options?.[0]?.image ?? '');
		requestedMaxRuntimeHours = tpl.default_max_runtime_hours ?? null;
		envValues = {};
		portValues = {};
		selectedGpuSliceIds = [];
		gpuShareOk = false;
		for (const env of tpl.env_schema ?? []) envValues[env.key] = env.default ?? '';
		for (const port of tpl.port_schema ?? []) portValues[port.internal] = port.host_default ?? port.internal;
	}

	function selectGpuSlice(sliceId: number) {
		selectedGpuSliceIds = selectedGpuSliceIds[0] === sliceId ? [] : [sliceId];
		gpuShareOk = false;
	}

	function toggleModel(versionId: string) {
		selectedModelVersionIds = selectedModelVersionIds.includes(versionId)
			? selectedModelVersionIds.filter((id) => id !== versionId)
			: [...selectedModelVersionIds, versionId];
	}

	async function submit() {
		if (!selectedTemplate || !selectedAgent || !canSubmit) return;
		busy = true;
		errorMsg = '';

		const t = token();
		if (!t) {
			errorMsg = '로그인이 필요합니다.';
			busy = false;
			return;
		}

		const customPorts = (selectedTemplate.port_schema ?? []).map((port: any) => ({
			host: portValues[port.internal] ?? port.host_default,
			container: port.internal,
			protocol: 'tcp',
		}));
		const body: Record<string, any> = {
			action: 'create',
			template: selectedTemplate.id,
			target_agent: selectedAgent,
			custom_name: customName.trim(),
			selected_image: selectedImage,
			custom_env: envValues,
			custom_ports: customPorts,
			gpu_slice_ids: selectedGpuSliceIds,
			gpu_share_ok: gpuShareOk,
			model_version_ids: selectedModelVersionIds,
		};
		if (requestedMaxRuntimeHours) body.requested_max_runtime_hours = requestedMaxRuntimeHours;

		try {
			const res = await fetch(`${base}/api/requests/`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${t}`,
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(body),
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(humanizeError(json, `요청 제출 실패 (${res.status})`));
			onSubmitted();
			onClose();
		} catch (error: any) {
			errorMsg = error?.message || '요청 제출에 실패했습니다.';
		} finally {
			busy = false;
		}
	}

	function humanizeError(payload: any, fallback: string) {
		if (!payload || typeof payload !== 'object') return fallback;
		const direct = payload.detail || payload.message || payload.error?.detail;
		if (typeof direct === 'string') return translateError(direct);

		const source =
			payload.error && typeof payload.error === 'object' && !Array.isArray(payload.error) ? payload.error : payload;
		const messages: string[] = [];
		for (const [key, value] of Object.entries(source)) {
			if (['data', 'status', 'success'].includes(key)) continue;
			const label = fieldLabel(key);
			if (Array.isArray(value)) {
				for (const item of value) messages.push(`${label}: ${translateError(String(item))}`);
			} else if (typeof value === 'string') {
				messages.push(`${label}: ${translateError(value)}`);
			}
		}
		return messages.length > 0 ? messages.join(' / ') : fallback;
	}

	function fieldLabel(key: string) {
		if (key === 'gpu_slice_ids') return 'GPU';
		if (key === 'model_version_ids') return '모델';
		if (key === 'target_agent') return '서버';
		if (key === 'template') return '템플릿';
		return key;
	}

	function translateError(message: string) {
		if (message.includes('requires a GPU slice')) return 'GPU가 필요한 템플릿입니다. GPU slice를 선택하세요.';
		if (message.includes('must belong to the target agent')) return '선택한 GPU가 대상 서버에 속하지 않습니다.';
		if (message.includes('Shared GPU mode is disabled')) return '공유 GPU 모드는 아직 관리자 정책에서 비활성화되어 있습니다.';
		return message;
	}

	function sliceModeLabel(slice: GpuSlice) {
		if (slice.kind === 'mig') return `MIG ${slice.mig_profile || ''}`.trim();
		return 'Full GPU';
	}

	function formatMb(value: number) {
		if (!value) return '-';
		if (value >= 1024) return `${(value / 1024).toFixed(1)} GB`;
		return `${value} MB`;
	}

	function formatBytes(value: number) {
		if (!value) return '-';
		if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`;
		if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`;
		if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
		return `${value} B`;
	}

	function cacheLabel(versionId: string) {
		const status = cacheStatuses[versionId]?.status ?? 'missing';
		if (status === 'ready') return '캐시 완료';
		if (status === 'preparing') return '준비 중';
		if (status === 'failed') return '준비 실패';
		return '준비 필요';
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onClose();
	}

	$effect(() => {
		if (!open) return;
		document.addEventListener('keydown', handleKeydown);
		return () => document.removeEventListener('keydown', handleKeydown);
	});
</script>

{#if open}
	<div class="overlay" onclick={onClose} role="dialog" aria-modal="true">
		<div class="modal" onclick={(event) => event.stopPropagation()}>
			<header class="modal-header">
				<div>
					<p>Container Request</p>
					<h2>{selectedTemplate ? selectedTemplate.name : '새 컨테이너 요청'}</h2>
				</div>
				<button type="button" class="icon-btn" onclick={onClose} aria-label="닫기">x</button>
			</header>

			<div class="modal-content">
				{#if !selectedTemplate}
					<div class="tabs">
						<button type="button" class:active={templateTab === 'ml'} onclick={() => (templateTab = 'ml')}>
							ML Workspace
						</button>
						<button type="button" class:active={templateTab === 'general'} onclick={() => (templateTab = 'general')}>
							General
						</button>
					</div>

					{#if loading}
						<div class="empty">템플릿을 불러오는 중입니다.</div>
					{:else if visibleTemplates.length === 0}
						<div class="empty">선택 가능한 템플릿이 없습니다.</div>
					{:else}
						<div class="template-grid">
							{#each visibleTemplates as tpl (tpl.id)}
								<button type="button" class="template-card" onclick={() => selectTemplate(tpl)}>
									<div class="tpl-head">
										<strong>{tpl.name}</strong>
										<span>{tpl.kind}</span>
									</div>
									<p>{tpl.description || tpl.image}</p>
									<div class="badges">
										{#if tpl.requires_gpu}<b>GPU</b>{/if}
										{#if tpl.workspace_enabled}<b>{tpl.workspace_kind || 'workspace'}</b>{/if}
										{#if tpl.category === 'ml'}<b>ML</b>{/if}
									</div>
								</button>
							{/each}
						</div>
					{/if}
				{:else}
					<div class="two-col">
						<section>
							<h3>1. 실행 대상</h3>
							{#if selectedTemplate.kind === 'simple' && selectedTemplate.image_options?.length > 0}
								<label class="field">
									<span>이미지</span>
									<select bind:value={selectedImage}>
										{#each selectedTemplate.image_options as option}
											<option value={option.image}>{option.label}</option>
										{/each}
									</select>
								</label>
							{/if}
							<label class="field">
								<span>컨테이너 이름</span>
								<input bind:value={customName} placeholder="비워두면 자동 생성" />
							</label>
							<label class="field">
								<span>배치 서버 *</span>
								<select bind:value={selectedAgent}>
									<option value="" disabled>서버 선택</option>
									{#each agents as agent (agent.id)}
										<option value={agent.id}>{agent.hostname} ({agent.ip_address})</option>
									{/each}
								</select>
							</label>
							<label class="field">
								<span>최대 실행 시간</span>
								<input
									type="number"
									min="1"
									bind:value={requestedMaxRuntimeHours}
									placeholder="템플릿 기본값"
								/>
							</label>
						</section>

						<section>
							<h3>2. GPU</h3>
							{#if selectedTemplate.requires_gpu}
								{#if !selectedAgent}
									<div class="empty compact">먼저 배치 서버를 선택하세요.</div>
								{:else if gpuLoading}
									<div class="empty compact">GPU 정보를 불러오는 중입니다.</div>
								{:else if gpuSlices.length === 0}
									<div class="empty compact">선택한 서버에 사용 가능한 GPU slice가 없습니다.</div>
								{:else}
									<div class="slice-list">
										{#each gpuSlices as slice (slice.id)}
											<button
												type="button"
												class="slice-tile"
												class:selected={selectedGpuSliceIds.includes(slice.id)}
												disabled={slice.status !== 'available'}
												onclick={() => selectGpuSlice(slice.id)}
											>
												<span>
													<strong>{slice.label || slice.gpuName || slice.device_id}</strong>
													<em>GPU {slice.gpuIndex ?? 0} · {sliceModeLabel(slice)} · {formatMb(slice.memory_mb)}</em>
												</span>
												<div class="slice-badges">
													<b>{slice.status}</b>
													{#if slice.allow_shared}<b class="share-badge">shareable</b>{/if}
												</div>
											</button>
										{/each}
									</div>
									{#if selectedGpuCanShare}
										<label class="share-opt-in">
											<input type="checkbox" bind:checked={gpuShareOk} />
											<span>
												<strong>Request shared GPU</strong>
												<em>Experimental: backend policy must enable shared mode and memory accounting first.</em>
											</span>
										</label>
									{:else if selectedGpuSlice}
										<div class="policy-note">
											Selected slice will be reserved exclusively. Shared GPU is allowed only when both the slice and backend policy opt in.
										</div>
									{/if}
								{/if}
							{:else}
								<div class="empty compact">이 템플릿은 GPU 없이 요청할 수 있습니다.</div>
							{/if}
						</section>
					</div>

					<section>
						<h3>3. 모델 자산</h3>
						{#if modelVersions.length === 0}
							<div class="empty compact">등록된 모델 버전이 없습니다.</div>
						{:else}
							<div class="model-list">
								{#each modelVersions as version (version.id)}
									<button
										type="button"
										class="model-row"
										class:selected={selectedModelVersionIds.includes(version.id)}
										onclick={() => toggleModel(version.id)}
									>
										<span>
											<strong>{version.asset_name}</strong>
											<em>{version.version} · {formatBytes(version.size_bytes)}</em>
										</span>
										<b data-status={cacheStatuses[version.id]?.status ?? 'missing'}>{cacheLabel(version.id)}</b>
									</button>
								{/each}
							</div>
							{#if cacheLoading}
								<p class="micro">선택한 서버의 모델 캐시 상태를 확인하는 중입니다.</p>
							{/if}
						{/if}
					</section>

					{#if selectedTemplate.env_schema?.length > 0 || selectedTemplate.port_schema?.length > 0}
						<section>
							<h3>4. 환경/포트</h3>
							<div class="two-col">
								<div class="stack">
									{#each selectedTemplate.env_schema ?? [] as env}
										<label class="field">
											<span>{env.key}{env.required ? ' *' : ''}</span>
											<input
												type={env.type === 'password' ? 'password' : 'text'}
												value={envValues[env.key] ?? ''}
												oninput={(event) => {
													envValues[env.key] = event.currentTarget.value;
													envValues = envValues;
												}}
											/>
										</label>
									{/each}
								</div>
								<div class="stack">
									{#each selectedTemplate.port_schema ?? [] as port}
										<label class="field">
											<span>{port.description || `Port ${port.internal}`}</span>
											<input
												type="number"
												min="1"
												max="65535"
												value={portValues[port.internal] ?? port.host_default}
												oninput={(event) => {
													portValues[port.internal] = Number(event.currentTarget.value);
													portValues = portValues;
												}}
											/>
										</label>
									{/each}
								</div>
							</div>
						</section>
					{/if}
				{/if}
			</div>

			<footer class="modal-footer">
				{#if errorMsg}<div class="error">{errorMsg}</div>{/if}
				{#if selectedTemplate}
					<button type="button" class="secondary" onclick={() => (selectedTemplate = null)}>템플릿 다시 선택</button>
					<button type="button" class="primary" disabled={!canSubmit} onclick={submit}>
						{busy ? '제출 중...' : '요청 제출'}
					</button>
				{/if}
			</footer>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 200;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(0, 0, 0, 0.62);
		backdrop-filter: blur(4px);
	}

	.modal {
		width: min(980px, 94vw);
		max-height: 90vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-card);
		box-shadow: 0 22px 60px rgba(0, 0, 0, 0.36);
	}

	.modal-header,
	.modal-footer,
	.tpl-head,
	.tabs,
	.model-row,
	.slice-tile {
		display: flex;
		align-items: center;
	}

	.modal-header,
	.modal-footer {
		justify-content: space-between;
		gap: 12px;
		padding: 14px 18px;
		border-bottom: 1px solid var(--border);
	}

	.modal-footer {
		border-top: 1px solid var(--border);
		border-bottom: none;
		justify-content: flex-end;
	}

	.modal-header p,
	h2,
	h3,
	.template-card p,
	.micro {
		margin: 0;
	}

	.modal-header p {
		color: var(--accent);
		font-size: 11px;
		font-weight: 900;
		letter-spacing: 0;
	}

	h2 {
		font-size: 18px;
		color: var(--text-primary);
	}

	h3 {
		margin-bottom: 10px;
		font-size: 13px;
		color: var(--text-secondary);
	}

	.modal-content {
		flex: 1;
		overflow: auto;
		padding: 16px 18px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.tabs {
		gap: 6px;
		padding: 3px;
		width: fit-content;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
	}

	.tabs button,
	.secondary,
	.primary,
	.icon-btn,
	.template-card,
	.slice-tile,
	.model-row {
		font-family: inherit;
		cursor: pointer;
	}

	.tabs button,
	.secondary,
	.icon-btn {
		border: 1px solid transparent;
		border-radius: 7px;
		background: transparent;
		color: var(--text-secondary);
	}

	.tabs button {
		min-height: 30px;
		padding: 0 10px;
		font-weight: 800;
	}

	.tabs button.active {
		background: rgba(48, 213, 200, 0.16);
		color: var(--accent);
	}

	.template-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 10px;
	}

	.template-card,
	.slice-tile,
	.model-row,
	.empty,
	.error {
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
	}

	.template-card {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 120px;
		padding: 12px;
		text-align: left;
		color: var(--text-primary);
	}

	.template-card:hover,
	.slice-tile:hover:not(:disabled),
	.model-row:hover {
		border-color: var(--accent);
	}

	.tpl-head {
		justify-content: space-between;
		gap: 10px;
	}

	.tpl-head strong {
		font-size: 14px;
	}

	.tpl-head span,
	.template-card p,
	.micro {
		color: var(--text-muted);
		font-size: 11px;
	}

	.badges {
		display: flex;
		flex-wrap: wrap;
		gap: 5px;
		margin-top: auto;
	}

	.badges b,
	.model-row b,
	.slice-tile b {
		min-height: 22px;
		padding: 3px 7px;
		border-radius: 6px;
		background: rgba(48, 213, 200, 0.14);
		color: var(--accent);
		font-size: 10px;
		font-weight: 900;
		white-space: nowrap;
	}

	.slice-tile b.share-badge {
		background: rgba(251, 191, 36, 0.14);
		color: #fbbf24;
	}

	.two-col {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
	}

	.stack,
	.slice-list,
	.model-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 5px;
		margin-bottom: 10px;
	}

	.field span {
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 800;
	}

	input,
	select {
		min-height: 36px;
		padding: 0 10px;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
		color: var(--text-primary);
		font: inherit;
	}

	input:focus,
	select:focus {
		outline: none;
		border-color: var(--accent);
	}

	.slice-tile {
		justify-content: space-between;
		gap: 12px;
		padding: 10px;
		text-align: left;
		color: var(--text-primary);
	}

	.slice-badges {
		display: flex;
		flex-shrink: 0;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 5px;
	}

	.slice-tile span,
	.model-row span {
		display: flex;
		min-width: 0;
		flex-direction: column;
		gap: 3px;
	}

	.slice-tile em,
	.model-row em {
		color: var(--text-muted);
		font-size: 11px;
		font-style: normal;
	}

	.slice-tile.selected,
	.model-row.selected {
		border-color: var(--accent);
		background: rgba(48, 213, 200, 0.1);
	}

	.slice-tile:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.share-opt-in,
	.policy-note {
		border: 1px solid rgba(251, 191, 36, 0.28);
		border-radius: 8px;
		background: rgba(251, 191, 36, 0.08);
		color: var(--text-secondary);
	}

	.share-opt-in {
		display: flex;
		align-items: flex-start;
		gap: 9px;
		padding: 10px;
		font-size: 12px;
		cursor: pointer;
	}

	.share-opt-in input {
		width: 16px;
		min-height: 16px;
		margin-top: 2px;
		padding: 0;
		border: 0;
		accent-color: #fbbf24;
	}

	.share-opt-in span {
		display: flex;
		min-width: 0;
		flex-direction: column;
		gap: 2px;
	}

	.share-opt-in strong {
		color: var(--text-primary);
		font-size: 12px;
	}

	.share-opt-in em {
		color: var(--text-muted);
		font-size: 11px;
		font-style: normal;
		line-height: 1.35;
	}

	.policy-note {
		padding: 9px 10px;
		font-size: 11px;
		line-height: 1.4;
	}

	.model-row {
		justify-content: space-between;
		gap: 10px;
		padding: 10px 12px;
		text-align: left;
		color: var(--text-primary);
	}

	.slice-tile strong,
	.slice-tile em,
	.model-row strong,
	.model-row em {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.model-row b[data-status='missing'] {
		background: rgba(251, 191, 36, 0.14);
		color: #fbbf24;
	}

	.model-row b[data-status='failed'] {
		background: rgba(239, 68, 68, 0.14);
		color: var(--error);
	}

	.empty,
	.error {
		padding: 12px;
		color: var(--text-secondary);
		font-size: 12px;
	}

	.empty.compact {
		padding: 10px;
	}

	.error {
		margin-right: auto;
		color: var(--error);
	}

	.primary,
	.secondary {
		min-height: 36px;
		padding: 0 14px;
		font-weight: 900;
	}

	.primary {
		border: none;
		border-radius: 8px;
		background: var(--accent);
		color: var(--bg-base);
	}

	.secondary {
		border-color: var(--border);
		background: var(--bg-base);
		color: var(--text-primary);
	}

	.icon-btn {
		width: 32px;
		height: 32px;
		border-color: var(--border);
		background: var(--bg-base);
		color: var(--text-secondary);
		font-weight: 900;
	}

	button:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	@media (max-width: 760px) {
		.two-col,
		.template-grid {
			grid-template-columns: 1fr;
		}

		.modal-footer {
			flex-wrap: wrap;
		}
	}
</style>
