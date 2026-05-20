<script lang="ts">
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import ResourceLimitForm from './ResourceLimitForm.svelte';

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
		default_model_version_ids?: string[];
		description: string;
		requires_gpu?: boolean;
		workspace_enabled?: boolean;
		workspace_kind?: string;
		default_max_runtime_hours?: number | null;
		min_cpu_percent?: number;
		min_memory_mb?: number;
		min_workspace_gb?: number;
		data_mount_path?: string;
	};

	type Agent = {
		id: string;
		hostname: string;
		ip_address: string;
		is_active: boolean;
		cpu_cores?: number | null;
		ram_total_mb?: number | null;
		workspace_pool_total_gb?: number | null;
		workspace_pool_free_gb?: number | null;
		workspace_hard_enforcement?: boolean;
		target_users?: number;
		safety_margin?: number;
	};

	type ResourceRecommendation = {
		cpu_percent: number;
		memory_mb: number;
		workspace_gb: number;
		capacity_complete?: boolean;
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
	let cpuPercent = $state(100);
	let memoryMb = $state(2048);
	let workspaceGb = $state(10);
	let useResourceRecommendation = $state(true);
	let resourceRecommendation = $state<ResourceRecommendation | null>(null);
	let resourceLoading = $state(false);
	let templateSearch = $state('');
	type TemplateScope = 'all' | 'with-model';
	let templateScope = $state<TemplateScope>('all');
	let busy = $state(false);
	let loading = $state(false);
	let gpuLoading = $state(false);
	let cacheLoading = $state(false);
	let errorMsg = $state('');
	let lastGpuAgent = '';
	let lastCacheKey = '';
	let lastRecommendationKey = '';

	let visibleTemplates = $derived.by(() => {
		const q = templateSearch.trim().toLowerCase();
		return templates.filter((tpl) => {
			if (templateScope === 'with-model' && !(tpl.default_model_version_ids?.length)) return false;
			if (!q) return true;
			const hay = `${tpl.name} ${tpl.description ?? ''} ${tpl.image ?? ''}`.toLowerCase();
			return hay.includes(q);
		});
	});

	let withModelCount = $derived(
		templates.filter((tpl) => (tpl.default_model_version_ids?.length ?? 0) > 0).length,
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
	let selectedAgentInfo = $derived(agents.find((agent) => agent.id === selectedAgent) ?? null);
	let resourceLimitsValid = $derived(
		!selectedTemplate ||
			(cpuPercent >= (selectedTemplate.min_cpu_percent ?? 100) &&
				memoryMb >= (selectedTemplate.min_memory_mb ?? 2048) &&
				workspaceGb >= (selectedTemplate.min_workspace_gb ?? 10)),
	);

	let canSubmit = $derived(
		!!selectedTemplate &&
			!!selectedAgent &&
			resourceLimitsValid &&
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

	$effect(() => {
		const key = `${selectedTemplate?.id ?? ''}:${selectedAgent}`;
		if (!open || !selectedTemplate || !selectedAgent || key === lastRecommendationKey) return;
		lastRecommendationKey = key;
		loadResourceRecommendation(selectedTemplate.id, selectedAgent);
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
		cpuPercent = 100;
		memoryMb = 2048;
		workspaceGb = 10;
		useResourceRecommendation = true;
		resourceRecommendation = null;
		templateSearch = '';
		templateScope = 'all';
		gpuDevices = [];
		cacheStatuses = {};
		errorMsg = '';
		lastGpuAgent = '';
		lastCacheKey = '';
		lastRecommendationKey = '';
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
			// preserve the user's filter; we no longer auto-flip to General.
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

	async function loadResourceRecommendation(templateId: string, agentId: string) {
		const t = token();
		if (!t) return;
		resourceLoading = true;
		try {
			const res = await fetch(`${base}/api/containers/recommend/?template=${templateId}&agent=${agentId}`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(humanizeError(json, `자원 추천값 요청 실패 (${res.status})`));
			const data = json.data ?? {};
			resourceRecommendation = {
				cpu_percent: Number(data.cpu_percent ?? selectedTemplate?.min_cpu_percent ?? 100),
				memory_mb: Number(data.memory_mb ?? selectedTemplate?.min_memory_mb ?? 2048),
				workspace_gb: Number(data.workspace_gb ?? selectedTemplate?.min_workspace_gb ?? 10),
				capacity_complete: Boolean(data.capacity_complete),
			};
			if (useResourceRecommendation) {
				cpuPercent = resourceRecommendation.cpu_percent;
				memoryMb = resourceRecommendation.memory_mb;
				workspaceGb = resourceRecommendation.workspace_gb;
			}
		} catch (error: any) {
			errorMsg = error?.message || '자원 추천값을 불러오지 못했습니다.';
			applyTemplateMinimums();
		} finally {
			resourceLoading = false;
		}
	}

	function bundledModelLabels(tpl: Template): string[] {
		const ids = tpl.default_model_version_ids ?? [];
		if (ids.length === 0) return [];
		return ids
			.map((id) => {
				const v = modelVersions.find((mv) => mv.id === id);
				return v ? `${v.asset_name} ${v.version}` : '';
			})
			.filter((s) => !!s);
	}

	function selectTemplate(tpl: Template) {
		selectedTemplate = tpl;
		selectedImage = tpl.image || (tpl.image_options?.[0]?.image ?? '');
		requestedMaxRuntimeHours = tpl.default_max_runtime_hours ?? null;
		useResourceRecommendation = true;
		resourceRecommendation = null;
		applyTemplateMinimums(tpl);
		lastRecommendationKey = '';
		envValues = {};
		portValues = {};
		selectedGpuSliceIds = [];
		gpuShareOk = false;
		selectedModelVersionIds = (tpl.default_model_version_ids ?? [])
			.map((id) => String(id))
			.filter((id) => modelVersions.some((version) => version.id === id));
		for (const env of tpl.env_schema ?? []) envValues[env.key] = env.default ?? '';
		for (const port of tpl.port_schema ?? []) portValues[port.internal] = port.host_default ?? port.internal;
	}

	function applyTemplateMinimums(tpl = selectedTemplate) {
		cpuPercent = tpl?.min_cpu_percent ?? 100;
		memoryMb = tpl?.min_memory_mb ?? 2048;
		workspaceGb = tpl?.min_workspace_gb ?? 10;
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
			cpu_percent: cpuPercent,
			memory_mb: memoryMb,
			workspace_gb: workspaceGb,
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
					<div class="tpl-toolbar">
						<input
							class="tpl-search"
							type="search"
							bind:value={templateSearch}
							placeholder="템플릿 검색 (이름 · 설명 · 이미지)"
						/>
						<div class="tpl-segmented" role="radiogroup" aria-label="범위">
							<button type="button" class:active={templateScope === 'all'} onclick={() => (templateScope = 'all')} aria-pressed={templateScope === 'all'}>전체 <span class="cnt">{templates.length}</span></button>
							<button type="button" class:active={templateScope === 'with-model'} onclick={() => (templateScope = 'with-model')} aria-pressed={templateScope === 'with-model'}>모델 <span class="cnt">{withModelCount}</span></button>
						</div>
					</div>

					{#if loading}
						<div class="empty">템플릿을 불러오는 중입니다.</div>
					{:else if visibleTemplates.length === 0}
						<div class="empty">선택 가능한 템플릿이 없습니다.</div>
					{:else}
						<div class="tpl-table-wrap">
							<table class="tpl-table">
								<thead>
									<tr>
										<th>이름</th>
										<th class="col-meta">유형</th>
										<th>이미지 / 포함 모델</th>
										<th class="col-meta">자원</th>
										<th class="col-pick"></th>
									</tr>
								</thead>
								<tbody>
									{#each visibleTemplates as tpl (tpl.id)}
										{@const bundled = bundledModelLabels(tpl)}
										<tr class="tpl-row" onclick={() => selectTemplate(tpl)} title={tpl.description || tpl.image}>
											<td><strong>{tpl.name}</strong></td>
											<td class="col-meta">{tpl.kind}{#if tpl.category === 'ml'} · ML{/if}</td>
											<td class="col-archs">
												{#if bundled.length > 0}
													<code title={bundled.join(', ')}>{bundled.slice(0, 2).join(' · ')}{bundled.length > 2 ? ` +${bundled.length - 2}` : ''}</code>
												{:else}
													<code class="muted">{tpl.image || '—'}</code>
												{/if}
											</td>
											<td class="col-meta">
												{tpl.requires_gpu ? 'GPU' : 'CPU'} · {tpl.workspace_kind || '—'}
											</td>
											<td class="col-pick"><span class="tpl-pick">선택 →</span></td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				{:else}
					<table class="cfg-table">
						<tbody>
							{#if selectedTemplate?.kind === 'simple' && (selectedTemplate?.image_options?.length ?? 0) > 0}
								<tr>
									<th>이미지</th>
									<td>
										<select bind:value={selectedImage}>
											{#each selectedTemplate?.image_options ?? [] as option}
												<option value={option.image}>{option.label}</option>
											{/each}
										</select>
									</td>
								</tr>
							{/if}
							<tr>
								<th>컨테이너 이름</th>
								<td><input bind:value={customName} placeholder="비워두면 자동 생성" /></td>
							</tr>
							<tr>
								<th>배치 서버 <em class="req">*</em></th>
								<td>
									<select bind:value={selectedAgent}>
										<option value="" disabled>서버 선택</option>
										{#each agents as agent (agent.id)}
											<option value={agent.id}>{agent.hostname} ({agent.ip_address})</option>
										{/each}
									</select>
								</td>
							</tr>
							<tr>
								<th>최대 실행 시간</th>
								<td>
									<input
										type="number"
										min="1"
										bind:value={requestedMaxRuntimeHours}
										placeholder="템플릿 기본값"
									/>
									<span class="cfg-hint">시간 단위. 비우면 템플릿 기본값.</span>
								</td>
							</tr>
							<tr>
								<th>GPU</th>
								<td>
									{#if !selectedTemplate?.requires_gpu}
										<span class="cfg-muted">이 템플릿은 GPU 없이 요청할 수 있습니다.</span>
									{:else if !selectedAgent}
										<span class="cfg-muted">먼저 배치 서버를 선택하세요.</span>
									{:else if gpuLoading}
										<span class="cfg-muted">GPU 정보를 불러오는 중…</span>
									{:else if gpuSlices.length === 0}
										<span class="cfg-muted">선택한 서버에 사용 가능한 GPU slice가 없습니다.</span>
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
								</td>
							</tr>
							<tr>
								<th>자원 limits</th>
								<td>
									<ResourceLimitForm
										bind:cpuPercent
										bind:memoryMb
										bind:workspaceGb
										bind:useRecommendation={useResourceRecommendation}
										recommendedCpuPercent={resourceRecommendation?.cpu_percent ?? selectedTemplate?.min_cpu_percent ?? 100}
										recommendedMemoryMb={resourceRecommendation?.memory_mb ?? selectedTemplate?.min_memory_mb ?? 2048}
										recommendedWorkspaceGb={resourceRecommendation?.workspace_gb ?? selectedTemplate?.min_workspace_gb ?? 10}
										minCpuPercent={selectedTemplate?.min_cpu_percent ?? 100}
										minMemoryMb={selectedTemplate?.min_memory_mb ?? 2048}
										minWorkspaceGb={selectedTemplate?.min_workspace_gb ?? 10}
										hostCpuCores={selectedAgentInfo?.cpu_cores ?? null}
										hostMemoryMb={selectedAgentInfo?.ram_total_mb ?? null}
										hostWorkspacePoolGb={selectedAgentInfo?.workspace_pool_total_gb ?? null}
										hostWorkspacePoolFreeGb={selectedAgentInfo?.workspace_pool_free_gb ?? null}
										hostWorkspaceHardEnforcement={selectedAgentInfo?.workspace_hard_enforcement ?? false}
										diskMountPath={selectedTemplate?.data_mount_path ?? '/workspace'}
										loading={resourceLoading}
									/>
								</td>
							</tr>
							<tr>
								<th>모델 자산</th>
								<td>
									{#if modelVersions.length === 0}
										<span class="cfg-muted">등록된 모델 버전이 없습니다.</span>
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
											<p class="cfg-hint">선택한 서버의 모델 캐시 상태를 확인하는 중입니다.</p>
										{/if}
									{/if}
								</td>
							</tr>
							{#each selectedTemplate?.env_schema ?? [] as env}
								<tr>
									<th>env: <code>{env.key}</code>{env.required ? ' *' : ''}</th>
									<td>
										<input
											type={env.type === 'password' ? 'password' : 'text'}
											value={envValues[env.key] ?? ''}
											oninput={(event) => {
												envValues[env.key] = event.currentTarget.value;
												envValues = envValues;
											}}
										/>
									</td>
								</tr>
							{/each}
							{#each selectedTemplate?.port_schema ?? [] as port}
								<tr>
									<th>port: <code>{port.internal}</code></th>
									<td>
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
										{#if port.description}<span class="cfg-hint">{port.description}</span>{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
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
		height: min(720px, 90vh);
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

	.cfg-table {
		width: 100%;
		border-collapse: separate;
		border-spacing: 0;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
		overflow: hidden;
	}

	.cfg-table th {
		padding: 10px 12px;
		text-align: left;
		vertical-align: top;
		width: 160px;
		min-width: 140px;
		font-size: 11.5px;
		font-weight: 800;
		letter-spacing: 0.02em;
		color: var(--text-muted);
		background: rgba(13, 17, 23, 0.4);
		border-bottom: 1px solid var(--border);
		text-transform: uppercase;
		white-space: nowrap;
	}

	.cfg-table td {
		padding: 10px 12px;
		border-bottom: 1px solid var(--border);
		vertical-align: top;
	}

	.cfg-table tr:last-child th,
	.cfg-table tr:last-child td {
		border-bottom: none;
	}

	.cfg-table input,
	.cfg-table select {
		width: 100%;
		font: inherit;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--bg-base);
		color: var(--text-primary);
		padding: 6px 9px;
	}

	.cfg-table input:focus,
	.cfg-table select:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 2px rgba(77, 191, 179, 0.18);
	}

	.cfg-hint {
		display: block;
		margin-top: 4px;
		color: var(--text-muted);
		font-size: 11px;
	}

	.cfg-muted {
		color: var(--text-muted);
		font-size: 12px;
	}

	.cfg-table .req {
		color: var(--accent);
		font-style: normal;
		font-weight: 900;
	}

	.cfg-table th code {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 11px;
		padding: 1px 4px;
		background: rgba(100, 116, 139, 0.18);
		border-radius: 3px;
		color: var(--text-primary);
		text-transform: none;
		font-weight: 700;
	}

	.tpl-toolbar {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 10px;
	}

	.tpl-search {
		flex: 1;
		min-width: 0;
		font: inherit;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
		color: var(--text-primary);
		padding: 8px 12px;
	}

	.tpl-search:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 3px rgba(77, 191, 179, 0.18);
	}

	.tpl-segmented {
		display: inline-flex;
		flex-shrink: 0;
		border: 1px solid var(--border);
		border-radius: 6px;
		overflow: hidden;
		background: var(--bg-base);
	}

	.tpl-segmented button {
		padding: 6px 12px;
		font: inherit;
		font-size: 11.5px;
		font-weight: 700;
		color: var(--text-muted);
		background: transparent;
		border: none;
		border-right: 1px solid var(--border);
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}

	.tpl-segmented button:last-child {
		border-right: none;
	}

	.tpl-segmented button:hover {
		color: var(--text-primary);
		background: rgba(77, 191, 179, 0.05);
	}

	.tpl-segmented button.active {
		color: var(--accent);
		background: rgba(77, 191, 179, 0.14);
	}

	.tpl-segmented .cnt {
		padding: 1px 5px;
		font-size: 10px;
		color: var(--text-muted);
		background: rgba(100, 116, 139, 0.18);
		border-radius: 3px;
	}

	.tpl-segmented button.active .cnt {
		color: var(--accent);
		background: rgba(77, 191, 179, 0.20);
	}

	.tpl-flag-group {
		display: inline-flex;
		gap: 6px;
		flex-shrink: 0;
	}

	.tpl-flag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 5px 10px;
		font-size: 11.5px;
		font-weight: 700;
		color: var(--text-muted);
		background: transparent;
		border: 1px solid var(--border);
		border-radius: 6px;
		cursor: pointer;
		user-select: none;
	}

	.tpl-flag:hover {
		color: var(--text-primary);
		border-color: rgba(77, 191, 179, 0.4);
	}

	.tpl-flag.active {
		color: var(--accent);
		background: rgba(77, 191, 179, 0.12);
		border-color: var(--accent);
	}

	.tpl-flag input[type='checkbox'] {
		width: 13px;
		height: 13px;
		margin: 0;
		accent-color: var(--accent);
	}

	.tpl-table-wrap {
		border: 1px solid var(--border);
		border-radius: 8px;
		overflow: auto;
		max-height: 460px;
		background: var(--bg-base);
	}

	.tpl-table {
		width: 100%;
		border-collapse: separate;
		border-spacing: 0;
		font-size: 12.5px;
	}

	.tpl-table thead th {
		padding: 6px 10px;
		text-align: left;
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--text-muted);
		border-bottom: 1px solid var(--border);
		background: rgba(13, 17, 23, 0.95);
		position: sticky;
		top: 0;
		z-index: 2;
	}

	.tpl-table tbody td {
		padding: 8px 10px;
		border-bottom: 1px solid var(--border);
		vertical-align: middle;
	}

	.tpl-table tbody tr.tpl-row {
		cursor: pointer;
		transition: background 0.12s;
	}

	.tpl-table tbody tr.tpl-row:hover {
		background: rgba(77, 191, 179, 0.06);
	}

	.tpl-table tbody tr.tpl-row strong {
		font-size: 13px;
		font-weight: 800;
		color: var(--text-primary);
	}

	.tpl-table .col-meta {
		white-space: nowrap;
		color: var(--text-muted);
		font-size: 11.5px;
	}

	.tpl-table .col-archs code {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 11px;
		color: var(--text-primary);
		background: rgba(100, 116, 139, 0.14);
		padding: 1px 5px;
		border-radius: 3px;
	}

	.tpl-table .col-archs code.muted {
		color: var(--text-muted);
	}

	.tpl-table .col-pick {
		width: 64px;
		text-align: right;
		white-space: nowrap;
	}

	.tpl-pick {
		color: var(--accent);
		font-size: 11.5px;
		font-weight: 800;
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
		height: 168px;
		padding: 12px;
		text-align: left;
		color: var(--text-primary);
		overflow: hidden;
	}

	.template-card:hover,
	.slice-tile:hover:not(:disabled),
	.model-row:hover {
		border-color: var(--accent);
	}

	.tpl-head {
		justify-content: space-between;
		gap: 10px;
		flex-wrap: nowrap;
		min-width: 0;
	}

	.tpl-head strong {
		flex: 1 1 auto;
		min-width: 0;
		font-size: 14px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.tpl-head span {
		flex-shrink: 0;
	}

	.template-card p {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.tpl-head span,
	.template-card p,
	.micro {
		color: var(--text-muted);
		font-size: 11px;
	}

	.bundled-models {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 6px 8px;
		border: 1px solid rgba(77, 191, 179, 0.25);
		border-radius: 6px;
		background: rgba(77, 191, 179, 0.06);
		font-size: 11.5px;
		line-height: 1.4;
		min-width: 0;
	}

	.bundled-key {
		flex-shrink: 0;
		color: var(--accent);
		font-weight: 900;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		font-size: 10px;
	}

	.bundled-val {
		color: var(--text-primary);
		font-weight: 700;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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
