<!--
  LogTailPanel — 컨테이너 live log tail.

  자체 WS 를 /ws/server/<agent_id>/ 로 열어 logs_subscribe 발행 → log_chunk
  메시지를 받아 라인 누적 → log_stream_end 또는 unmount 시 logs_unsubscribe.

  필터 / auto-scroll / 복사·다운로드 / pause 지원. 가상 스크롤 X (max 5000줄
  cap 으로 충분).
-->
<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';

	type LineRow = { id: number; stream: 'stdout' | 'stderr' | 'mixed'; text: string };

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
	let streamId = $state<string | null>(null);
	let unsubscribePending = false;

	let lines = $state<LineRow[]>([]);
	let lineSeq = 0;
	const MAX_LINES = 5000;

	let connected = $state(false);
	let subscribed = $state(false);
	let endedReason = $state<string | null>(null);
	let errorMsg = $state('');
	let autoScroll = $state(true);
	let paused = $state(false);
	let filter = $state('');
	let logBox: HTMLDivElement | undefined = $state(undefined);

	let initialTail = $state(100);
	let timestamps = $state(true);

	let displayed = $derived(filterLines(lines, filter));

	function filterLines(rows: LineRow[], q: string): LineRow[] {
		const t = q.trim();
		if (!t) return rows;
		try {
			const re = new RegExp(t, 'i');
			return rows.filter((r) => re.test(r.text));
		} catch {
			// invalid regex → fallback to substring
			const lc = t.toLowerCase();
			return rows.filter((r) => r.text.toLowerCase().includes(lc));
		}
	}

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	function uuid(): string {
		// 의존성 추가 없이 단순 UUIDv4-ish (RFC 4122 strict 아님 — backend 가 구분키로만 사용)
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

	async function startTail() {
		if (ws) return;
		errorMsg = '';
		endedReason = null;
		subscribed = false;
		ws = new WebSocket(wsUrl());
		ws.onopen = () => {
			connected = true;
			sendSubscribe();
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
			subscribed = false;
			ws = null;
		};
	}

	function sendSubscribe() {
		if (!ws || ws.readyState !== WebSocket.OPEN) return;
		streamId = uuid();
		ws.send(
			JSON.stringify({
				type: 'command',
				requestId: streamId,
				command: 'logs_subscribe',
				params: {
					containerId,
					tail: initialTail,
					timestamps,
				},
			}),
		);
	}

	function sendUnsubscribe() {
		if (!ws || ws.readyState !== WebSocket.OPEN || !streamId) return;
		unsubscribePending = true;
		ws.send(
			JSON.stringify({
				type: 'command',
				requestId: uuid(),
				command: 'logs_unsubscribe',
				params: { streamId },
			}),
		);
	}

	function stopTail() {
		sendUnsubscribe();
		try {
			ws?.close();
		} catch {
			/* ignore */
		}
		ws = null;
		streamId = null;
		connected = false;
		subscribed = false;
	}

	function handleMessage(msg: any) {
		const t = msg?.type;
		if (t === 'command_response' && msg.requestId === streamId) {
			if (msg.success) {
				subscribed = true;
			} else {
				errorMsg = msg.error || 'subscribe failed';
				subscribed = false;
			}
			return;
		}
		if (t === 'log_chunk' && msg.streamId === streamId && !paused) {
			appendChunk(msg.lines || [], msg.stream || 'mixed');
			return;
		}
		if (t === 'log_stream_end' && msg.streamId === streamId) {
			endedReason = msg.reason || 'ended';
			subscribed = false;
			return;
		}
		// 다른 server group broadcast (system_metrics 등) 은 무시.
	}

	async function appendChunk(newLines: string[], stream: 'stdout' | 'stderr' | 'mixed') {
		if (newLines.length === 0) return;
		const next = lines.slice();
		for (const ln of newLines) {
			next.push({ id: ++lineSeq, stream, text: ln });
		}
		// cap — 가장 오래된 부분 drop. 데이터 손실 의식적 (메모리 보호).
		if (next.length > MAX_LINES) next.splice(0, next.length - MAX_LINES);
		lines = next;
		if (autoScroll) {
			await tick();
			scrollToBottom();
		}
	}

	function scrollToBottom() {
		if (logBox) logBox.scrollTop = logBox.scrollHeight;
	}

	function clearLines() {
		lines = [];
	}

	async function copyAll() {
		const text = displayed.map((l) => l.text).join('\n');
		try {
			await navigator.clipboard.writeText(text);
		} catch {
			/* clipboard 권한 없음 */
		}
	}

	function downloadAll() {
		const text = displayed.map((l) => l.text).join('\n');
		const blob = new Blob([text], { type: 'text/plain' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `${containerId}-logs.txt`;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}

	function togglePanel() {
		open = !open;
		if (open) {
			startTail();
		} else {
			stopTail();
			lines = [];
			lineSeq = 0;
		}
	}

	function restart() {
		stopTail();
		lines = [];
		lineSeq = 0;
		setTimeout(() => startTail(), 100);
	}

	onMount(() => {
		if (open) startTail();
	});

	onDestroy(() => {
		stopTail();
	});
</script>

<section class="panel" class:closed={!open}>
	<div class="panel-header slim">
		<div>
			<h2>실시간 로그</h2>
			<p>컨테이너 로그를 실시간으로 tail. 패널을 열면 agent 가 stream 시작, 닫으면 즉시 정리.</p>
		</div>
		<button class="toggle" class:on={open} onclick={togglePanel}>
			{open ? '닫기' : '열기'}
		</button>
	</div>

	{#if !open}
		<!-- 닫힌 상태 CTA — bento 우측 영역(col 9-12) 의 남은 세로 공간을 채우는
		     큰 클릭 영역. agent stream 부담 없이 유저가 명시적으로 시작하도록. -->
		<button class="placeholder" onclick={togglePanel} aria-label="실시간 로그 시작">
			<span class="placeholder-icon">▶</span>
			<span class="placeholder-title">로그 스트림 시작</span>
			<span class="placeholder-desc">클릭하면 agent 가 tail 을 시작하고<br />실시간 로그가 표시됩니다.</span>
		</button>
	{:else}
		<div class="toolbar">
			<span class="status" class:ok={subscribed} class:err={!!errorMsg || endedReason}>
				{#if errorMsg}
					에러: {errorMsg}
				{:else if endedReason}
					종료됨 ({endedReason})
				{:else if subscribed}
					● 수신 중
				{:else if connected}
					◌ 연결 중...
				{:else}
					◌ 끊김
				{/if}
			</span>
			<input
				class="filter"
				type="text"
				placeholder="필터 (regex / substring)"
				bind:value={filter}
			/>
			<label class="chk">
				<input type="checkbox" bind:checked={autoScroll} /> 자동 스크롤
			</label>
			<label class="chk">
				<input type="checkbox" bind:checked={paused} /> 일시정지
			</label>
			<button class="btn" onclick={clearLines} disabled={lines.length === 0}>지우기</button>
			<button class="btn" onclick={copyAll} disabled={displayed.length === 0}>복사</button>
			<button class="btn" onclick={downloadAll} disabled={displayed.length === 0}>다운로드</button>
			<button class="btn" onclick={restart}>재시작</button>
			<span class="count">{displayed.length}{filter ? ` / ${lines.length}` : ''}줄{lines.length >= MAX_LINES ? ' (cap)' : ''}</span>
		</div>

		<div class="logbox" bind:this={logBox}>
			{#if displayed.length === 0}
				<div class="empty">
					{#if subscribed}로그를 기다리는 중...{:else if endedReason}로그가 없습니다.{:else}구독 중...{/if}
				</div>
			{:else}
				{#each displayed as line (line.id)}
					<div class="line {line.stream}">{line.text}</div>
				{/each}
			{/if}
		</div>
	{/if}
</section>

<style>
	.panel {
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		border-radius: 18px;
		padding: 20px;
		margin-top: 18px;
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

	/* 닫힌 상태 panel — 자식 placeholder 가 영역 채우도록 flex column. */
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
		font-size: 28px;
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

	.filter {
		flex: 1 1 200px;
		min-width: 0;
		padding: 6px 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 12px;
	}

	.chk {
		display: inline-flex;
		gap: 5px;
		align-items: center;
		font-size: 11px;
		color: var(--text-secondary);
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

	.count {
		margin-left: auto;
		font-size: 11px;
		color: var(--text-muted);
	}

	.logbox {
		height: 420px;
		overflow-y: auto;
		padding: 12px;
		border-radius: 10px;
		background: rgba(2, 6, 12, 0.7);
		border: 1px solid rgba(31, 41, 55, 0.7);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 11px;
		line-height: 1.5;
		color: #cbd5e1;
	}

	.empty {
		color: var(--text-muted);
		font-style: italic;
		font-size: 12px;
	}

	.line {
		white-space: pre-wrap;
		word-break: break-all;
		overflow-wrap: anywhere;
	}
	.line.stderr {
		color: #fca5a5;
	}
	.line.stdout {
		color: #cbd5e1;
	}
	.line.mixed {
		color: #cbd5e1;
	}
</style>
