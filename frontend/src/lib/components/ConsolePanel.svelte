<!--
  ConsolePanel — 컨테이너 내부 shell (B4 Console exec). 멀티 세션 / 탭 지원.

  /ws/server/<agent_id>/ 로 세션마다 자체 WS 를 열어 exec_open → exec_chunk 를
  xterm 으로 write. 세션마다 독립된 execId, term, ws, mountEl.

  설계 결정
  ---------
  · 세션 1개 = WS 1개 (격리). 한 세션이 끊겨도 다른 세션 영향 X.
  · 비활성 탭의 term 은 unmount 하지 않고 display:none 으로 숨김 — 백그라운드에서
    들어오는 chunk 가 buffer 되어 탭 전환 시 즉시 보임.
  · 탭 닫기 = 그 세션의 exec_close + WS close + term.dispose. 마지막 탭 닫으면
    sessions 비어 placeholder 표시.
  · reactive (sessions[]) 와 non-reactive (handles: ws/term/fitAddon/mountEl) 분리.
    xterm/WebSocket 같이 큰 객체를 $state proxy 에 넣어 reactivity 가 깊은 순회
    하지 않게 한다.

  Portainer 모델: 명령 차단 없음, 키스트로크 미기록. session audit 은 backend.
-->
<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';

	let {
		agentId,
		containerId,
		startOpen = false,
	}: {
		agentId: string;
		containerId: string;
		startOpen?: boolean;
	} = $props();

	type SessionStatus = 'connecting' | 'active' | 'ended' | 'error';

	type SessionView = {
		id: string; // = execId
		label: string;
		shell: 'sh' | 'bash';
		user: string;
		status: SessionStatus;
		connected: boolean;
		ready: boolean;
		errorMsg: string;
		endedReason: string | null;
		exitCode: number | null;
	};

	type SessionHandle = {
		ws: WebSocket | null;
		term: any;
		fitAddon: any;
		mountEl: HTMLDivElement | null;
		resizeObs: ResizeObserver | null;
	};

	let open = $state(startOpen);
	let sessions = $state<SessionView[]>([]);
	let activeId = $state<string | null>(null);
	let nextOrdinal = $state(1);

	// non-reactive: 큰 비-serializable 객체. Map 으로 분리해 svelte reactivity 가 깊이
	// 순회하지 않게 한다.
	const handles = new Map<string, SessionHandle>();

	let mountedShellPref = $state<'sh' | 'bash'>('sh');
	let mountedUserPref = $state<string>('');

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	function uuid(): string {
		const r = (n: number) => Math.floor(Math.random() * n);
		const hex = (n: number) =>
			Array.from({ length: n }, () => r(16).toString(16)).join('');
		return `${hex(8)}-${hex(4)}-4${hex(3)}-${(8 + r(4)).toString(16)}${hex(3)}-${hex(12)}`;
	}

	function wsUrl(): string {
		const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
		const host = window.location.host;
		return `${proto}://${host}${base}/ws/server/${agentId}/`;
	}

	function bytesToB64(bytes: Uint8Array): string {
		let bin = '';
		for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
		return btoa(bin);
	}
	function b64ToBytes(b64: string): Uint8Array {
		const bin = atob(b64);
		const arr = new Uint8Array(bin.length);
		for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
		return arr;
	}
	function strToB64(s: string): string {
		return bytesToB64(new TextEncoder().encode(s));
	}

	function makeLabel(shell: string, user: string, ordinal: number): string {
		const u = user ? user : '(default)';
		return `${shell} · ${u} · #${ordinal}`;
	}

	function getSession(id: string): SessionView | undefined {
		return sessions.find((s) => s.id === id);
	}
	function patchSession(id: string, patch: Partial<SessionView>) {
		sessions = sessions.map((s) => (s.id === id ? { ...s, ...patch } : s));
	}

	async function ensureTerm(id: string) {
		const h = handles.get(id);
		if (!h || h.term) return;
		// mountEl 이 아직 mount 안 된 시점에 호출될 수 있다. Svelte 가 DOM patch 끝낼
		// 때까지 대기.
		if (!h.mountEl) {
			await tick();
		}
		const el = h.mountEl;
		if (!el) return;
		const [{ Terminal }, { FitAddon }] = await Promise.all([
			import('@xterm/xterm'),
			import('@xterm/addon-fit'),
		]);
		await import('@xterm/xterm/css/xterm.css');

		const term = new Terminal({
			cursorBlink: true,
			fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace',
			fontSize: 12,
			theme: {
				background: '#02060c',
				foreground: '#cbd5e1',
				cursor: '#30d5c8',
				selectionBackground: 'rgba(48, 213, 200, 0.3)',
			},
			scrollback: 5000,
			convertEol: false,
		});
		const fitAddon = new FitAddon();
		term.loadAddon(fitAddon);
		term.open(el);
		fitAddon.fit();

		term.onData((data: string) => {
			const hh = handles.get(id);
			const ws = hh?.ws;
			if (!ws || ws.readyState !== WebSocket.OPEN) return;
			ws.send(JSON.stringify({
				type: 'command',
				requestId: uuid(),
				command: 'exec_input',
				params: { execId: id, data: strToB64(data) },
			}));
		});

		const resizeObs = new ResizeObserver(() => {
			try {
				fitAddon.fit();
				const hh = handles.get(id);
				if (hh?.ws?.readyState === WebSocket.OPEN) {
					hh.ws.send(JSON.stringify({
						type: 'command',
						requestId: uuid(),
						command: 'exec_resize',
						params: { execId: id, cols: term.cols, rows: term.rows },
					}));
				}
			} catch {
				/* ignore */
			}
		});
		resizeObs.observe(el);

		h.term = term;
		h.fitAddon = fitAddon;
		h.resizeObs = resizeObs;
	}

	async function startSession(id: string) {
		const view = getSession(id);
		const h = handles.get(id);
		if (!view || !h || h.ws) return;
		patchSession(id, { errorMsg: '', endedReason: null, exitCode: null, ready: false, status: 'connecting' });

		await ensureTerm(id);

		const t = token();
		if (!t) {
			patchSession(id, { errorMsg: '로그인이 필요합니다.', status: 'error' });
			return;
		}

		const ws = new WebSocket(wsUrl(), ['hypercube.jwt', t]);
		h.ws = ws;
		ws.onopen = () => {
			patchSession(id, { connected: true });
			sendOpen(id);
		};
		ws.onmessage = (ev) => {
			let msg: any;
			try {
				msg = JSON.parse(ev.data);
			} catch {
				return;
			}
			handleMessage(id, msg);
		};
		ws.onerror = () => {
			patchSession(id, { errorMsg: 'WebSocket 에러', status: 'error' });
		};
		ws.onclose = () => {
			patchSession(id, { connected: false, ready: false });
			const hh = handles.get(id);
			if (hh) hh.ws = null;
		};
	}

	function sendOpen(id: string) {
		const view = getSession(id);
		const h = handles.get(id);
		if (!view || !h?.ws || h.ws.readyState !== WebSocket.OPEN || !h.term) return;
		const cmd = view.shell === 'bash' ? ['/bin/bash'] : ['/bin/sh'];
		h.ws.send(JSON.stringify({
			type: 'command',
			requestId: id, // execId 로 매핑
			command: 'exec_open',
			params: {
				containerId,
				cmd,
				user: view.user || undefined,
				tty: true,
				cols: h.term.cols,
				rows: h.term.rows,
			},
		}));
	}

	function sendClose(id: string) {
		const h = handles.get(id);
		if (!h?.ws || h.ws.readyState !== WebSocket.OPEN) return;
		h.ws.send(JSON.stringify({
			type: 'command',
			requestId: uuid(),
			command: 'exec_close',
			params: { execId: id },
		}));
	}

	function teardownSession(id: string) {
		sendClose(id);
		const h = handles.get(id);
		if (h) {
			try {
				h.ws?.close();
			} catch {
				/* ignore */
			}
			try {
				h.resizeObs?.disconnect();
			} catch {
				/* ignore */
			}
			try {
				h.term?.dispose();
			} catch {
				/* ignore */
			}
			handles.delete(id);
		}
	}

	function handleMessage(id: string, msg: any) {
		const t = msg?.type;
		const h = handles.get(id);
		if (!h) return;
		if (t === 'command_response' && msg.requestId === id) {
			if (msg.success) {
				patchSession(id, { ready: true, status: 'active' });
			} else {
				patchSession(id, {
					errorMsg: msg.error || 'exec_open failed',
					ready: false,
					status: 'error',
				});
			}
			return;
		}
		if (t === 'exec_chunk' && msg.execId === id) {
			if (h.term && typeof msg.data === 'string') {
				try {
					h.term.write(b64ToBytes(msg.data));
				} catch {
					/* ignore decode errors */
				}
			}
			return;
		}
		if (t === 'exec_end' && msg.execId === id) {
			const endedReason = msg.reason || 'ended';
			const exitCode = typeof msg.exitCode === 'number' ? msg.exitCode : null;
			patchSession(id, {
				endedReason,
				exitCode,
				ready: false,
				status: 'ended',
			});
			if (h.term) {
				h.term.write(
					`\r\n\x1b[33m[session ended: ${endedReason}${exitCode !== null ? `, exit ${exitCode}` : ''}]\x1b[0m\r\n`,
				);
			}
			return;
		}
	}

	function newSession(shell: 'sh' | 'bash' = mountedShellPref, user: string = mountedUserPref) {
		const id = uuid();
		const ordinal = nextOrdinal;
		nextOrdinal = nextOrdinal + 1;
		const view: SessionView = {
			id,
			label: makeLabel(shell, user, ordinal),
			shell,
			user,
			status: 'connecting',
			connected: false,
			ready: false,
			errorMsg: '',
			endedReason: null,
			exitCode: null,
		};
		handles.set(id, { ws: null, term: null, fitAddon: null, mountEl: null, resizeObs: null });
		sessions = [...sessions, view];
		activeId = id;
		// mount 직후 DOM 이 생성된 다음 cycle 에 ws/term 시작.
		queueMicrotask(() => startSession(id));
	}

	function closeSession(id: string) {
		teardownSession(id);
		const wasActive = activeId === id;
		sessions = sessions.filter((s) => s.id !== id);
		if (wasActive) {
			activeId = sessions.length > 0 ? sessions[sessions.length - 1].id : null;
		}
	}

	function selectSession(id: string) {
		activeId = id;
		// 활성 전환 직후 fit — 비활성으로 숨겨져 있던 term 의 dimension 재계산.
		queueMicrotask(() => {
			const h = handles.get(id);
			try {
				h?.fitAddon?.fit();
			} catch {
				/* ignore */
			}
		});
	}

	function togglePanel() {
		open = !open;
		if (open && sessions.length === 0) {
			// 패널을 처음 열면 자동으로 한 세션 시작 — 기존 단일-세션 UX 와 동일.
			newSession();
		}
		if (!open) {
			// 닫을 때 모든 세션 종료. 다시 열면 새로 시작.
			for (const s of sessions) teardownSession(s.id);
			sessions = [];
			activeId = null;
		}
	}

	// Svelte action — 각 termbox <div> 가 mount/unmount 될 때 handles 에 등록/해제.
	// each loop 안에서 동적 id 매핑이라 bind:this 보다 use:action 이 깔끔.
	function termMount(node: HTMLDivElement, id: string) {
		const h = handles.get(id);
		if (h) h.mountEl = node;
		return {
			destroy() {
				const hh = handles.get(id);
				if (hh && hh.mountEl === node) hh.mountEl = null;
			},
		};
	}

	function statusLabel(s: SessionView): string {
		if (s.errorMsg) return `에러: ${s.errorMsg}`;
		if (s.endedReason) return `종료 (${s.endedReason}${s.exitCode !== null ? `, exit ${s.exitCode}` : ''})`;
		if (s.ready) return '● 활성';
		if (s.connected) return '◌ 연결 중...';
		return '◌ 끊김';
	}

	function statusClass(s: SessionView): string {
		if (s.errorMsg || s.endedReason) return 'err';
		if (s.ready) return 'ok';
		return '';
	}

	onMount(() => {
		if (open && sessions.length === 0) newSession();
	});

	onDestroy(() => {
		for (const s of sessions) teardownSession(s.id);
	});

	let activeSession = $derived(sessions.find((s) => s.id === activeId) ?? null);
