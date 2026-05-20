<script lang="ts">
	let {
		template = null,
		open = false,
		onClose = () => {},
		onSave = (_data: any) => Promise.resolve(),
	}: {
		template?: any | null;
		open?: boolean;
		onClose?: () => void;
		onSave?: (data: any) => Promise<void>;
	} = $props();

	let name = $state('');
	let description = $state('');
	let kind = $state<'simple' | 'compose'>('simple');
	let image = $state('');
	let imageOptionsJson = $state('[]');
	let envSchemaJson = $state('[]');
	let portSchemaJson = $state('[]');
	let defaultVolumesJson = $state('[]');
	let composeYaml = $state('');
	let networkPolicy = $state<'none' | 'internal_only' | 'custom'>('none');
	let busy = $state(false);
	let errorMsg = $state('');

	$effect(() => {
		if (open) {
			if (template) {
				name = template.name ?? '';
				description = template.description ?? '';
				kind = template.kind ?? 'simple';
				image = template.image ?? '';
				imageOptionsJson = JSON.stringify(template.image_options ?? [], null, 2);
				envSchemaJson = JSON.stringify(template.env_schema ?? [], null, 2);
				portSchemaJson = JSON.stringify(template.port_schema ?? [], null, 2);
				defaultVolumesJson = JSON.stringify(template.default_volumes ?? [], null, 2);
				composeYaml = template.compose_yaml ?? '';
				networkPolicy = template.network_policy ?? 'none';
			} else {
				name = ''; description = ''; kind = 'simple'; image = '';
				imageOptionsJson = '[]'; envSchemaJson = '[]';
				portSchemaJson = '[]'; defaultVolumesJson = '[]';
				composeYaml = '';
				networkPolicy = 'none';
			}
			errorMsg = '';
		}
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	$effect(() => {
		if (open) {
			document.addEventListener('keydown', handleKeydown);
			return () => document.removeEventListener('keydown', handleKeydown);
		}
	});

	function tryParseJson(str: string, label: string): any {
		try {
			return JSON.parse(str);
		} catch {
			throw new Error(`${label} JSON 파싱 실패. 올바른 JSON인지 확인해주세요.`);
		}
	}

	async function handleSave() {
		if (busy) return;
		busy = true;
		errorMsg = '';
		try {
			const data: any = { name, description, kind, network_policy: networkPolicy };
			if (kind === 'simple') {
				data.image = image;
				data.image_options = tryParseJson(imageOptionsJson, 'image_options');
				data.env_schema = tryParseJson(envSchemaJson, 'env_schema');
				data.port_schema = tryParseJson(portSchemaJson, 'port_schema');
				data.default_volumes = tryParseJson(defaultVolumesJson, 'default_volumes');
			} else {
				data.compose_yaml = composeYaml;
				data.env_schema = tryParseJson(envSchemaJson, 'env_schema');
			}
			await onSave(data);
			onClose();
		} catch (e: any) {
			errorMsg = e?.message || '저장 실패';
		} finally {
			busy = false;
		}
	}
</script>

{#if open}
<div class="overlay" onclick={onClose} role="dialog">
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<span class="title">{template ? '템플릿 수정' : '새 템플릿'}</span>
			<button class="close-btn" onclick={onClose} aria-label="close">
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			<div class="field">
				<label for="tpl-name">이름 *</label>
				<input id="tpl-name" type="text" bind:value={name} placeholder="예: Postgres 15" />
			</div>

			<div class="field">
				<label for="tpl-desc">설명</label>
				<textarea id="tpl-desc" bind:value={description} rows="2" placeholder="템플릿 용도 설명"></textarea>
			</div>

			<div class="field">
				<label>타입 *</label>
				<div class="kind-toggle">
					<button class:active={kind === 'simple'} onclick={() => kind = 'simple'}>Simple (단일 이미지)</button>
					<button class:active={kind === 'compose'} onclick={() => kind = 'compose'}>Docker Compose</button>
				</div>
			</div>

			<div class="field">
				<label for="tpl-netpolicy">네트워크 정책</label>
				<select id="tpl-netpolicy" bind:value={networkPolicy}>
					<option value="none">none (호스트 포트 publish)</option>
					<option value="internal_only">internal_only (Docker 내부망)</option>
					<option value="custom">custom</option>
				</select>
				{#if networkPolicy === 'internal_only'}
					<div class="netpolicy-warn">
						internal_only 는 backend 와 agent 가 같은 Docker daemon 일 때만 동작합니다.
						다른 호스트의 agent 에 배포하면 Web UI 가 502 가 됩니다. 멀티호스트 fleet
						에서는 none 을 사용하세요.
					</div>
				{/if}
			</div>

			{#if kind === 'simple'}
				<div class="field">
					<label for="tpl-image">기본 이미지</label>
					<input id="tpl-image" type="text" bind:value={image} placeholder="예: postgres:15" />
				</div>

				<div class="field">
					<label for="tpl-image-opts">이미지 옵션 (JSON) <span class="hint">사용자가 선택할 이미지 변형</span></label>
					<textarea id="tpl-image-opts" bind:value={imageOptionsJson} rows="3"
						placeholder='[{{"label":"Postgres 13","image":"postgres:13"}}]'></textarea>
				</div>

				<div class="field">
					<label for="tpl-env">환경변수 스키마 (JSON) <span class="hint">사용자 입력 폼 자동 생성</span></label>
					<textarea id="tpl-env" bind:value={envSchemaJson} rows="5"
						placeholder='[{{"key":"POSTGRES_PASSWORD","required":true,"type":"password","description":"DB 비밀번호"}}]'></textarea>
				</div>

				<div class="field">
					<label for="tpl-ports">포트 스키마 (JSON)</label>
					<textarea id="tpl-ports" bind:value={portSchemaJson} rows="3"
						placeholder='[{{"internal":5432,"host_default":15432,"description":"DB port"}}]'></textarea>
				</div>

				<div class="field">
					<label for="tpl-vols">볼륨 (JSON)</label>
					<textarea id="tpl-vols" bind:value={defaultVolumesJson} rows="2"
						placeholder='["/var/data/pg:/var/lib/postgresql/data"]'></textarea>
				</div>
			{:else}
				<div class="field">
					<label for="tpl-yaml">docker-compose.yml *</label>
					<textarea id="tpl-yaml" bind:value={composeYaml} rows="12"
						placeholder="services:\n  web:\n    image: nginx:latest\n    ports:\n      - '8080:80'"></textarea>
				</div>

				<div class="field">
					<label for="tpl-env-compose">환경변수 스키마 (JSON) <span class="hint">compose 변수 치환용</span></label>
					<textarea id="tpl-env-compose" bind:value={envSchemaJson} rows="4"
						placeholder='[{{"key":"TAG","type":"text","default":"latest"}}]'></textarea>
				</div>
			{/if}
		</div>

		<div class="modal-footer">
			{#if errorMsg}
				<div class="error">{errorMsg}</div>
			{/if}
			<div class="action-row">
				<button class="btn-cancel" onclick={onClose}>취소</button>
				<button class="btn-save" disabled={busy} onclick={handleSave}>
					{busy ? '저장 중...' : (template ? '수정' : '생성')}
				</button>
			</div>
		</div>
	</div>
</div>
{/if}

<style>
	.overlay {
		position: fixed; inset: 0; z-index: 200;
		background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
		display: flex; align-items: center; justify-content: center;
	}
	.modal {
		width: 680px; max-width: 92vw; max-height: 90vh;
		background: var(--bg-card); border: 1px solid var(--border);
		border-radius: var(--radius-md);
		display: flex; flex-direction: column; overflow: hidden;
	}
	.modal-header {
		display: flex; justify-content: space-between; align-items: center;
		padding: 18px 22px; border-bottom: 1px solid var(--border);
	}
	.title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
	.close-btn { background: none; border: none; cursor: pointer; padding: 4px; display: flex; }
	.close-btn:hover svg { stroke: var(--text-primary); }

	.modal-content {
		flex: 1; overflow-y: auto;
		padding: 18px 22px 22px;
		display: flex; flex-direction: column; gap: 14px;
	}

	.field { display: flex; flex-direction: column; gap: 4px; }
	.field label {
		font-size: 12px; font-weight: 600; color: var(--text-secondary);
	}
	.hint { font-weight: 400; color: var(--text-muted); font-size: 10px; }
	.field input, .field textarea, .field select {
		background: var(--bg-base); border: 1px solid var(--border);
		border-radius: var(--radius-sm); padding: 8px 12px;
		color: var(--text-primary); font-family: 'JetBrains Mono', monospace;
		font-size: 12px; resize: vertical;
	}
	.field input:focus, .field textarea:focus, .field select:focus {
		outline: none; border-color: var(--accent);
	}
	.netpolicy-warn {
		margin-top: 4px;
		padding: 6px 8px;
		border-radius: var(--radius-sm);
		background: var(--state-warn-bg, rgba(234, 179, 8, 0.12));
		color: var(--state-warn-fg, #b45309);
		font-size: 11px;
		line-height: 1.5;
	}

	.kind-toggle {
		display: flex; gap: 2px; background: var(--bg-base);
		border-radius: var(--radius-md); padding: 3px;
	}
	.kind-toggle button {
		flex: 1; background: none; border: none; color: var(--text-secondary);
		padding: 7px 12px; font-size: 12px; cursor: pointer;
		border-radius: var(--radius-sm); font-family: inherit;
	}
	.kind-toggle button:hover { color: var(--text-primary); }
	.kind-toggle button.active {
		background: var(--accent); color: var(--bg-base); font-weight: 600;
	}

	.modal-footer {
		padding: 14px 22px; border-top: 1px solid var(--border);
		display: flex; flex-direction: column; gap: 8px;
	}
	.error { font-size: 12px; color: var(--error); }
	.action-row { display: flex; justify-content: flex-end; gap: 10px; }
	.btn-cancel, .btn-save {
		padding: 8px 18px; border-radius: var(--radius-sm);
		font-size: 13px; font-weight: 600; cursor: pointer; font-family: inherit;
	}
	.btn-cancel {
		background: var(--bg-tab); border: 1px solid var(--border); color: var(--text-primary);
	}
	.btn-save {
		background: var(--accent); border: none; color: var(--bg-base);
	}
	.btn-save:hover:not(:disabled) { filter: brightness(1.1); }
	button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
