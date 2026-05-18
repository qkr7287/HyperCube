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

	let busy = $state(false);
	let errorMsg = $state('');

	let selectedPreset = $derived<ModelPreset | null>(
		presetId ? MODEL_PRESETS.find((p) => p.id === presetId) ?? null : null,
	);

	let step1Valid = $derived(!!modelName.trim() && !!version.trim() && !!file);
	let step2Valid = $derived(!!selectedPreset);
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
		if (!t || !file || !selectedPreset) return null;
		const form = new FormData();
		form.append('name', modelName.trim());
		form.append('slug', slugify(modelName));
		form.append('version', version.trim());
		form.append('framework', selectedPreset.framework);
		form.append('task', selectedPreset.task);
		form.append('description', description.trim());
		form.append('template_name', effectiveTemplateName);
		form.append('template_description', description.trim() || effectiveTemplateName);
		form.append('base_image', selectedPreset.baseImage);
		form.append('requires_gpu', String(selectedPreset.requiresGpu));
		form.append('workspace_kind', selectedPreset.workspaceKind);
		form.append('workspace_port', String(effectiveWorkspacePort));
		form.append('default_max_runtime_hours', String(effectiveMaxRuntimeHours));
		form.append('min_cpu_percent', String(selectedPreset.minCpuPercent));
		form.append('min_memory_mb', String(effectiveMinMemoryMb));
		form.append('min_workspace_gb', String(effectiveMinWorkspaceGb));
		form.append('file', file);

		const res = await fetch(`${base}/api/model-upload-requests/`, {
			method: 'POST',
			headers: { Authorization: `Bearer ${t}` },
			body: form,
		});
		const json = await res.json().catch(() => ({}));
		if (!res.ok) throw new Error(json?.detail || json?.error?.detail || `HTTP ${res.status}`);
		return json?.data?.id ?? null;
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
			errorMsg = error?.message || '제출에 실패했습니다.';
		} finally {
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
								<p>이 모델을 어떻게 쓰실 건가요? 가장 가까운 환경을 골라주세요. 세부 설정은 자동으로 채워집니다.</p>
							</header>
							<div class="preset-grid">
								{#each MODEL_PRESETS as p (p.id)}
									<button
										type="button"
										class="preset-card"
										class:selected={presetId === p.id}
										onclick={() => (presetId = p.id)}
									>
										<div class="preset-head">
											<span class="preset-badge">{p.badge}</span>
											<strong>{p.label}</strong>
										</div>
										<p class="preset-tagline">{p.tagline}</p>
										<p class="preset-desc">{p.description}</p>
										<div class="preset-meta">
											<span>{p.requiresGpu ? 'GPU 필요' : 'CPU 가능'}</span>
											<span>RAM {p.minMemoryMb} MB</span>
											<span>디스크 {p.minWorkspaceGb} GB</span>
										</div>
									</button>
								{/each}
							</div>
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

	.modal {
		width: min(960px, 96vw);
		max-height: 92vh;
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
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}

	.preset-card {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 16px;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--bg-base);
		color: var(--text-primary);
		text-align: left;
		cursor: pointer;
		font: inherit;
		transition: border-color 0.12s, background 0.12s, transform 0.12s;
	}

	.preset-card:hover {
		border-color: rgba(77, 191, 179, 0.4);
		background: rgba(77, 191, 179, 0.04);
	}

	.preset-card.selected {
		border-color: var(--accent);
		background: rgba(77, 191, 179, 0.10);
		box-shadow: 0 0 0 3px rgba(77, 191, 179, 0.18);
	}

	.preset-head {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.preset-badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 3px 8px;
		font-size: 10.5px;
		font-weight: 900;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--bg-base);
		background: var(--accent);
		border-radius: 5px;
	}

	.preset-head strong {
		color: var(--text-primary);
		font-size: 14.5px;
		font-weight: 800;
	}

	.preset-tagline {
		margin: 0;
		color: var(--accent);
		font-size: 12px;
		font-weight: 800;
	}

	.preset-desc {
		margin: 0;
		color: var(--text-secondary);
		font-size: 12.5px;
		line-height: 1.5;
	}

	.preset-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 4px;
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
		.preset-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
