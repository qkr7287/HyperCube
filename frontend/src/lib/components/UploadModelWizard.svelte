<script lang="ts">
	import { base } from '$app/paths';
	import { browser } from '$app/environment';
	import { MODEL_PRESETS, type ModelPreset } from '$lib/presets/model-presets';

	type Mode = 'user' | 'admin';

	let {
		open = false,
		mode = 'user' as Mode,
		onClose = () => {},
		onSubmitted = (_result: { requestId?: string; templateId?: string; templateName?: string }) => {
			void _result;
		},
	}: {
		open?: boolean;
		mode?: Mode;
		onClose?: () => void;
		onSubmitted?: (result: { requestId?: string; templateId?: string; templateName?: string }) => void;
	} = $props();

	type Step = 1 | 2 | 3;
	let step = $state<Step>(1);

	let modelName = $state('');
	let description = $state('');
	let version = $state('v1');
	let file = $state<File | null>(null);
	let presetId = $state<string | null>(null);

	let showAdvanced = $state(false);
	let minMemoryMb = $state<number | null>(null);
	let minWorkspaceGb = $state<number | null>(null);
	let workspacePort = $state<number | null>(null);
	let defaultMaxRuntimeHours = $state<number | null>(null);

	let templateName = $state('');

	// Custom preset (사용자가 직접 입력하는 실행 환경)
	const CUSTOM_PRESET_ID = '__custom__';
	let customBaseImage = $state('');
	let customWorkspaceKind = $state<'jupyter' | 'code-server' | 'api'>('jupyter');
	let customWorkspacePort = $state<number | null>(null);
	let customRequiresGpu = $state(true);
	let customPresetExpanded = $state(false);

	// Custom recipe (사용자가 직접 입력하는 추론 레시피)
	const CUSTOM_RECIPE_ID = '__custom__';
	let customModelClass = $state('');
	let customProcessorClass = $state('AutoTokenizer');
	let customAppTemplate = $state<'gradio_text_chat' | 'gradio_vlm_chat' | 'none'>('gradio_text_chat');
	let customTrustRemoteCode = $state(false);
	let customRecipeExpanded = $state(false);

	type LauncherRecipe = {
		id: string;
		label: string;
		description: string;
		input_kinds: string[];
		app_template: string;
		architectures?: string[];
		available?: boolean;
		category?: string;
	};

	const RECIPE_CATEGORY_LABEL: Record<string, string> = {
		chat: '대화 (텍스트 / 멀티모달)',
		image: '이미지 생성',
		audio: '음성',
		embedding: '임베딩 · 검색',
		video: '비디오',
		other: '기타',
	};
	let recipes = $state<LauncherRecipe[]>([]);
	let recipeId = $state<string>('none');
	let recipesError = $state('');

	let busy = $state(false);
	let errorMsg = $state('');
	let uploadPercent = $state(0);
	let uploadBytes = $state(0);
	let uploadTotal = $state(0);
	let uploadPhase = $state<'idle' | 'uploading' | 'finalizing' | 'approving'>('idle');
	let currentXhr: XMLHttpRequest | null = null;
	let userCancelled = $state(false);

	function cancelUpload() {
		if (currentXhr && (uploadPhase === 'uploading' || uploadPhase === 'finalizing')) {
			userCancelled = true;
			currentXhr.abort();
		}
	}

	let selectedPreset = $derived<ModelPreset | null>(
		presetId && presetId !== CUSTOM_PRESET_ID
			? MODEL_PRESETS.find((p) => p.id === presetId) ?? null
			: null,
	);

	let isCustomPreset = $derived(presetId === CUSTOM_PRESET_ID);
	let isCustomRecipe = $derived(recipeId === CUSTOM_RECIPE_ID);

	let step1Valid = $derived(!!modelName.trim() && !!version.trim() && !!file);
	let step2Valid = $derived(
		(!!selectedPreset || (isCustomPreset && !!customBaseImage.trim())) &&
		(!isCustomRecipe || !!customModelClass.trim()),
	);
	let canSubmit = $derived(step1Valid && step2Valid && !busy);

	let effectiveTemplateName = $derived(
		templateName.trim() ||
			(selectedPreset ? `${modelName.trim()} · ${selectedPreset.label}` : ''),
	);

	let effectiveMinMemoryMb = $derived(
		showAdvanced && minMemoryMb && minMemoryMb > 0
			? Math.round(minMemoryMb)
			: selectedPreset?.minMemoryMb ?? 2048,
	);
	let effectiveMinWorkspaceGb = $derived(
		showAdvanced && minWorkspaceGb && minWorkspaceGb > 0
			? Math.round(minWorkspaceGb)
			: selectedPreset?.minWorkspaceGb ?? 10,
	);
	let effectiveWorkspacePort = $derived(
		showAdvanced && workspacePort && workspacePort > 0
			? Math.round(workspacePort)
			: selectedPreset?.workspacePort ?? 8888,
	);
	let effectiveMaxRuntimeHours = $derived(
		showAdvanced && defaultMaxRuntimeHours && defaultMaxRuntimeHours > 0
			? Math.round(defaultMaxRuntimeHours)
			: selectedPreset?.defaultMaxRuntimeHours ?? 24,
	);

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function loadRecipes() {
		const t = token();
		if (!t) return;
		try {
			const res = await fetch(`${base}/api/launcher-recipes/`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
			recipes = (json?.data?.recipes ?? json?.recipes ?? []) as LauncherRecipe[];
			recipesError = '';
		} catch (error: any) {
			recipes = [
				{ id: 'none', label: '자동 실행 안 함', description: '', input_kinds: [], app_template: 'none' },
			];
			recipesError = error?.message || 'recipe 목록을 불러오지 못했습니다.';
		}
	}

	$effect(() => {
		if (open && recipes.length === 0) {
			loadRecipes();
		}
	});

	// Auto-select the first AVAILABLE preset on open so the wizard never blocks
	// on "pick the only option". Preview/disabled presets are not auto-selected.
	$effect(() => {
		if (open && !presetId) {
			const first = MODEL_PRESETS.find((p) => p.available !== false);
			if (first) presetId = first.id;
		}
	});

	let selectedRecipe = $derived<LauncherRecipe | null>(
		recipes.find((r) => r.id === recipeId) ?? null,
	);

	let recipesByCategory = $derived.by<Record<string, LauncherRecipe[]>>(() => {
		const groups: Record<string, LauncherRecipe[]> = {};
		for (const r of recipes) {
			const cat = r.category || 'other';
			(groups[cat] ||= []).push(r);
		}
		return groups;
	});

	let recipeCategoryOrder = $derived(
		(['chat', 'image', 'audio', 'embedding', 'video', 'other'] as const).filter(
			(c) => (recipesByCategory[c] ?? []).length > 0,
		),
	);

	function resetAll() {
		step = 1;
		modelName = '';
		description = '';
		version = 'v1';
		file = null;
		presetId = null;
		showAdvanced = false;
		minMemoryMb = null;
		minWorkspaceGb = null;
		workspacePort = null;
		defaultMaxRuntimeHours = null;
		templateName = '';
		recipeId = 'none';
		errorMsg = '';
	}

	function close() {
		if (busy) return;
		onClose();
		// keep state for accidental close; reset only on success
	}

	function goNext() {
		if (step === 1 && !step1Valid) return;
		if (step === 2 && !step2Valid) return;
		if (step < 3) step = (step + 1) as Step;
	}

	function goBack() {
		if (step > 1) step = (step - 1) as Step;
	}

	function gotoStep(target: Step) {
		// allow jumping back; forward only if prior steps valid
		if (target < step) {
			step = target;
			return;
		}
		if (target === 2 && step1Valid) step = 2;
		else if (target === 3 && step1Valid && step2Valid) step = 3;
	}

	function fileSizeLabel(f: File): string {
		const mb = f.size / 1024 / 1024;
		if (mb >= 1) return `${mb.toFixed(2)} MB`;
		return `${(f.size / 1024).toFixed(1)} KB`;
	}

	function slugify(name: string): string {
		return name
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-|-$/g, '')
			.slice(0, 60);
	}

	async function submitRequest(): Promise<string | null> {
		const t = token();
		if (!t || !file) return null;
		if (!selectedPreset && !isCustomPreset) return null;
		const form = new FormData();
		form.append('name', modelName.trim());
		form.append('slug', slugify(modelName));
		form.append('version', version.trim());
		const baseImage = isCustomPreset ? customBaseImage.trim() : selectedPreset!.baseImage;
		const wsKind = isCustomPreset ? customWorkspaceKind : selectedPreset!.workspaceKind;
		const wsPort = isCustomPreset
			? (customWorkspacePort && customWorkspacePort > 0 ? customWorkspacePort : 8888)
			: effectiveWorkspacePort;
		const requiresGpu = isCustomPreset ? customRequiresGpu : selectedPreset!.requiresGpu;
		form.append('framework', selectedPreset?.framework || 'custom');
		form.append('task', selectedPreset?.task || 'general');
		form.append('description', description.trim());
		form.append('template_name', effectiveTemplateName);
		form.append('template_description', description.trim() || effectiveTemplateName);
		form.append('base_image', baseImage);
		form.append('requires_gpu', String(requiresGpu));
		form.append('workspace_kind', wsKind);
		form.append('workspace_port', String(wsPort));
		form.append('default_max_runtime_hours', String(effectiveMaxRuntimeHours));
		form.append('min_cpu_percent', String(selectedPreset?.minCpuPercent ?? 100));
		form.append('min_memory_mb', String(effectiveMinMemoryMb));
		form.append('min_workspace_gb', String(effectiveMinWorkspaceGb));
		form.append('launcher_recipe_id', recipeId || 'none');
		if (isCustomRecipe) {
			form.append('launcher_overrides', JSON.stringify({
				model_class: customModelClass.trim(),
				processor_class: customProcessorClass.trim(),
				app_template: customAppTemplate,
				trust_remote_code: customTrustRemoteCode,
			}));
		}
		form.append('file', file);

		uploadTotal = file.size;
		uploadBytes = 0;
		uploadPercent = 0;
		uploadPhase = 'uploading';
		userCancelled = false;
		return await new Promise<string | null>((resolve, reject) => {
			const xhr = new XMLHttpRequest();
			currentXhr = xhr;
			xhr.open('POST', `${base}/api/model-upload-requests/`);
			xhr.setRequestHeader('Authorization', `Bearer ${t}`);
			xhr.upload.onprogress = (e) => {
				if (e.lengthComputable) {
					uploadBytes = e.loaded;
					uploadTotal = e.total;
					uploadPercent = Math.min(100, Math.round((e.loaded / e.total) * 100));
					if (e.loaded >= e.total) uploadPhase = 'finalizing';
				}
			};
			xhr.upload.onload = () => { uploadPhase = 'finalizing'; };
			xhr.onload = () => {
				currentXhr = null;
				let json: any = {};
				try { json = JSON.parse(xhr.responseText); } catch { /* keep empty */ }
				if (xhr.status >= 200 && xhr.status < 300) {
					resolve(json?.data?.id ?? null);
				} else {
					reject(new Error(json?.detail || json?.error?.detail || `HTTP ${xhr.status}`));
				}
			};
			xhr.onerror = () => { currentXhr = null; reject(new Error('네트워크 오류로 업로드에 실패했습니다.')); };
			xhr.onabort = () => {
				currentXhr = null;
				reject(new Error(userCancelled ? '사용자가 업로드를 취소했습니다.' : '업로드가 중단되었습니다.'));
			};
			xhr.send(form);
		});
	}

	async function approveAsAdmin(requestId: string) {
		const t = token();
		if (!t) return null;
		const res = await fetch(`${base}/api/model-upload-requests/${requestId}/approve/`, {
			method: 'POST',
			headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' },
			body: JSON.stringify({ note: 'admin direct register via wizard' }),
		});
		const json = await res.json().catch(() => ({}));
		if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
		return json?.data ?? null;
	}

	async function submit() {
		if (!canSubmit) return;
		busy = true;
		errorMsg = '';
		try {
			const requestId = await submitRequest();
			if (!requestId) throw new Error('업로드 요청을 만들지 못했습니다.');
			if (mode === 'admin') {
				uploadPhase = 'approving';
				const approved = await approveAsAdmin(requestId);
				onSubmitted({
					requestId,
					templateId: approved?.created_template ?? undefined,
					templateName: approved?.created_template_name ?? effectiveTemplateName,
				});
			} else {
				onSubmitted({ requestId });
			}
			resetAll();
			onClose();
		} catch (error: any) {
			errorMsg = userCancelled ? '업로드를 취소했습니다.' : (error?.message || '제출에 실패했습니다.');
		} finally {
			uploadPhase = 'idle';
			uploadPercent = 0;
			uploadBytes = 0;
			uploadTotal = 0;
			userCancelled = false;
			currentXhr = null;
			busy = false;
		}
	}

	const STEPS: { n: Step; label: string; hint: string }[] = [
		{ n: 1, label: '모델 정보', hint: '이름과 파일' },
		{ n: 2, label: '실행 환경', hint: '용도에 맞는 preset 선택' },
		{ n: 3, label: '확인 · 제출', hint: '내용 확인 후 제출' },
	];