</script>

<section class="panel" class:closed={!open}>
	<div class="panel-header slim" class:closed-row={!open}>
		<div>
			<h2>콘솔 (exec)</h2>
			{#if open}
				<p>컨테이너 안에 shell 을 띄워 명령 실행. 탭을 닫으면 그 세션만 종료됩니다.</p>
			{/if}
		</div>
		<button class="toggle" class:on={open} onclick={togglePanel}>
			{open ? '닫기' : '열기'}
		</button>
	</div>

	{#if open}
		<!-- 탭 바: 세션 목록 + "+ 새 세션" -->
		<div class="tab-bar" role="tablist" aria-label="콘솔 세션">
			{#each sessions as s (s.id)}
				<div
					class="tab"
					class:active={s.id === activeId}
					class:err={s.status === 'error' || !!s.endedReason}
					role="tab"
					aria-selected={s.id === activeId}
				>
					<button
						type="button"
						class="tab-label"
						onclick={() => selectSession(s.id)}
						title={s.label}
					>
						<span class="tab-dot" data-status={s.status} aria-hidden="true"></span>
						<span class="tab-text">{s.label}</span>
					</button>
					<button
						type="button"
						class="tab-close"
						onclick={() => closeSession(s.id)}
						aria-label="세션 닫기"
						title="세션 닫기"
					>×</button>
				</div>
			{/each}
			<button type="button" class="tab-new" onclick={() => newSession()} title="새 세션 시작">+ 새 세션</button>
		</div>

		<!-- 활성 세션 toolbar (옵션·상태) -->
		{#if activeSession}
			{@const s = activeSession}
			<div class="toolbar">
				<span class="status" class:ok={statusClass(s) === 'ok'} class:err={statusClass(s) === 'err'}>
					{statusLabel(s)}
				</span>
				<label class="sel">
					shell
					<select
						value={s.shell}
						onchange={(e) => {
							mountedShellPref = (e.currentTarget as HTMLSelectElement).value as 'sh' | 'bash';
						}}
						disabled
						title="신규 세션에 적용되는 기본값입니다. 시작된 세션의 shell 은 변경되지 않습니다."
					>
						<option value="sh">/bin/sh</option>
						<option value="bash">/bin/bash</option>
					</select>
				</label>
				<label class="sel">
					user
					<input
						type="text"
						placeholder="(default)"
						value={s.user}
						disabled
						title="신규 세션에 적용되는 기본값입니다. 시작된 세션의 user 는 변경되지 않습니다."
					/>
				</label>
			</div>
		{/if}

		<!-- 새 세션 기본값 (sessions 비어 있을 때 입력 받기) -->
		{#if sessions.length === 0}
			<div class="empty-state">
				<button type="button" class="empty-cta" onclick={() => newSession()}>
					<span class="placeholder-icon">›_</span>
					<span class="placeholder-title">새 세션 시작</span>
					<span class="placeholder-desc">컨테이너 안에 shell 을 띄워 명령을 실행합니다.</span>
				</button>
				<div class="empty-prefs">
					<label class="sel">
						shell
						<select bind:value={mountedShellPref}>
							<option value="sh">/bin/sh</option>
							<option value="bash">/bin/bash</option>
						</select>
					</label>
					<label class="sel">
						user
						<input type="text" placeholder="(default)" bind:value={mountedUserPref} />
					</label>
				</div>
			</div>
		{/if}

		<!-- 모든 세션의 term — 활성만 보이고 나머지는 hidden (DOM/buffer 유지) -->
		<div class="term-stack" class:has-sessions={sessions.length > 0}>
			{#each sessions as s (s.id)}
				<div
					class="termbox"
					class:visible={s.id === activeId}
					use:termMount={s.id}
				></div>
			{/each}
		</div>
	{/if}
</section>

<style>
	.panel {
		background:
			linear-gradient(180deg, rgba(21, 27, 38, 0.98), rgba(7, 12, 20, 0.98)),
			rgba(18, 23, 32, 0.96);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: var(--radius-panel);
		padding: clamp(5px, 0.45vw, 8px);
		transition: border-color var(--ease-fast);
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		height: 100%;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
		position: relative;
		box-shadow:
			0 8px 24px rgba(0, 0, 0, 0.16),
			inset 0 1px 0 rgba(255, 255, 255, 0.025);
	}
	.panel::before {
		content: '';
		position: absolute;
		inset: 0 0 auto;
		height: 2px;
		background: linear-gradient(90deg, rgba(48, 213, 200, 0.6), rgba(167, 139, 250, 0.16));
		opacity: 0.72;
	}
	.panel:hover {
		border-color: rgba(48, 213, 200, 0.22);
	}
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
		margin-bottom: 5px;
		padding-bottom: 5px;
		border-bottom: 1px solid rgba(100, 116, 139, 0.12);
		flex: 0 0 auto;
	}
	.panel-header.closed-row {
		align-items: center;
		margin-bottom: 0;
	}
	.panel-header.closed-row h2 {
		margin-bottom: 0;
		font-size: clamp(12px, 0.8vw, 14px);
	}
	.panel-header.closed-row h2::before {
		content: '›_ ';
		color: var(--accent);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		opacity: 0.7;
		margin-right: 6px;
	}
	.panel.closed {
		padding: clamp(5px, 0.45vw, 9px) clamp(8px, 0.7vw, 14px);
		border-color: rgba(48, 213, 200, 0.22);
		background:
			linear-gradient(90deg, rgba(48, 213, 200, 0.06), rgba(18, 23, 32, 0.96) 40%),
			rgba(18, 23, 32, 0.96);
	}
	.panel.closed:hover {
		border-color: rgba(48, 213, 200, 0.45);
	}
	.panel.closed .toggle {
		padding: 5px 12px;
		font-size: 11px;
	}
	h2 {
		font-size: 14px;
		margin-bottom: 0;
		letter-spacing: -0.01em;
	}
	.panel-header p {
		display: none;
		font-size: 11px;
		color: var(--text-secondary);
	}

	.toggle {
		padding: 5px 9px;
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: inherit;
		font-size: 10.5px;
		font-weight: 700;
		cursor: pointer;
	}
	.toggle.on {
		background: rgba(48, 213, 200, 0.18);
		border-color: rgba(48, 213, 200, 0.4);
		color: var(--accent);
	}

	/* 탭 바 */
	.tab-bar {
		display: flex;
		gap: 3px;
		align-items: center;
		min-width: 0;
		max-width: 100%;
		overflow-x: auto;
		padding: 3px;
		margin-bottom: 5px;
		background: rgba(2, 6, 12, 0.45);
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-radius: 8px;
		scrollbar-width: thin;
		flex: 0 0 auto;
	}
	.tab {
		display: inline-flex;
		align-items: center;
		gap: 2px;
		padding: 0;
		border-radius: 6px;
		background: transparent;
		max-width: 220px;
		min-width: 0;
		flex: 0 0 auto;
	}
	.tab.active {
		background: rgba(48, 213, 200, 0.16);
		box-shadow: inset 0 0 0 1px rgba(48, 213, 200, 0.3);
	}
	.tab.err.active {
		background: rgba(239, 68, 68, 0.15);
		box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.35);
	}
	.tab-label {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 4px 8px;
		background: transparent;
		border: 0;
		color: var(--text-muted);
		font: inherit;
		font-size: 10.5px;
		font-weight: 700;
		letter-spacing: 0.01em;
		cursor: pointer;
		max-width: 180px;
	}
	.tab.active .tab-label { color: var(--accent); }
	.tab.err .tab-label { color: #fca5a5; }
	.tab-text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}
	.tab-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: rgba(100, 116, 139, 0.4);
		flex: 0 0 auto;
	}
	.tab-dot[data-status='active']     { background: #34d399; box-shadow: 0 0 4px rgba(52, 211, 153, 0.55); }
	.tab-dot[data-status='connecting'] { background: #fbbf24; }
	.tab-dot[data-status='ended']      { background: rgba(148, 163, 184, 0.6); }
	.tab-dot[data-status='error']      { background: #f87171; box-shadow: 0 0 4px rgba(239, 68, 68, 0.55); }
	.tab-close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 18px;
		height: 18px;
		border: 0;
		border-radius: 4px;
		background: transparent;
		color: var(--text-muted);
		font: inherit;
		font-size: 14px;
		font-weight: 700;
		line-height: 1;
		cursor: pointer;
		margin-right: 3px;
	}
	.tab-close:hover {
		background: rgba(239, 68, 68, 0.2);
		color: #fca5a5;
	}
	.tab-new {
		padding: 4px 9px;
		margin-left: auto;
		border: 1px dashed rgba(48, 213, 200, 0.35);
		border-radius: 6px;
		background: transparent;
		color: var(--accent);
		font: inherit;
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.02em;
		cursor: pointer;
		white-space: nowrap;
		flex: 0 0 auto;
	}
	.tab-new:hover {
		background: rgba(48, 213, 200, 0.12);
		border-color: rgba(48, 213, 200, 0.6);
	}

	.toolbar {
		display: flex;
		flex-wrap: wrap;
		gap: 5px;
		align-items: center;
		min-width: 0;
		max-width: 100%;
		box-sizing: border-box;
		margin-bottom: 5px;
		padding: 5px 6px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.5);
		border: 1px solid rgba(100, 116, 139, 0.16);
		flex: 0 0 auto;
	}
	.status {
		font-size: 10px;
		font-weight: 700;
		padding: 3px 7px;
		border-radius: 999px;
		background: rgba(100, 116, 139, 0.16);
		color: var(--text-secondary);
		border: 1px solid rgba(100, 116, 139, 0.32);
	}
	.status.ok {
		background: rgba(16, 185, 129, 0.18);
		color: #34d399;
		border-color: rgba(16, 185, 129, 0.35);
	}
	.status.err {
		background: rgba(239, 68, 68, 0.18);
		color: #fca5a5;
		border-color: rgba(239, 68, 68, 0.4);
	}

	.sel {
		display: inline-flex;
		gap: 4px;
		align-items: center;
		font-size: 10px;
		color: var(--text-secondary);
	}
	.sel select,
	.sel input {
		padding: 3px 6px;
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: inherit;
		font-size: 10px;
	}

	/* 빈 상태 placeholder + 신규 세션 prefs */
	.empty-state {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 0;
	}
	.empty-cta {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 10px;
		padding: 22px 18px;
		min-height: 140px;
		border: 1px dashed rgba(48, 213, 200, 0.28);
		border-radius: 12px;
		background: rgba(48, 213, 200, 0.04);
		color: var(--text-secondary);
		font-family: inherit;
		cursor: pointer;
		transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
	}
	.empty-cta:hover {
		background: rgba(48, 213, 200, 0.1);
		border-color: rgba(48, 213, 200, 0.5);
		color: var(--accent);
	}
	.placeholder-icon {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 22px;
		line-height: 1;
		color: var(--accent);
		opacity: 0.8;
	}
	.placeholder-title {
		font-size: 13px;
		font-weight: 800;
		color: var(--text-primary);
	}
	.placeholder-desc {
		font-size: 11px;
		color: var(--text-muted);
		text-align: center;
	}
	.empty-prefs {
		display: flex;
		gap: 8px;
		justify-content: center;
		flex: 0 0 auto;
	}

	/* termbox 스택 — 비활성 세션은 hidden 으로 DOM 유지 (xterm buffer 보존) */
	.term-stack {
		position: relative;
		flex: 1 1 0;
		min-height: 0;
		min-width: 0;
		display: flex;
	}
	.term-stack:not(.has-sessions) { display: none; }
	.termbox {
		position: absolute;
		inset: 0;
		padding: 7px;
		border-radius: 8px;
		background: linear-gradient(180deg, #02060c, #020812);
		border: 1px solid rgba(100, 116, 139, 0.18);
		overflow: hidden;
		visibility: hidden;
	}
	.termbox.visible {
		visibility: visible;
	}

	.termbox :global(.xterm) {
		height: 100%;
	}
	.termbox :global(.xterm-viewport) {
		background: transparent !important;
	}
</style>
