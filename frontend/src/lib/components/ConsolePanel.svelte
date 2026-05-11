<!--
  ConsolePanel — 컨테이너 내부에 web 기반 shell 을 띄움 (B4 Console exec).

  /ws/server/<agent_id>/ 로 자체 WS 를 열어 exec_open 발행 → exec_chunk 메시지를
  xterm 으로 write, term.onData 를 base64 encode 해 exec_input 발송. fit addon 으로
  컨테이너 크기에 맞춰 exec_resize 전달. unmount / 닫기 시 exec_close + WS close.

  Portainer 모델: console 권한 = full shell 권한. 명령 차단 없음. 키스트로크 미기록.
  세션 audit 은 backend ConsoleSession 모델에서 처리.
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

	let open = $state(startOpen);
	let ws: WebSocket | null = null;
	let execId = $state<string | null>(null);
	let term: any = null;
	let fitAddon: any = null;
	let termEl: HTMLDivElement | undefined = $state(undefined);
	let resizeObs: ResizeObserver | null = null;

	let connected = $state(false);
	let ready = $state(false);
	let endedReason = $state<string | null>(null);
	let exitCode = $state<number | null>(null);
	let errorMsg = $state('');

	let shellCmd = $state<'sh' | 'bash'>('sh');
	let execUser = $state('');

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
		const t = token();
		const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
		const host = window.location.host;
		return `${proto}://${host}${base}/ws/server/${agentId}/?token=${encodeURIComponent(t || '')}`;
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

	async function ensureTerm() {
		if (term) return;
		// open=true 직후 호출되면 {:else} 블록의 <div bind:this={termEl}> 가
		// 아직 mount 안 됐을 수 있다. Svelte 가 DOM patch 끝낼 때까지 대기.
		if (!termEl) {
			await tick();
		}
		if (!termEl) return;
		const [{ Terminal }, { FitAddon }] = await Promise.all([
			import('@xterm/xterm'),
			import('@xterm/addon-fit'),
		]);
		await import('@xterm/xterm/css/xterm.css');

		term = new Terminal({
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
		fitAddon = new FitAddon();
		term.loadAddon(fitAddon);
		term.open(termEl);
		fitAddon.fit();

		term.onData((data: string) => {
			if (!execId || !ws || ws.readyState !== WebSocket.OPEN) return;
			ws.send(JSON.stringify({
				type: 'command',
				requestId: uuid(),
				command: 'exec_input',
				params: { execId, data: strToB64(data) },
			}));
		});

		resizeObs = new ResizeObserver(() => {
			try {
				fitAddon?.fit();
				if (term && execId && ws && ws.readyState === WebSocket.OPEN) {
					ws.send(JSON.stringify({
						type: 'command',
						requestId: uuid(),
						command: 'exec_resize',
						params: { execId, cols: term.cols, rows: term.rows },
					}));
				}
			} catch {
				/* ignore */
			}
		});
		resizeObs.observe(termEl);
	}

	async function startSession() {
		if (ws) return;
		errorMsg = '';
		endedReason = null;
		exitCode = null;
		ready = false;

		await ensureTerm();

		ws = new WebSocket(wsUrl());
		ws.onopen = () => {
			connected = true;
			sendOpen();
		};
		ws.onmessage = (ev) => {
			let msg: any;
			try {
				msg = JSON.parse(ev.data);
			} catch {
				return;
			}
			handleMessage(msg);
		};
		ws.onerror = () => {
			errorMsg = 'WebSocket 에러';
		};
		ws.onclose = () => {
			connected = false;
			ready = false;
			ws = null;
		};
	}

	function sendOpen() {
		if (!ws || ws.readyState !== WebSocket.OPEN || !term) return;
		execId = uuid();
		const cmd = shellCmd === 'bash' ? ['/bin/bash'] : ['/bin/sh'];
		ws.send(JSON.stringify({
			type: 'command',
			requestId: execId,
			command: 'exec_open',
			params: {
				containerId,
				cmd,
				user: execUser || undefined,
				tty: true,
				cols: term.cols,
				rows: term.rows,
			},
		}));
	}

	function sendClose() {
		if (!ws || ws.readyState !== WebSocket.OPEN || !execId) return;
		ws.send(JSON.stringify({
			type: 'command',
			requestId: uuid(),
			command: 'exec_close',
			params: { execId },
		}));
	}

	function stopSession() {
		sendClose();
		try {
			ws?.close();
		} catch {
			/* ignore */
		}
		ws = null;
		execId = null;
		connected = false;
		ready = false;
	}

	function handleMessage(msg: any) {
		const t = msg?.type;
		if (t === 'command_response' && msg.requestId === execId) {
			if (msg.success) {
				ready = true;
			} else {
				errorMsg = msg.error || 'exec_open failed';
				ready = false;
			}
			return;
		}
		if (t === 'exec_chunk' && msg.execId === execId) {
			if (term && typeof msg.data === 'string') {
				try {
					term.write(b64ToBytes(msg.data));
				} catch {
					/* ignore decode errors */
				}
			}
			return;
		}
		if (t === 'exec_end' && msg.execId === execId) {
			endedReason = msg.reason || 'ended';
			exitCode = typeof msg.exitCode === 'number' ? msg.exitCode : null;
			ready = false;
			if (term) term.write(`\r\n\x1b[33m[session ended: ${endedReason}${exitCode !== null ? `, exit ${exitCode}` : ''}]\x1b[0m\r\n`);
			return;
		}
	}

	function togglePanel() {
		open = !open;
		if (open) {
			startSession();
		} else {
			stopSession();
		}
	}

	function restart() {
		stopSession();
		if (term) {
			term.reset();
		}
		setTimeout(() => startSession(), 100);
	}

	onMount(() => {
		if (open) startSession();
	});

	onDestroy(() => {
		stopSession();
		try {
			resizeObs?.disconnect();
		} catch {
			/* ignore */
		}
		try {
			term?.dispose();
		} catch {
			/* ignore */
		}
		term = null;
		fitAddon = null;
	});
</script>

<section class="panel" class:closed={!open}>
	<div class="panel-header slim">
		<div>
			<h2>콘솔 (exec)</h2>
			<p>컨테이너 내부에 shell 을 띄워 직접 명령을 실행. 패널을 열면 새 exec 세션이 시작되고, 닫으면 정리됩니다.</p>
		</div>
		<button class="toggle" class:on={open} onclick={togglePanel}>
			{open ? '닫기' : '열기'}
		</button>
	</div>

	{#if !open}
		<button class="placeholder" onclick={togglePanel} aria-label="콘솔 세션 시작">
			<span class="placeholder-icon">›_</span>
			<span class="placeholder-title">콘솔 세션 시작</span>
			<span class="placeholder-desc">클릭하면 컨테이너 안에 shell 이 열립니다.<br />세션은 audit 로그에 기록됩니다.</span>
		</button>
	{:else}
		<div class="toolbar">
			<span class="status" class:ok={ready} class:err={!!errorMsg || endedReason}>
				{#if errorMsg}
					에러: {errorMsg}
				{:else if endedReason}
					종료됨 ({endedReason}{exitCode !== null ? `, exit ${exitCode}` : ''})
				{:else if ready}
					● 활성
				{:else if connected}
					◌ 연결 중...
				{:else}
					◌ 끊김
				{/if}
			</span>
			<label class="sel">
				shell
				<select bind:value={shellCmd} disabled={ready || connected}>
					<option value="sh">/bin/sh</option>
					<option value="bash">/bin/bash</option>
				</select>
			</label>
			<label class="sel">
				user
				<input
					type="text"
					placeholder="(기본)"
					bind:value={execUser}
					disabled={ready || connected}
				/>
			</label>
			<button class="btn" onclick={restart}>재시작</button>
		</div>

		<div class="termbox" bind:this={termEl}></div>
	{/if}
</section>

<style>
	.panel {
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		border-radius: 18px;
		padding: 20px;
	}
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 18px;
		margin-bottom: 14px;
	}
	h2 {
		font-size: 20px;
		margin-bottom: 4px;
	}
	.panel-header p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.panel.closed {
		display: flex;
		flex-direction: column;
		min-height: 0;
		height: 100%;
	}

	.placeholder {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		padding: 32px 20px;
		min-height: 200px;
		border: 1px dashed rgba(48, 213, 200, 0.28);
		border-radius: 12px;
		background: rgba(48, 213, 200, 0.04);
		color: var(--text-secondary);
		font-family: inherit;
		cursor: pointer;
		transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
	}
	.placeholder:hover {
		background: rgba(48, 213, 200, 0.1);
		border-color: rgba(48, 213, 200, 0.5);
		color: var(--accent);
	}
	.placeholder-icon {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 26px;
		line-height: 1;
		color: var(--accent);
		opacity: 0.7;
	}
	.placeholder:hover .placeholder-icon {
		opacity: 1;
	}
	.placeholder-title {
		font-size: 14px;
		font-weight: 800;
		letter-spacing: 0.02em;
		color: var(--text-primary);
	}
	.placeholder-desc {
		font-size: 12px;
		font-weight: 500;
		text-align: center;
		line-height: 1.5;
		color: var(--text-muted);
	}

	.toggle {
		padding: 8px 14px;
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: inherit;
		font-size: 12px;
		font-weight: 700;
		cursor: pointer;
	}
	.toggle.on {
		background: rgba(48, 213, 200, 0.18);
		border-color: rgba(48, 213, 200, 0.4);
		color: var(--accent);
	}

	.toolbar {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
		margin-bottom: 10px;
		padding: 10px;
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.5);
		border: 1px solid rgba(31, 41, 55, 0.6);
	}
	.status {
		font-size: 11px;
		font-weight: 700;
		padding: 4px 10px;
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
		gap: 6px;
		align-items: center;
		font-size: 11px;
		color: var(--text-secondary);
	}
	.sel select,
	.sel input {
		padding: 4px 8px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: inherit;
		font-size: 11px;
	}

	.btn {
		padding: 6px 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-secondary);
		font-family: inherit;
		font-size: 11px;
		font-weight: 700;
		cursor: pointer;
	}
	.btn:hover:not(:disabled) {
		color: var(--accent);
		border-color: rgba(48, 213, 200, 0.4);
	}
	.btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.termbox {
		height: 420px;
		min-height: 280px;
		padding: 10px;
		border-radius: 10px;
		background: #02060c;
		border: 1px solid rgba(31, 41, 55, 0.7);
		overflow: hidden;
	}

	.termbox :global(.xterm) {
		height: 100%;
	}
	.termbox :global(.xterm-viewport) {
		background: transparent !important;
	}
</style>