</script>

{#if open}
	<div class="overlay" onclick={close} role="dialog" aria-modal="true">
		<div class="modal" onclick={(e) => e.stopPropagation()}>
			{#if busy && uploadPhase !== 'idle'}
				<div class="upload-overlay" role="status" aria-live="polite">
					<div class="upload-card">
						<h3>
							{#if uploadPhase === 'uploading'}
								업로드 중…
							{:else if uploadPhase === 'finalizing'}
								서버 처리 중…
							{:else if uploadPhase === 'approving'}
								자동 승인 중…
							{/if}
						</h3>
						<p class="upload-file">{file?.name ?? ''}</p>
						{#if uploadPhase === 'uploading' && uploadTotal > 0}
							<div class="upload-bar">
								<div class="upload-bar-fill" style="width: {uploadPercent}%"></div>
							</div>
							<p class="upload-meta">
								{uploadPercent}% · {(uploadBytes / 1024 / 1024).toFixed(1)} / {(uploadTotal / 1024 / 1024).toFixed(1)} MB
							</p>
						{:else}
							<div class="upload-spinner"></div>
							<p class="upload-meta">
								{#if uploadPhase === 'finalizing'}
									sha256 계산 + 저장 중. 잠시만요.
								{:else if uploadPhase === 'approving'}
									ContainerTemplate 생성 중.
								{:else}
									진행 중…
								{/if}
							</p>
						{/if}
						<div class="upload-actions">
							<button
								type="button"
								class="upload-cancel"
								onclick={cancelUpload}
								disabled={uploadPhase !== 'uploading'}
								title={uploadPhase !== 'uploading' ? '서버 처리 단계는 취소할 수 없습니다' : '업로드 중단'}
							>
								취소
							</button>
						</div>
					</div>
				</div>
			{/if}

			<header class="modal-head">
				<div class="modal-head-text">
					<p class="kicker">{mode === 'admin' ? 'Admin · Template Register' : 'Model Upload Request'}</p>
					<h2>{mode === 'admin' ? '템플릿 등록' : '모델 등록 요청'}</h2>
					<p class="subtitle">
						{mode === 'admin'
							? '모델 파일과 실행 환경 preset을 골라 즉시 등록합니다.'
							: '모델 파일과 실행 환경 preset을 골라 요청을 보냅니다. 관리자가 검토 후 템플릿으로 등록합니다.'}
					</p>
				</div>
				<button class="icon-btn" onclick={close} aria-label="닫기">×</button>
			</header>

			<div class="body">
				<aside class="stepper" aria-label="진행 단계">
					{#each STEPS as s}
						{@const isActive = step === s.n}
						{@const isDone = step > s.n}
						{@const isReachable =
							s.n === 1 || (s.n === 2 && step1Valid) || (s.n === 3 && step1Valid && step2Valid)}
						<button
							type="button"
							class="step"
							class:active={isActive}
							class:done={isDone}
							class:reachable={isReachable && !isActive}
							disabled={!isReachable}
							onclick={() => gotoStep(s.n)}
						>
							<span class="step-num" aria-hidden="true">
								{#if isDone}
									<svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 11 8 15 16 6" /></svg>
								{:else}
									{s.n}
								{/if}
							</span>
							<span class="step-text">
								<strong>{s.label}</strong>
								<em>{s.hint}</em>
							</span>
						</button>
					{/each}
				</aside>

				<section class="content">
					{#if step === 1}
						<div class="step-pane">
							<header class="pane-head">
								<h3>1. 모델 정보</h3>
								<p>이 모델을 식별할 정보와 파일을 올려주세요.</p>
							</header>
							<div class="grid">
								<label class="field">
									<span class="label">모델 이름 <em class="req">*</em></span>
									<input bind:value={modelName} placeholder="예: Tiny Vision Classifier" />
									<span class="hint">팀이 보고 알아볼 수 있는 이름이면 충분합니다.</span>
								</label>
								<label class="field">
									<span class="label">버전 <em class="req">*</em></span>
									<input bind:value={version} placeholder="v1" />
									<span class="hint">같은 모델을 여러 번 올리면 v2, v3… 로 구분합니다.</span>
								</label>
							</div>
							<label class="field">
								<span class="label">간단한 설명</span>
								<textarea bind:value={description} rows="3" placeholder="이 모델이 무엇을 하는지, 어떻게 쓰는지 한두 줄로 적어주세요."></textarea>
							</label>
							<div class="upload-zone" class:has-file={!!file}>
								<input
									type="file"
									id="wizard-file-input"
									onchange={(e) => {
										file = e.currentTarget.files?.[0] ?? null;
									}}
								/>
								<label for="wizard-file-input" class="upload-label">
									{#if file}
										<div class="file-info">
											<strong>{file.name}</strong>
											<span>{fileSizeLabel(file)} · 클릭하면 다른 파일로 바꿀 수 있어요</span>
										</div>
									{:else}
										<div class="upload-cta">
											<strong>모델 파일 선택 <em class="req">*</em></strong>
											<span>.pt · .pth · .safetensors · .h5 · .pb · 디렉터리 아카이브 등 어떤 모델이든</span>
										</div>
									{/if}
								</label>
							</div>
						</div>
					{:else if step === 2}
						<div class="step-pane">
							<header class="pane-head">
								<h3>2. 실행 환경 선택</h3>
								<p>모델을 띄울 base image · 워크스페이스 종류. 직접 입력으로 임의의 이미지도 지정 가능.</p>
							</header>
							<div class="opt-table-wrap opt-table-wrap-sm">
							<table class="opt-table">
								<thead>
									<tr>
										<th class="col-sel" aria-label="select"></th>
										<th>환경</th>
										<th class="col-meta">입력</th>
										<th class="col-meta">자원</th>
										<th class="col-state">상태</th>
									</tr>
								</thead>
								<tbody>
									{#each MODEL_PRESETS as p (p.id)}
										{@const unavailable = p.available === false}
										<tr
											class="opt-row"
											class:selected={presetId === p.id}
											class:unavailable
											onclick={() => (unavailable ? null : (presetId = p.id))}
											title={unavailable ? '준비 중 — admin이 base image 를 빌드하면 활성화됩니다.' : p.description}
										>
											<td class="col-sel">
												<span class="radio" class:on={presetId === p.id}></span>
											</td>
											<td>
												<div class="opt-title">
													<span class="opt-badge" class:opt-badge-muted={unavailable}>{p.badge}</span>
													<strong>{p.label}</strong>
												</div>
												<div class="opt-sub">{p.tagline}</div>
											</td>
											<td class="col-meta">{p.workspaceKind}</td>
											<td class="col-meta">{p.requiresGpu ? 'GPU' : 'CPU'} · {p.minMemoryMb}MB · {p.minWorkspaceGb}GB</td>
											<td class="col-state">
												{#if unavailable}<span class="preview-tag">PREVIEW</span>{:else}<span class="state-ok">활성</span>{/if}
											</td>
										</tr>
									{/each}
									<tr
										class="opt-row opt-row-custom"
										class:selected={isCustomPreset}
										onclick={() => { presetId = CUSTOM_PRESET_ID; customPresetExpanded = true; }}
									>
										<td class="col-sel"><span class="radio" class:on={isCustomPreset}></span></td>
										<td colspan="3">
											<div class="opt-title">
												<span class="opt-badge opt-badge-muted">CUSTOM</span>
												<strong>직접 입력</strong>
											</div>
											<div class="opt-sub">사전 정의 환경 외의 base image / 워크스페이스 직접 지정</div>
										</td>
										<td class="col-state"><span class="state-custom">CUSTOM</span></td>
									</tr>
								</tbody>
							</table>
							</div>
							{#if isCustomPreset}
								<div class="custom-form">
									<div class="grid">
										<label class="field">
											<span class="label">Base image <em class="req">*</em></span>
											<input bind:value={customBaseImage} placeholder="예: my-registry/my-image:tag" />
											<span class="hint">레지스트리에 이미 로드된 image tag.</span>
										</label>
										<label class="field">
											<span class="label">워크스페이스 종류</span>
											<select bind:value={customWorkspaceKind}>
												<option value="jupyter">jupyter</option>
												<option value="code-server">code-server</option>
												<option value="api">api</option>
											</select>
										</label>
										<label class="field">
											<span class="label">포트</span>
											<input type="number" bind:value={customWorkspacePort} placeholder="8888" min="1" max="65535" />
										</label>
										<label class="field field-inline">
											<input type="checkbox" bind:checked={customRequiresGpu} />
											<span>GPU 필요</span>
										</label>
									</div>
								</div>
							{/if}

							<header class="pane-head pane-head-sub">
								<h3>추론 레시피</h3>
								<p>
									컨테이너 시작 시 모델을 어떻게 띄울지 결정. <code>config.json</code> 의
									<code>architectures</code> 와 매칭되는 행 선택. 자동 실행을 원치 않으면
									<b>자동 실행 안 함</b>, 카탈로그에 없으면 <b>직접 입력</b>.
								</p>
							</header>
							{#if recipesError}
								<div class="error-box">{recipesError}</div>
							{/if}
							<div class="opt-table-wrap opt-table-wrap-lg">
							<table class="opt-table">
								<thead>
									<tr>
										<th class="col-sel" aria-label="select"></th>
										<th>레시피</th>
										<th class="col-meta">입력</th>
										<th>지원 아키텍처</th>
										<th class="col-state">상태</th>
									</tr>
								</thead>
								<tbody>
									{#each recipeCategoryOrder as cat}
										<tr class="opt-row-cat-head"><td colspan="5">{RECIPE_CATEGORY_LABEL[cat] || cat}</td></tr>
										{#each recipesByCategory[cat] as r (r.id)}
											{@const unavailable = r.available === false}
											<tr
												class="opt-row"
												class:selected={recipeId === r.id}
												class:unavailable
												onclick={() => (unavailable ? null : (recipeId = r.id))}
												title={unavailable ? '준비 중 — admin이 launch.py 의 app_template 을 구현하면 활성화됩니다.' : r.description}
											>
												<td class="col-sel"><span class="radio" class:on={recipeId === r.id}></span></td>
												<td>
													<div class="opt-title"><strong>{r.label}</strong></div>
													<div class="opt-sub">{r.description}</div>
												</td>
												<td class="col-meta">{r.input_kinds && r.input_kinds.length > 0 ? r.input_kinds.join(' + ') : '—'}</td>
												<td class="col-archs" title={(r.architectures || []).join(', ')}>
													{#if r.architectures && r.architectures.length > 0}
														<code>{r.architectures.slice(0, 2).join(', ')}{r.architectures.length > 2 ? ` +${r.architectures.length - 2}` : ''}</code>
													{:else}
														<span class="muted">—</span>
													{/if}
												</td>
												<td class="col-state">
													{#if unavailable}<span class="preview-tag">PREVIEW</span>{:else}<span class="state-ok">활성</span>{/if}
												</td>
											</tr>
										{/each}
									{/each}
									<tr
										class="opt-row opt-row-custom"
										class:selected={isCustomRecipe}
										onclick={() => { recipeId = CUSTOM_RECIPE_ID; customRecipeExpanded = true; }}
									>
										<td class="col-sel"><span class="radio" class:on={isCustomRecipe}></span></td>
										<td colspan="3">
											<div class="opt-title"><strong>직접 입력</strong></div>
											<div class="opt-sub">model_class / processor_class / app_template 을 직접 지정</div>
										</td>
										<td class="col-state"><span class="state-custom">CUSTOM</span></td>
									</tr>
								</tbody>
							</table>
							</div>
							{#if isCustomRecipe}
								<div class="custom-form">
									<div class="grid">
										<label class="field">
											<span class="label">model_class <em class="req">*</em></span>
											<input bind:value={customModelClass} placeholder="예: Idefics3ForConditionalGeneration" />
											<span class="hint"><code>transformers</code> 안의 클래스 이름.</span>
										</label>
										<label class="field">
											<span class="label">processor_class</span>
											<input bind:value={customProcessorClass} placeholder="AutoProcessor / AutoTokenizer" />
										</label>
										<label class="field">
											<span class="label">UI 형태 (app_template)</span>
											<select bind:value={customAppTemplate}>
												<option value="gradio_text_chat">텍스트 chat — 메시지 in / 텍스트 out (LLM)</option>
												<option value="gradio_vlm_chat">이미지+텍스트 chat — 이미지 업로드 + 프롬프트 (VLM)</option>
												<option value="none">자동 실행 안 함 — Jupyter 에서 직접</option>
											</select>
											<span class="hint">컨테이너가 시작될 때 어떤 모양의 자동 UI 를 띄울지.</span>
										</label>
										<label class="field field-inline">
											<input type="checkbox" bind:checked={customTrustRemoteCode} />
											<span>trust_remote_code</span>
										</label>
									</div>
								</div>
							{/if}
						</div>
					{:else}
						<div class="step-pane">
							<header class="pane-head">
								<h3>3. 확인 후 제출</h3>
								<p>아래 내용으로 {mode === 'admin' ? '등록' : '요청'}됩니다. 잘못된 부분이 있다면 좌측에서 단계를 눌러 돌아갈 수 있어요.</p>
							</header>
							<div class="summary">
								<div class="summary-row">
									<span class="key">모델</span>
									<span class="val"><strong>{modelName || '-'}</strong> <em>{version || 'v1'}</em></span>
								</div>
								<div class="summary-row">
									<span class="key">파일</span>
									<span class="val">{file ? `${file.name} · ${fileSizeLabel(file)}` : '-'}</span>
								</div>
								{#if description}
									<div class="summary-row">
										<span class="key">설명</span>
										<span class="val">{description}</span>
									</div>
								{/if}
								<div class="summary-row">
									<span class="key">실행 환경</span>
									<span class="val">
										{#if selectedPreset}
											<strong>{selectedPreset.label}</strong>
											<em>{selectedPreset.tagline}</em>
										{:else}
											-
										{/if}
									</span>
								</div>
								<div class="summary-row">
									<span class="key">추론 레시피</span>
									<span class="val">
										{#if selectedRecipe}
											<strong>{selectedRecipe.label}</strong>
											{#if selectedRecipe.id !== 'none'}
												<em>자동 실행</em>
											{:else}
												<em>수동 (노트북에서)</em>
											{/if}
										{:else}
											-
										{/if}
									</span>
								</div>
								<div class="summary-row">
									<span class="key">생성될 템플릿</span>
									<span class="val">{effectiveTemplateName || '-'}</span>
								</div>
								<div class="summary-row">
									<span class="key">자원</span>
									<span class="val">
										GPU {selectedPreset?.requiresGpu ? '필요' : '불필요'} · RAM {effectiveMinMemoryMb} MB · 디스크 {effectiveMinWorkspaceGb} GB · 포트 {effectiveWorkspacePort}
									</span>
								</div>
							</div>

							<details class="advanced" bind:open={showAdvanced}>
								<summary>고급 설정 (선택)</summary>
								<div class="advanced-body">
									<p class="advanced-hint">비워두면 preset 기본값을 그대로 사용합니다.</p>
									<div class="grid">
										<label class="field">
											<span class="label">템플릿 이름 (커스텀)</span>
											<input bind:value={templateName} placeholder={effectiveTemplateName} />
										</label>
										<label class="field">
											<span class="label">최대 가동 시간 (시간)</span>
											<input
												type="number"
												min="1"
												bind:value={defaultMaxRuntimeHours}
												placeholder={String(selectedPreset?.defaultMaxRuntimeHours ?? 24)}
											/>
										</label>
										<label class="field">
											<span class="label">최소 메모리 (MB)</span>
											<input
												type="number"
												min="512"
												bind:value={minMemoryMb}
												placeholder={String(selectedPreset?.minMemoryMb ?? 2048)}
											/>
										</label>
										<label class="field">
											<span class="label">워크스페이스 디스크 (GB)</span>
											<input
												type="number"
												min="1"
												bind:value={minWorkspaceGb}
												placeholder={String(selectedPreset?.minWorkspaceGb ?? 10)}
											/>
										</label>
										<label class="field">
											<span class="label">워크스페이스 포트</span>
											<input
												type="number"
												min="1"
												max="65535"
												bind:value={workspacePort}
												placeholder={String(selectedPreset?.workspacePort ?? 8888)}
											/>
										</label>
									</div>
								</div>
							</details>

							{#if errorMsg}
								<div class="error-box">{errorMsg}</div>
							{/if}
						</div>
					{/if}
				</section>
			</div>

			<footer class="modal-foot">
				<button class="ghost" onclick={close} disabled={busy}>취소</button>
				<div class="foot-right">
					{#if step > 1}
						<button class="secondary" onclick={goBack} disabled={busy}>이전</button>
					{/if}
					{#if step < 3}
						<button
							class="primary"
							onclick={goNext}
							disabled={(step === 1 && !step1Valid) || (step === 2 && !step2Valid)}
						>
							다음
						</button>
					{:else}
						<button class="primary" onclick={submit} disabled={!canSubmit}>
							{busy ? '제출 중…' : mode === 'admin' ? '템플릿 등록' : '요청 제출'}
						</button>
					{/if}
				</div>
			</footer>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 220;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(0, 0, 0, 0.66);
		backdrop-filter: blur(4px);
	}

	.upload-overlay {
		position: absolute;
		inset: 0;
		z-index: 30;
		background: rgba(13, 17, 23, 0.85);
		backdrop-filter: blur(2px);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.upload-card {
		width: min(420px, 86%);
		padding: 22px 24px;
		border: 1px solid var(--accent);
		border-radius: 10px;
		background: var(--bg-card);
		box-shadow: 0 12px 36px rgba(0, 0, 0, 0.4);
		text-align: center;
	}

	.upload-card h3 {
		margin: 0 0 8px;
		color: var(--accent);
		font-size: 15px;
		font-weight: 800;
	}

	.upload-file {
		margin: 0 0 14px;
		font-size: 12px;
		color: var(--text-secondary);
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		word-break: break-all;
	}

	.upload-bar {
		width: 100%;
		height: 8px;
		background: rgba(100, 116, 139, 0.18);
		border-radius: 4px;
		overflow: hidden;
		margin-bottom: 8px;
	}

	.upload-bar-fill {
		height: 100%;
		background: var(--accent);
		transition: width 0.18s linear;
	}

	.upload-meta {
		margin: 0;
		font-size: 11.5px;
		color: var(--text-muted);
	}

	.upload-spinner {
		width: 28px;
		height: 28px;
		margin: 8px auto 12px;
		border: 3px solid rgba(100, 116, 139, 0.2);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: upload-spin 0.8s linear infinite;
	}

	@keyframes upload-spin {
		to { transform: rotate(360deg); }
	}

	.upload-actions {
		display: flex;
		justify-content: center;
		gap: 8px;
		margin-top: 14px;
	}

	.upload-cancel {
		padding: 7px 16px;
		font: inherit;
		font-size: 12px;
		font-weight: 800;
		color: var(--text-primary);
		background: rgba(239, 68, 68, 0.15);
		border: 1px solid rgba(239, 68, 68, 0.5);
		border-radius: 6px;
		cursor: pointer;
	}

	.upload-cancel:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.25);
		border-color: rgba(239, 68, 68, 0.8);
	}

	.upload-cancel:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.modal {
		position: relative;
		width: min(960px, 96vw);
		height: min(720px, 92vh);
		display: flex;
		flex-direction: column;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 12px;
		overflow: hidden;
		box-shadow: 0 24px 60px rgba(0, 0, 0, 0.5);
	}

	.modal-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 12px;
		padding: 18px 20px;
		border-bottom: 1px solid var(--border);
		background: linear-gradient(180deg, rgba(21, 28, 39, 0.6), transparent);
	}

	.modal-head-text p,
	.modal-head-text h2 {
		margin: 0;
	}

	.kicker {
		color: var(--accent);
		font-size: 11px;
		font-weight: 900;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

	.modal-head h2 {
		margin-top: 4px;
		color: var(--text-primary);
		font-size: 20px;
	}

	.subtitle {
		margin-top: 6px;
		color: var(--text-secondary);
		font-size: 12.5px;
		max-width: 580px;
		line-height: 1.5;
	}

	.icon-btn {
		width: 34px;
		height: 34px;
		padding: 0;
		font: inherit;
		font-size: 18px;
		background: var(--bg-base);
		color: var(--text-secondary);
		border: 1px solid var(--border);
		border-radius: 8px;
		cursor: pointer;
	}

	.body {
		display: grid;
		grid-template-columns: 240px 1fr;
		gap: 0;
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}

	.stepper {
		padding: 22px 14px;
		border-right: 1px solid var(--border);
		background: rgba(13, 17, 23, 0.55);
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.step {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 12px;
		border: 1px solid transparent;
		border-radius: 10px;
		background: transparent;
		color: var(--text-secondary);
		font: inherit;
		cursor: pointer;
		text-align: left;
		transition: background 0.12s, border-color 0.12s, color 0.12s;
	}

	.step:disabled {
		cursor: not-allowed;
		opacity: 0.55;
	}

	.step.reachable:hover {
		background: rgba(77, 191, 179, 0.06);
	}

	.step.active {
		background: rgba(77, 191, 179, 0.10);
		border-color: rgba(77, 191, 179, 0.4);
		color: var(--text-primary);
	}

	.step.done {
		color: var(--text-primary);
	}

	.step-num {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: rgba(100, 116, 139, 0.18);
		color: var(--text-muted);
		font-weight: 900;
		font-size: 13px;
		flex-shrink: 0;
	}

	.step.active .step-num {
		background: var(--accent);
		color: var(--bg-base);
	}

	.step.done .step-num {
		background: rgba(77, 191, 179, 0.85);
		color: var(--bg-base);
	}

	.step-text {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.step-text strong {
		font-size: 13.5px;
		font-weight: 800;
	}

	.step-text em {
		font-style: normal;
		font-size: 11.5px;
		color: var(--text-muted);
	}

	.content {
		padding: 22px 24px;
		overflow-y: auto;
		min-width: 0;
	}

	.step-pane {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	.pane-head h3 {
		margin: 0;
		color: var(--text-primary);
		font-size: 16px;
		font-weight: 800;
	}

	.pane-head p {
		margin: 6px 0 0;
		color: var(--text-secondary);
		font-size: 12.5px;
		line-height: 1.5;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 14px;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}

	.field .label {
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 800;
	}

	.field .hint {
		color: var(--text-muted);
		font-size: 11.5px;
	}

	.field .req {
		color: var(--accent);
		font-style: normal;
		font-weight: 900;
	}

	.field input,
	.field textarea {
		font: inherit;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
		color: var(--text-primary);
		padding: 9px 11px;
		min-width: 0;
	}

	.field textarea {
		resize: vertical;
	}

	.field input:focus,
	.field textarea:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 3px rgba(77, 191, 179, 0.18);
	}

	.upload-zone {
		position: relative;
		border: 1.5px dashed rgba(100, 116, 139, 0.5);
		border-radius: 12px;
		background: rgba(13, 17, 23, 0.4);
		transition: border-color 0.12s, background 0.12s;
	}

	.upload-zone.has-file {
		border-color: rgba(77, 191, 179, 0.55);
		background: rgba(77, 191, 179, 0.06);
	}

	.upload-zone input[type='file'] {
		position: absolute;
		inset: 0;
		opacity: 0;
		cursor: pointer;
	}

	.upload-label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 22px 18px;
		text-align: center;
		cursor: pointer;
	}

	.upload-cta strong,
	.file-info strong {
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 800;
	}

	.upload-cta span,
	.file-info span {
		color: var(--text-muted);
		font-size: 12px;
		margin-top: 4px;
	}

	.preset-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 10px;
	}

	.preset-card {
		display: flex;
		flex-direction: column;
		gap: 6px;
		height: 124px;
		padding: 12px 14px;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--bg-base);
		color: var(--text-primary);
		text-align: left;
		cursor: pointer;
		font: inherit;
		overflow: hidden;
		transition: border-color 0.12s, background 0.12s;
	}

	.preset-card:hover {
		border-color: rgba(77, 191, 179, 0.4);
		background: rgba(77, 191, 179, 0.04);
	}

	.preset-card.selected {
		border-color: var(--accent);
		background: rgba(77, 191, 179, 0.10);
		box-shadow: 0 0 0 2px rgba(77, 191, 179, 0.22);
	}

	.preset-card.unavailable,
	.recipe-card.unavailable {
		cursor: not-allowed;
		border-style: dashed;
		opacity: 0.55;
	}

	.preset-card.unavailable:hover,
	.recipe-card.unavailable:hover {
		background: var(--bg-base);
		border-color: var(--border);
	}

	.preview-tag {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		padding: 2px 6px;
		font-size: 9.5px;
		font-weight: 900;
		letter-spacing: 0.06em;
		color: var(--text-muted);
		background: rgba(100, 116, 139, 0.18);
		border-radius: 4px;
	}

	.recipe-category {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.recipe-category-label {
		margin: 4px 0 0;
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 800;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.opt-table-wrap {
		border: 1px solid var(--border);
		border-radius: 8px;
		overflow: auto;
		background: var(--bg-base);
	}

	.opt-table-wrap-sm {
		max-height: 220px;
	}

	.opt-table-wrap-lg {
		max-height: 320px;
	}

	.opt-table {
		width: 100%;
		border-collapse: separate;
		border-spacing: 0;
		font-size: 12.5px;
	}

	.opt-table thead th {
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

	.opt-table tbody tr.opt-row {
		cursor: pointer;
		transition: background 0.12s;
	}

	.opt-table tbody tr.opt-row:hover {
		background: rgba(77, 191, 179, 0.05);
	}

	.opt-table tbody tr.opt-row.selected {
		background: rgba(77, 191, 179, 0.12);
	}

	.opt-table tbody tr.opt-row.unavailable {
		cursor: not-allowed;
		opacity: 0.5;
	}

	.opt-table tbody tr.opt-row.unavailable:hover {
		background: transparent;
	}

	.opt-table td {
		padding: 6px 10px;
		border-bottom: 1px solid var(--border);
		vertical-align: middle;
		line-height: 1.3;
	}

	.opt-table .col-sel {
		width: 28px;
		text-align: center;
		padding-right: 0;
	}

	.opt-table .col-meta {
		white-space: nowrap;
		color: var(--text-muted);
		font-size: 11.5px;
	}

	.opt-table .col-archs code {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 11px;
		color: var(--text-primary);
		background: rgba(100, 116, 139, 0.14);
		padding: 1px 5px;
		border-radius: 3px;
	}

	.opt-table .col-archs .muted {
		color: var(--text-muted);
	}

	.opt-table .col-state {
		width: 88px;
		text-align: right;
		white-space: nowrap;
	}

	.opt-title {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.opt-title strong {
		font-size: 13px;
		font-weight: 800;
		color: var(--text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.opt-badge {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		padding: 2px 6px;
		font-size: 9.5px;
		font-weight: 900;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--bg-base);
		background: var(--accent);
		border-radius: 3px;
	}

	.opt-badge-muted {
		color: var(--text-muted);
		background: rgba(100, 116, 139, 0.18);
	}

	.opt-sub {
		display: none; /* compact table — full description in hover title only */
	}

	.radio {
		display: inline-block;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		border: 1.5px solid var(--text-muted);
		background: transparent;
		vertical-align: middle;
	}

	.radio.on {
		border-color: var(--accent);
		background: radial-gradient(circle, var(--accent) 0 4.5px, transparent 5.5px);
	}

	.opt-row-cat-head td {
		padding: 8px 10px 3px;
		border-bottom: none;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		background: rgba(13, 17, 23, 0.25);
	}

	.opt-row-custom td {
		border-bottom: none;
	}

	.opt-row-custom {
		background: rgba(13, 17, 23, 0.4);
	}

	.state-ok {
		color: var(--accent);
		font-size: 11px;
		font-weight: 800;
	}

	.state-custom {
		color: var(--text-muted);
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.04em;
	}

	.custom-form {
		margin-top: -4px;
		padding: 12px 14px;
		border: 1px solid var(--accent);
		border-radius: 8px;
		background: rgba(77, 191, 179, 0.06);
	}

	.field-inline {
		flex-direction: row !important;
		align-items: center;
		gap: 8px !important;
		padding-top: 24px;
	}

	.field-inline input[type='checkbox'] {
		width: 16px;
		height: 16px;
		flex-shrink: 0;
	}

	.field select {
		font: inherit;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
		color: var(--text-primary);
		padding: 9px 11px;
		min-width: 0;
	}

	.preset-head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.preset-badge {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 2px 7px;
		font-size: 10px;
		font-weight: 900;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--bg-base);
		background: var(--accent);
		border-radius: 4px;
	}

	.preset-badge-muted {
		color: var(--text-muted);
		background: rgba(100, 116, 139, 0.18);
	}

	.preset-head strong {
		flex: 1 1 auto;
		min-width: 0;
		color: var(--text-primary);
		font-size: 13.5px;
		font-weight: 800;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.preset-check {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: var(--accent);
		color: var(--bg-base);
	}

	.preset-tagline {
		margin: 0;
		color: var(--accent);
		font-size: 11.5px;
		font-weight: 700;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.preset-tagline-muted {
		color: var(--text-muted);
		font-weight: 600;
	}

	.preset-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 5px;
		margin-top: auto;
	}

	.preset-meta-muted span {
		color: var(--text-muted) !important;
		background: transparent !important;
		font-weight: 600 !important;
		padding: 0 !important;
		font-size: 11px !important;
	}

	.pane-head-sub {
		margin-top: 6px;
		padding-top: 14px;
		border-top: 1px solid var(--border);
	}

	.recipe-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px;
	}

	.recipe-card {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 12px 14px;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--bg-base);
		color: var(--text-primary);
		text-align: left;
		cursor: pointer;
		font: inherit;
		transition: border-color 0.12s, background 0.12s;
	}

	.recipe-card:hover {
		border-color: rgba(77, 191, 179, 0.4);
	}

	.recipe-card.selected {
		border-color: var(--accent);
		background: rgba(77, 191, 179, 0.10);
		box-shadow: 0 0 0 3px rgba(77, 191, 179, 0.18);
	}

	.recipe-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}

	.recipe-head strong {
		font-size: 13.5px;
		font-weight: 800;
	}

	.recipe-kinds {
		padding: 2px 6px;
		font-size: 10.5px;
		font-weight: 700;
		color: var(--text-muted);
		background: rgba(100, 116, 139, 0.18);
		border-radius: 4px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.recipe-desc {
		margin: 0;
		color: var(--text-secondary);
		font-size: 12px;
		line-height: 1.45;
	}

	.recipe-archs {
		display: flex;
		align-items: baseline;
		gap: 6px;
		padding: 5px 7px;
		margin-top: 2px;
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: 5px;
		background: rgba(100, 116, 139, 0.06);
		font-size: 11px;
		line-height: 1.3;
		min-width: 0;
	}

	.recipe-archs-key {
		flex-shrink: 0;
		color: var(--text-muted);
		font-weight: 800;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.recipe-archs-val {
		color: var(--text-primary);
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.recipe-fallback {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 8px 12px;
		padding: 10px 12px;
		border: 1px dashed rgba(100, 116, 139, 0.4);
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.4);
		color: var(--text-secondary);
		font-size: 12px;
		line-height: 1.5;
	}

	.recipe-fallback strong {
		color: var(--text-primary);
		font-size: 12.5px;
		font-weight: 800;
		white-space: nowrap;
	}

	.recipe-fallback code {
		padding: 1px 5px;
		border-radius: 3px;
		background: rgba(100, 116, 139, 0.18);
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 11.5px;
		color: var(--text-primary);
	}

	.pane-head p code {
		padding: 1px 5px;
		border-radius: 3px;
		background: rgba(100, 116, 139, 0.18);
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 11.5px;
		color: var(--text-primary);
	}

	.preset-meta span {
		display: inline-flex;
		align-items: center;
		padding: 3px 8px;
		font-size: 11px;
		font-weight: 700;
		color: var(--text-muted);
		background: rgba(100, 116, 139, 0.14);
		border-radius: 5px;
	}

	.summary {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 14px 16px;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.4);
	}

	.summary-row {
		display: grid;
		grid-template-columns: 130px 1fr;
		gap: 12px;
		align-items: baseline;
		font-size: 13px;
		line-height: 1.5;
	}

	.summary-row .key {
		color: var(--text-muted);
		font-weight: 800;
		font-size: 12px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.summary-row .val {
		color: var(--text-primary);
		word-break: break-word;
	}

	.summary-row .val em {
		font-style: normal;
		color: var(--text-muted);
		margin-left: 6px;
		font-size: 12px;
	}

	.advanced {
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--bg-base);
		padding: 0;
	}

	.advanced > summary {
		list-style: none;
		padding: 12px 16px;
		cursor: pointer;
		color: var(--text-secondary);
		font-size: 13px;
		font-weight: 800;
	}

	.advanced > summary::-webkit-details-marker {
		display: none;
	}

	.advanced > summary::before {
		content: '▸ ';
		color: var(--text-muted);
		display: inline-block;
		transition: transform 0.12s;
	}

	.advanced[open] > summary::before {
		content: '▾ ';
	}

	.advanced-body {
		padding: 6px 16px 16px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.advanced-hint {
		margin: 0;
		color: var(--text-muted);
		font-size: 12px;
	}

	.error-box {
		padding: 10px 12px;
		border: 1px solid rgba(239, 68, 68, 0.45);
		border-radius: 8px;
		color: var(--error);
		background: rgba(239, 68, 68, 0.1);
		font-size: 12.5px;
	}

	.modal-foot {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		padding: 14px 20px;
		border-top: 1px solid var(--border);
		background: rgba(13, 17, 23, 0.4);
	}

	.foot-right {
		display: flex;
		gap: 10px;
	}

	.modal-foot button {
		min-height: 36px;
		border-radius: 8px;
		padding: 0 16px;
		font: inherit;
		font-weight: 800;
		cursor: pointer;
		border: 1px solid var(--border);
	}

	.ghost {
		background: transparent;
		color: var(--text-muted);
	}

	.secondary {
		background: var(--bg-base);
		color: var(--text-primary);
	}

	.primary {
		background: var(--accent);
		border-color: transparent;
		color: var(--bg-base);
	}

	.modal-foot button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	@media (max-width: 760px) {
		.body {
			grid-template-columns: 1fr;
		}

		.stepper {
			flex-direction: row;
			overflow-x: auto;
			border-right: none;
			border-bottom: 1px solid var(--border);
			padding: 10px;
		}

		.step {
			min-width: 180px;
		}

		.grid,
		.preset-grid,
		.recipe-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
