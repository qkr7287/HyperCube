<script lang="ts">
	import { browser } from '$app/environment';
	import { base } from '$app/paths';

	let {
		open = false,
		onClose = () => {},
		onSubmitted = () => {},
	}: {
		open?: boolean;
		onClose?: () => void;
		onSubmitted?: () => void;
	} = $props();

	type Template = {
		id: string;
		name: string;
		kind: string;
		image: string;
		image_options: any[];
		env_schema: any[];
		port_schema: any[];
		description: string;
		[k: string]: any;
	};

	type Agent = {
		id: string;
		hostname: string;
		ip_address: string;
		is_active: boolean;
	};

	let templates = $state<Template[]>([]);
	let agents = $state<Agent[]>([]);
	let selectedTemplate = $state<Template | null>(null);
	let selectedAgent = $state('');
	let selectedImage = $state('');
	let customName = $state('');
	let envValues = $state<Record<string, string>>({});
	let portValues = $state<Record<number, number>>({});
	let busy = $state(false);
	let errorMsg = $state('');

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	$effect(() => {
		if (open) {
			selectedTemplate = null;
			selectedAgent = '';
			selectedImage = '';
			customName = '';
			envValues = {};
			portValues = {};
			errorMsg = '';
			loadData();
		}
	});

	async function loadData() {
		const t = token();
		if (!t) return;
		try {
			const [tplRes, agentRes] = await Promise.all([
				fetch(`${base}/api/templates/?page_size=100`, {
					headers: { Authorization: `Bearer ${t}` },
				}),
				fetch(`${base}/api/agents/?status=approved&active=true`, {
					headers: { Authorization: `Bearer ${t}` },
				}),
			]);
			if (tplRes.ok) {
				const j = await tplRes.json();
				templates = j.data?.results ?? [];
			}
			if (agentRes.ok) {
				const j = await agentRes.json();
				agents = j.data?.results ?? [];
				if (agents.length === 1) selectedAgent = agents[0].id;
			}
		} catch {
			// ignore
		}
	}

	function selectTemplate(tpl: Template) {
		selectedTemplate = tpl;
		selectedImage = tpl.image || (tpl.image_options?.[0]?.image ?? '');
		envValues = {};
		portValues = {};
		for (const env of tpl.env_schema ?? []) {
			envValues[env.key] = env.default ?? '';
		}
		for (const port of tpl.port_schema ?? []) {
			portValues[port.internal] = port.host_default ?? port.internal;
		}
	}

	async function submit() {
		if (!selectedTemplate || !selectedAgent || busy) return;
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

		const body = {
			action: 'create',
			template: selectedTemplate.id,
			target_agent: selectedAgent,
			custom_name: customName,
			selected_image: selectedImage,
			custom_env: envValues,
			custom_ports: customPorts,
		};

		try {
			const res = await fetch(`${base}/api/requests/`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${t}`,
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(body),
			});
			if (!res.ok) {
				const j = await res.json().catch(() => ({}));
				const detail = j?.detail || j?.error;
				throw new Error(
					typeof detail === 'string' ? detail : JSON.stringify(detail ?? `HTTP ${res.status}`),
				);
			}
			onSubmitted();
			onClose();
		} catch (error: any) {
			errorMsg = error?.message || '요청 제출에 실패했습니다.';
		} finally {
			busy = false;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onClose();
	}

	$effect(() => {
		if (open) {
			document.addEventListener('keydown', handleKeydown);
			return () => document.removeEventListener('keydown', handleKeydown);
		}
	});
</script>

{#if open}
	<div class="overlay" onclick={onClose} role="dialog" aria-modal="true">
		<div class="modal" onclick={(event) => event.stopPropagation()}>
			<div class="modal-header">
				<span class="title">{selectedTemplate ? `새 요청: ${selectedTemplate.name}` : '새 컨테이너 요청'}</span>
				<button class="close-btn" onclick={onClose} aria-label="닫기">
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
						<path d="M18 6L6 18M6 6l12 12" />
					</svg>
				</button>
			</div>

			<div class="modal-content">
				{#if !selectedTemplate}
					<div class="step-label">1. 템플릿 선택</div>
					<p class="step-hint">먼저 만들고 싶은 컨테이너 종류를 선택하세요. 템플릿마다 필요한 설정이 다르게 표시됩니다.</p>
					<div class="template-grid">
						{#each templates as tpl (tpl.id)}
							<button class="template-card" onclick={() => selectTemplate(tpl)}>
								<div class="tpl-name">{tpl.name}</div>
								<div class="tpl-kind" class:compose={tpl.kind === 'compose'}>
									{tpl.kind === 'compose' ? 'Compose' : '단일'}
								</div>
								<div class="tpl-desc">{tpl.description || tpl.image}</div>
							</button>
						{/each}
					</div>
					{#if templates.length === 0}
						<div class="empty-hint">관리자가 등록한 템플릿이 아직 없습니다.</div>
					{/if}
				{:else}
					<div class="step-label">2. 요청 정보 입력</div>
					<p class="step-hint">이름, 배치 서버, 환경 변수, 포트를 확인한 뒤 요청을 제출하세요.</p>

					{#if selectedTemplate.kind === 'simple' && selectedTemplate.image_options?.length > 0}
						<div class="field">
							<label for="req-image">이미지 선택</label>
							<select id="req-image" bind:value={selectedImage}>
								{#each selectedTemplate.image_options as option}
									<option value={option.image}>{option.label}</option>
								{/each}
							</select>
						</div>
					{/if}

					<div class="field">
						<label for="req-name">
							컨테이너 이름
							<span class="hint">비워두면 기본 이름이 사용됩니다.</span>
						</label>
						<input id="req-name" type="text" bind:value={customName} placeholder="예: my-postgres" />
					</div>

					<div class="field">
						<label for="req-agent">배치 서버 *</label>
						<select id="req-agent" bind:value={selectedAgent}>
							<option value="" disabled>서버를 선택하세요</option>
							{#each agents as agent (agent.id)}
								<option value={agent.id}>{agent.hostname} ({agent.ip_address})</option>
							{/each}
						</select>
					</div>

					{#if selectedTemplate.env_schema?.length > 0}
						<div class="section-label">환경 변수</div>
						{#each selectedTemplate.env_schema as env}
							<div class="field">
								<label>
									{env.key}
									{#if env.required}
										<span class="required">*</span>
									{/if}
									{#if env.description}
										<span class="hint">{env.description}</span>
									{/if}
								</label>
								<input
									type={env.type === 'password' ? 'password' : 'text'}
									value={envValues[env.key] ?? ''}
									oninput={(event) => {
										envValues[env.key] = event.currentTarget.value;
										envValues = envValues;
									}}
									placeholder={env.default || ''}
								/>
							</div>
						{/each}
					{/if}

					{#if selectedTemplate.port_schema?.length > 0}
						<div class="section-label">포트 매핑</div>
						{#each selectedTemplate.port_schema as port}
							<div class="port-row">
								<span class="port-label">
									{port.description || `포트 ${port.internal}`}
									<span class="port-internal">컨테이너 내부 포트 :{port.internal}</span>
								</span>
								<input
									type="number"
									value={portValues[port.internal] ?? port.host_default}
									oninput={(event) => {
										portValues[port.internal] = Number(event.currentTarget.value);
										portValues = portValues;
									}}
									min="1"
									max="65535"
								/>
							</div>
						{/each}
					{/if}

					<button class="back-btn" onclick={() => (selectedTemplate = null)}>다른 템플릿 선택</button>
				{/if}
			</div>

			{#if selectedTemplate}
				<div class="modal-footer">
					{#if errorMsg}
						<div class="error">{errorMsg}</div>
					{/if}
					<div class="action-row">
						<button class="btn-cancel" onclick={onClose}>취소</button>
						<button class="btn-submit" disabled={busy || !selectedAgent} onclick={submit}>
							{busy ? '제출 중...' : '요청 제출'}
						</button>
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 200;
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(4px);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.modal {
		width: 640px;
		max-width: 92vw;
		max-height: 88vh;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 18px 22px;
		border-bottom: 1px solid var(--border);
	}

	.title {
		font-size: 16px;
		font-weight: 700;
		color: var(--text-primary);
	}

	.close-btn {
		background: none;
		border: none;
		cursor: pointer;
		padding: 4px;
		display: flex;
	}

	.modal-content {
		flex: 1;
		overflow-y: auto;
		padding: 18px 22px 22px;
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.step-label {
		font-size: 13px;
		font-weight: 700;
		color: var(--text-secondary);
		margin-bottom: 4px;
	}

	.step-hint {
		font-size: 12px;
		color: var(--text-muted);
		line-height: 1.5;
	}

	.template-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 10px;
	}

	.template-card {
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 14px;
		cursor: pointer;
		text-align: left;
		font-family: inherit;
		transition: border-color 0.12s, background 0.12s;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.template-card:hover {
		border-color: var(--accent);
		background: var(--bg-tab);
	}

	.tpl-name {
		font-size: 14px;
		font-weight: 700;
		color: var(--text-primary);
	}

	.tpl-kind {
		display: inline-block;
		padding: 1px 6px;
		border-radius: 3px;
		font-size: 10px;
		font-weight: 600;
		width: fit-content;
		background: rgba(48, 213, 200, 0.15);
		color: var(--accent);
	}

	.tpl-kind.compose {
		background: rgba(139, 92, 246, 0.15);
		color: #a78bfa;
	}

	.tpl-desc {
		font-size: 11px;
		color: var(--text-muted);
		line-height: 1.4;
	}

	.empty-hint {
		text-align: center;
		color: var(--text-muted);
		font-size: 12px;
		padding: 20px;
	}

	.section-label {
		font-size: 12px;
		font-weight: 700;
		color: var(--text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.02em;
		margin-top: 4px;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.field label {
		font-size: 12px;
		font-weight: 600;
		color: var(--text-secondary);
	}

	.required {
		color: var(--error);
	}

	.hint {
		font-weight: 400;
		color: var(--text-muted);
		font-size: 10px;
		margin-left: 4px;
	}

	.field input,
	.field select {
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		padding: 8px 12px;
		color: var(--text-primary);
		font-family: inherit;
		font-size: 13px;
	}

	.field input:focus,
	.field select:focus {
		outline: none;
		border-color: var(--accent);
	}

	.port-row {
		display: flex;
		align-items: center;
		gap: 10px;
		justify-content: space-between;
	}

	.port-label {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.port-internal {
		display: block;
		font-size: 10px;
		color: var(--text-muted);
		margin-top: 4px;
	}

	.port-row input {
		width: 100px;
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		padding: 6px 10px;
		color: var(--text-primary);
		font-family: inherit;
		font-size: 13px;
		text-align: right;
	}

	.back-btn {
		background: none;
		border: none;
		color: var(--accent);
		font-size: 12px;
		cursor: pointer;
		padding: 4px 0;
		align-self: flex-start;
		font-family: inherit;
	}

	.back-btn:hover {
		text-decoration: underline;
	}

	.modal-footer {
		padding: 14px 22px;
		border-top: 1px solid var(--border);
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.error {
		font-size: 12px;
		color: var(--error);
	}

	.action-row {
		display: flex;
		justify-content: flex-end;
		gap: 10px;
	}

	.btn-cancel,
	.btn-submit {
		padding: 8px 18px;
		border-radius: var(--radius-sm);
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
		font-family: inherit;
	}

	.btn-cancel {
		background: var(--bg-tab);
		border: 1px solid var(--border);
		color: var(--text-primary);
	}

	.btn-submit {
		background: var(--accent);
		border: none;
		color: var(--bg-base);
	}

	.btn-submit:hover:not(:disabled) {
		filter: brightness(1.1);
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	@media (max-width: 640px) {
		.port-row {
			flex-direction: column;
			align-items: stretch;
		}

		.port-row input {
			width: 100%;
			text-align: left;
		}
	}
</style>
