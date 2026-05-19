<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { browser } from '$app/environment';
	import TemplateEditorModal from '$lib/components/TemplateEditorModal.svelte';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';

	type TemplateRow = {
		id: string;
		name: string;
		kind: string;
		image: string;
		description: string;
		created_by_username: string;
		updated_at: string;
		[k: string]: any;
	};

	let templates = $state<TemplateRow[]>([]);
	let loading = $state(false);
	let errorMsg = $state('');

	let editorOpen = $state(false);
	let editTarget = $state<TemplateRow | null>(null);

	let deleteTarget = $state<TemplateRow | null>(null);
	let deleteConfirmOpen = $state(false);
	let deleting = $state(false);

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
			const res = await fetch(`${base}/api/templates/?page_size=100&ordering=name`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (!res.ok) { errorMsg = `HTTP ${res.status}`; return; }
			const json = await res.json();
			templates = json.data?.results ?? [];
		} catch (e: any) {
			errorMsg = e?.message || '로드 실패';
		} finally {
			loading = false;
		}
	}

	async function handleSave(data: any) {
		const t = token();
		if (!t) throw new Error('no token');
		const isEdit = !!editTarget;
		const url = isEdit ? `${base}/api/templates/${editTarget!.id}/` : `${base}/api/templates/`;
		const method = isEdit ? 'PATCH' : 'POST';
		const res = await fetch(url, {
			method,
			headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' },
			body: JSON.stringify(data),
		});
		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			const detail = body?.error ?? body?.detail ?? body;
			throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
		}
		await load();
	}

	function openCreate() {
		editTarget = null;
		editorOpen = true;
	}

	function openEdit(tpl: TemplateRow) {
		editTarget = tpl;
		editorOpen = true;
	}

	function openDeleteConfirm(tpl: TemplateRow) {
		deleteTarget = tpl;
		deleteConfirmOpen = true;
	}

	async function confirmDelete() {
		if (!deleteTarget || deleting) return;
		const t = token();
		if (!t) return;
		deleting = true;
		try {
			const res = await fetch(`${base}/api/templates/${deleteTarget.id}/`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${t}` },
			});
			if (!res.ok && res.status !== 204) {
				const body = await res.json().catch(() => ({}));
				errorMsg = body?.detail || `삭제 실패 (${res.status})`;
			}
			deleteConfirmOpen = false;
			deleteTarget = null;
			await load();
		} finally {
			deleting = false;
		}
	}

	function kindLabel(k: string): string {
		return k === 'compose' ? 'Compose' : 'Simple';
	}

	function formatTime(iso?: string): string {
		if (!iso) return '-';
		try { return new Date(iso).toLocaleDateString('ko-KR'); } catch { return iso; }
	}

	onMount(load);
</script>

<div class="page">
	<div class="page-header">
		<div>
			<h1>컨테이너 템플릿 <InfoTooltip text={"\"이 이미지를 이 옵션으로 띄우면 됩니다\"라는 미리 만든 묶음입니다.\n\n사용자는 컨테이너 생성을 요청할 때 직접 docker 옵션을 쓰지 않고 여기서 만든 템플릿을 골라 제출합니다.\n\n• 새 템플릿을 만들면 사용자 화면에 즉시 노출됩니다.\n• 잘못 만든 템플릿은 편집 또는 삭제할 수 있습니다 (사용 중인 요청이 있으면 삭제 불가)."} placement="bottom-start" /></h1>
			<p class="subtitle">사용자가 컨테이너 요청 시 선택할 수 있는 템플릿을 관리합니다.</p>
		</div>
		<button class="create-btn" onclick={openCreate} title="새 템플릿을 등록합니다. 이름·타입(Simple/Compose)·이미지·설명을 입력하면 즉시 사용자 화면에 표시됩니다.">+ 새 템플릿</button>
	</div>

	{#if errorMsg}
		<div class="error-box">{errorMsg}</div>
	{/if}

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>이름 <InfoTooltip text={"템플릿을 식별하는 사람이 읽기 쉬운 이름입니다.\n사용자 화면 \"컨테이너 생성\" 드롭다운에 그대로 노출됩니다.\n\n예: \"Postgres 16\", \"Nginx 정적 호스팅\"."} placement="bottom-start" /></th>
					<th class="col-kind">타입 <InfoTooltip text={"템플릿이 정의된 형식\n\n• Simple — 단일 이미지 + 기본 옵션 (docker run 한 번에 띄울 수 있는 컨테이너)\n• Compose — docker-compose.yml 형태 (여러 서비스를 묶음으로 띄워야 할 때)"} placement="bottom-start" /></th>
					<th>이미지 <InfoTooltip text={"Simple 타입일 때 사용할 도커 이미지 주소입니다 (예: postgres:16, nginx:alpine).\nCompose 타입은 yaml 안에 이미지가 여러 개 들어 있어 여기엔 \"(yaml)\"로 표시됩니다."} placement="bottom-start" /></th>
					<th>설명 <InfoTooltip text={"이 템플릿이 어떤 용도인지, 어떤 옵션을 쓰는지 사용자가 한 줄로 이해할 수 있게 적은 짧은 안내입니다.\n사용자 화면에서 템플릿 선택 시 함께 노출됩니다."} placement="bottom-start" /></th>
					<th class="col-author">작성자 <InfoTooltip text={"이 템플릿을 등록한 관리자 계정입니다."} placement="bottom-start" /></th>
					<th class="col-date">수정일 <InfoTooltip text={"이 템플릿이 마지막으로 만들어졌거나 편집된 날짜입니다.\n오래된 템플릿은 이미지 태그가 옛 버전으로 고정되어 있을 수 있으니 가끔 점검해 주세요."} placement="bottom-start" /></th>
					<th class="col-actions"></th>
				</tr>
			</thead>
			<tbody>
				{#if !loading && templates.length === 0}
					<tr class="empty-row">
						<td colspan="7">
							<div class="empty-inline">
								<div class="empty-icon">📦</div>
								<div class="empty-text">등록된 템플릿이 없습니다.</div>
								<button class="empty-btn" onclick={openCreate}>첫 템플릿 만들기</button>
							</div>
						</td>
					</tr>
				{:else}
					{#each templates as tpl (tpl.id)}
						<tr>
							<td class="name-cell">{tpl.name}</td>
							<td>
								<span class="kind-tag" class:compose={tpl.kind === 'compose'}>
									{kindLabel(tpl.kind)}
								</span>
							</td>
							<td class="mono">{tpl.kind === 'simple' ? (tpl.image || '-') : '(yaml)'}</td>
							<td class="desc-cell">{tpl.description || '-'}</td>
							<td>{tpl.created_by_username}</td>
							<td class="dim">{formatTime(tpl.updated_at)}</td>
							<td class="actions-cell">
								<button class="edit-btn" onclick={() => openEdit(tpl)}>편집</button>
								<button class="del-btn" onclick={() => openDeleteConfirm(tpl)}>삭제</button>
							</td>
						</tr>
					{/each}
				{/if}
			</tbody>
		</table>
	</div>
</div>

<TemplateEditorModal
	template={editTarget}
	open={editorOpen}
	onClose={() => { editorOpen = false; editTarget = null; }}
	onSave={handleSave}
/>

{#if deleteConfirmOpen && deleteTarget}
<div class="overlay" onclick={() => { deleteConfirmOpen = false; }} role="dialog">
	<div class="confirm-box" onclick={(e) => e.stopPropagation()}>
		<div class="confirm-title">템플릿 삭제</div>
		<p class="confirm-text">
			<strong>{deleteTarget.name}</strong> 템플릿을 삭제하시겠습니까?
			이 템플릿을 사용한 진행 중인 요청이 있으면 삭제할 수 없습니다.
		</p>
		<div class="confirm-actions">
			<button class="btn-cancel" onclick={() => { deleteConfirmOpen = false; }}>취소</button>
			<button class="btn-delete" disabled={deleting} onclick={confirmDelete}>
				{deleting ? '삭제 중...' : '삭제'}
			</button>
		</div>
	</div>
</div>
{/if}

<style>
	/* Layout-level :global() controls .page / .page-header / h1 / .subtitle /
	   .table-wrap / table / thead / tbody / .filter-btn / .refresh-btn /
	   .error-box / .empty so this panel only declares panel-specific styling. */
	.create-btn {
		background: var(--accent); color: var(--bg-base); border: none;
		padding: 9px 18px; border-radius: var(--radius-sm);
		font-size: 13px; font-weight: 600; cursor: pointer; font-family: inherit;
		white-space: nowrap;
	}
	.create-btn:hover { filter: brightness(1.1); }
	.empty-btn {
		background: var(--accent); color: var(--bg-base); border: none;
		padding: 8px 16px; border-radius: var(--radius-sm);
		font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit;
	}

	.name-cell { font-weight: 600; color: var(--text-primary); }
	.desc-cell { color: var(--text-secondary); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.mono { font-family: 'JetBrains Mono', monospace; font-size: 11px; }
	.dim { color: var(--text-muted); }

	.kind-tag {
		display: inline-block; padding: 2px 8px; border-radius: 4px;
		background: rgba(48,213,200,0.15); color: var(--accent);
		font-size: 11px; font-weight: 600; white-space: nowrap;
	}
	.kind-tag.compose {
		background: rgba(139,92,246,0.15); color: #a78bfa;
	}

	.col-kind { width: 90px; }
	.col-author { width: 90px; }
	.col-date { width: 90px; }
	.col-actions { width: 130px; text-align: right; }
	.actions-cell { display: flex; gap: 6px; justify-content: flex-end; }

	.edit-btn, .del-btn {
		background: var(--bg-tab); border: 1px solid var(--border);
		color: var(--text-primary); padding: 4px 10px; font-size: 11px;
		border-radius: var(--radius-sm); cursor: pointer; font-family: inherit;
	}
	.edit-btn:hover { border-color: var(--accent); }
	.del-btn { color: var(--error); border-color: rgba(239,68,68,0.3); }
	.del-btn:hover { background: rgba(239,68,68,0.1); border-color: var(--error); }

	.overlay {
		position: fixed; inset: 0; z-index: 200;
		background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
		display: flex; align-items: center; justify-content: center;
	}
	.confirm-box {
		background: var(--bg-card); border: 1px solid var(--border);
		border-radius: var(--radius-md); padding: 24px; max-width: 420px; width: 90%;
	}
	.confirm-title { font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 10px; }
	.confirm-text { font-size: 13px; color: var(--text-secondary); margin: 0 0 18px; line-height: 1.5; }
	.confirm-actions { display: flex; justify-content: flex-end; gap: 10px; }
	.btn-cancel {
		background: var(--bg-tab); border: 1px solid var(--border); color: var(--text-primary);
		padding: 8px 16px; border-radius: var(--radius-sm); font-size: 13px; cursor: pointer; font-family: inherit;
	}
	.btn-delete {
		background: var(--error); border: none; color: white;
		padding: 8px 16px; border-radius: var(--radius-sm); font-size: 13px;
		font-weight: 600; cursor: pointer; font-family: inherit;
	}
	.btn-delete:hover:not(:disabled) { filter: brightness(1.1); }
	button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
