<script lang="ts">
	import { base } from '$app/paths';
	import { browser } from '$app/environment';

	let {
		open = false,
		onClose = () => {},
		onSubmitted = () => {},
	}: {
		open?: boolean;
		onClose?: () => void;
		onSubmitted?: () => void;
	} = $props();

	let name = $state('');
	let slug = $state('');
	let version = $state('v1');
	let framework = $state('pytorch');
	let task = $state('');
	let description = $state('');
	let templateName = $state('');
	let baseImage = $state('hypercube/ml-pytorch-jupyter:cuda12.4-airgap');
	let requiresGpu = $state(true);
	let minMemoryMb = $state(2048);
	let minWorkspaceGb = $state(10);
	let file = $state<File | null>(null);
	let busy = $state(false);
	let errorMsg = $state('');

	let canSubmit = $derived(
		!!name.trim() && !!version.trim() && !!baseImage.trim() && !!file && !busy,
	);

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	function reset() {
		name = '';
		slug = '';
		version = 'v1';
		framework = 'pytorch';
		task = '';
		description = '';
		templateName = '';
		baseImage = 'hypercube/ml-pytorch-jupyter:cuda12.4-airgap';
		requiresGpu = true;
		minMemoryMb = 2048;
		minWorkspaceGb = 10;
		file = null;
		errorMsg = '';
	}

	function fillSlug() {
		if (!name || slug) return;
		slug = name
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-|-$/g, '');
	}

	async function submit() {
		const t = token();
		if (!t || !canSubmit || !file) return;
		busy = true;
		errorMsg = '';
		try {
			const form = new FormData();
			form.append('name', name.trim());
			form.append('slug', slug.trim());
			form.append('version', version.trim());
			form.append('framework', framework.trim());
			form.append('task', task.trim());
			form.append('description', description.trim());
			form.append('template_name', templateName.trim() || `${name.trim()} Workspace`);
			form.append('template_description', description.trim());
			form.append('base_image', baseImage.trim());
			form.append('requires_gpu', String(requiresGpu));
			form.append('workspace_kind', 'jupyter');
			form.append('workspace_port', '8888');
			form.append('default_max_runtime_hours', '24');
			form.append('min_cpu_percent', '100');
			form.append('min_memory_mb', String(minMemoryMb || 2048));
			form.append('min_workspace_gb', String(minWorkspaceGb || 10));
			form.append('file', file);

			const res = await fetch(`${base}/api/model-upload-requests/`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${t}` },
				body: form,
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || json?.error || `HTTP ${res.status}`);
			reset();
			onSubmitted();
			onClose();
		} catch (error: any) {
			errorMsg = error?.message || '모델 업로드 요청에 실패했습니다.';
		} finally {
			busy = false;
		}
	}
</script>

{#if open}
	<div class="overlay" onclick={onClose} role="dialog" aria-modal="true">
		<div class="modal" onclick={(event) => event.stopPropagation()}>
			<header>
				<div>
					<p>Model Upload Request</p>
					<h2>모델 파일 등록 요청</h2>
				</div>
				<button class="icon-btn" onclick={onClose} aria-label="닫기">x</button>
			</header>

			<div class="content">
				<section>
					<h3>1. 모델 정보</h3>
					<div class="grid two">
						<label>
							<span>모델 이름 *</span>
							<input bind:value={name} onblur={fillSlug} placeholder="예: Tiny Vision" />
						</label>
						<label>
							<span>slug</span>
							<input bind:value={slug} placeholder="tiny-vision" />
						</label>
						<label>
							<span>버전 *</span>
							<input bind:value={version} placeholder="v1" />
						</label>
						<label>
							<span>프레임워크</span>
							<input bind:value={framework} placeholder="pytorch / tensorflow / vllm" />
						</label>
						<label>
							<span>작업 유형</span>
							<input bind:value={task} placeholder="text-generation, image-classification..." />
						</label>
						<label>
							<span>생성될 템플릿 이름</span>
							<input bind:value={templateName} placeholder="비우면 모델 이름 + Workspace" />
						</label>
					</div>
					<label>
						<span>설명</span>
						<textarea bind:value={description} rows="3" placeholder="모델 용도, 실행 조건, 필요한 메모리 등을 적어주세요."></textarea>
					</label>
				</section>

				<section>
					<h3>2. 실행 템플릿</h3>
					<div class="grid two">
						<label>
							<span>베이스 이미지 *</span>
							<input bind:value={baseImage} />
						</label>
						<label>
							<span>최소 메모리 MB</span>
							<input type="number" min="512" bind:value={minMemoryMb} />
						</label>
						<label>
							<span>워크스페이스 GB</span>
							<input type="number" min="1" bind:value={minWorkspaceGb} />
						</label>
						<label class="check">
							<input type="checkbox" bind:checked={requiresGpu} />
							<span>GPU 필요</span>
						</label>
					</div>
				</section>

				<section>
					<h3>3. 모델 파일</h3>
					<label class="file-field">
						<span>업로드 파일 *</span>
						<input
							type="file"
							onchange={(event) => {
								file = event.currentTarget.files?.[0] ?? null;
							}}
						/>
					</label>
					{#if file}
						<div class="file-pill">{file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB</div>
					{/if}
				</section>

				{#if errorMsg}
					<div class="error">{errorMsg}</div>
				{/if}
			</div>

			<footer>
				<button class="secondary" onclick={onClose}>취소</button>
				<button class="primary" disabled={!canSubmit} onclick={submit}>
					{busy ? '업로드 중...' : '요청 제출'}
				</button>
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
		background: rgba(0, 0, 0, 0.62);
		backdrop-filter: blur(4px);
	}

	.modal {
		width: min(820px, 94vw);
		max-height: 90vh;
		display: flex;
		flex-direction: column;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 10px;
		overflow: hidden;
	}

	header,
	footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		padding: 16px 18px;
		border-bottom: 1px solid var(--border);
	}

	footer {
		border-top: 1px solid var(--border);
		border-bottom: none;
		justify-content: flex-end;
	}

	header p,
	h2,
	h3 {
		margin: 0;
	}

	header p {
		color: var(--accent);
		font-size: 11px;
		font-weight: 900;
		text-transform: uppercase;
	}

	h2 {
		color: var(--text-primary);
		font-size: 18px;
	}

	h3 {
		color: var(--text-secondary);
		font-size: 13px;
	}

	.content {
		padding: 18px;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	section {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.grid {
		display: grid;
		gap: 10px;
	}

	.two {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 5px;
		min-width: 0;
	}

	label span {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 800;
	}

	input,
	textarea,
	button {
		font: inherit;
	}

	input,
	textarea {
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
		color: var(--text-primary);
		padding: 9px 10px;
		min-width: 0;
	}

	textarea {
		resize: vertical;
	}

	.check {
		flex-direction: row;
		align-items: center;
		align-self: end;
		min-height: 39px;
	}

	.check input {
		width: 16px;
		height: 16px;
	}

	.file-field input {
		padding: 8px;
	}

	.file-pill {
		display: inline-flex;
		align-self: flex-start;
		padding: 6px 9px;
		border: 1px solid rgba(77, 191, 179, 0.35);
		border-radius: 7px;
		color: var(--accent);
		background: rgba(77, 191, 179, 0.1);
		font-size: 12px;
		font-weight: 800;
	}

	.error {
		padding: 10px 12px;
		border: 1px solid rgba(239, 68, 68, 0.45);
		border-radius: 8px;
		color: var(--error);
		background: rgba(239, 68, 68, 0.1);
		font-size: 12px;
	}

	button {
		min-height: 36px;
		border-radius: 8px;
		padding: 0 14px;
		border: 1px solid var(--border);
		cursor: pointer;
		font-weight: 900;
	}

	.icon-btn {
		width: 34px;
		padding: 0;
		background: var(--bg-base);
		color: var(--text-secondary);
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

	button:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	@media (max-width: 720px) {
		.two {
			grid-template-columns: 1fr;
		}
	}
</style>
