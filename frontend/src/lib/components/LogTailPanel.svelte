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
	import StateBox from './StateBox.svelte';
	import InfoTooltip from './InfoTooltip.svelte';

	const HEADER_HELP = `컨테이너 stdout/stderr 를 agent 가 WebSocket 으로 stream.

· bottom 근처에 있으면 새 로그 자동 따라감, 위로 스크롤하면 자동 분리되어 과거 로그 읽기 가능
· "재연결" = WS 스트림만 다시 연결 (컨테이너 무관)
· "일시정지" = 화면 갱신만 멈춤 (수신 자체는 buffer 에 계속 쌓임)
· 최대 5000줄 유지 (cap 초과 시 가장 오래된 줄부터 drop)`;

	type LineRow = { id: number; stream: 'stdout' | 'stderr' | 'mixed'; text: string };
	type PendingChunk = { lines: string[]; stream: LineRow['stream'] };

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
	let paused = $state(false);
	let filter = $state('');
	let logBox: HTMLDivElement | undefined = $state(undefined);
	let actionMsg = $state('');
	let actionMsgTimer: ReturnType<typeof setTimeout> | null = null;
	let clearedByUser = $state(false);
	let pendingChunks = $state<PendingChunk[]>([]);
	let pausedLineCount = $state(0);

	// Sticky-bottom 자동 스크롤. bottom 근처(STICK_THRESHOLD_PX)면 stuckToBottom=true
	// → 신규 라인 도착 시 자동 따라감. 사용자가 위로 스크롤하면 자동 해제, 다시
	// bottom 가면 자동 재부착. 강제 점프(예전 autoScroll=true) 보다 표준 log/chat UX.
	const STICK_THRESHOLD_PX = 24;
	let stuckToBottom = $state(true);
	let unreadCount = $state(0);
	// 우리가 코드로 강제 스크롤한 경우엔 onscroll 핸들러가 stuckToBottom 토글 시
	// race condition 으로 잘못 끄지 않도록 skip.
	let programmaticScroll = false;

	let initialTail = $state(100);
	let timestamps = $state(true);

	let displayed = $derived(filterLines(lines, filter));
	let toolbarMsg = $derived(actionMsg || (pausedLineCount > 0 ? `${pausedLineCount}줄 대기 중` : ''));

	$effect(() => {
		if (!paused && pendingChunks.length > 0) {
			const chunks = pendingChunks;
			pendingChunks = [];
			pausedLineCount = 0;
			void appendChunks(chunks);
		}
	});

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

	function showActionMsg(message: string) {
		actionMsg = message;
		if (actionMsgTimer) clearTimeout(actionMsgTimer);
		actionMsgTimer = setTimeout(() => {
			actionMsg = '';
			actionMsgTimer = null;
		}, 1800);
	}

	function copyWithTextarea(text: string): boolean {
		if (!browser) return false;
		const textarea = document.createElement('textarea');
		textarea.value = text;
		textarea.setAttribute('readonly', '');
		textarea.style.position = 'fixed';
		textarea.style.left = '-9999px';
		textarea.style.top = '0';
		document.body.appendChild(textarea);
		textarea.focus();
		textarea.select();
		let ok = false;
		try {
			ok = document.execCommand('copy');
		} catch {
			ok = false;
		} finally {
			document.body.removeChild(textarea);
		}
		return ok;
	}

	function wsUrl(): string {
		const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
		const host = window.location.host;
		return `${proto}://${host}${base}/ws/server/${agentId}/`;
	}

	async function startTail() {
		if (ws) return;
		errorMsg = '';
		endedReason = null;
		subscribed = false;
		const t = token();
		if (!t) {
			errorMsg = '로그인이 필요합니다.';
			return;
		}
		const socket = new WebSocket(wsUrl(), ['hypercube.jwt', t]);
		ws = socket;
		socket.onopen = () => {
			if (ws !== socket) return;
			connected = true;
			sendSubscribe();
		};
		socket.onmessage = (ev) => {
			if (ws !== socket) return;
			let msg: any;
			try {
				msg = JSON.parse(ev.data);
			} catch {
				return;
			}
			handleMessage(msg);
		};
		socket.onerror = () => {
			if (ws !== socket) return;
			errorMsg = 'WebSocket 에러';
		};
		socket.onclose = () => {
			if (ws !== socket) return;
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
		const socket = ws;
		sendUnsubscribe();
		try {
			socket?.close();
		} catch {
			/* ignore */
		}
		if (ws === socket) ws = null;
		streamId = null;
		connected = false;
		subscribed = false;
		clearPendingChunks();
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
		if (t === 'log_chunk' && msg.streamId === streamId) {
			const chunkLines = Array.isArray(msg.lines) ? msg.lines : [];
			const stream = normalizeStream(msg.stream);
			if (paused) {
				queuePendingChunk(chunkLines, stream);
			} else {
				void appendChunk(chunkLines, stream);
			}
			return;
		}
		if (t === 'log_stream_end' && msg.streamId === streamId) {
			endedReason = msg.reason || 'ended';
			subscribed = false;
			return;
		}
		// 다른 server group broadcast (system_metrics 등) 은 무시.
	}

	function normalizeStream(stream: unknown): LineRow['stream'] {
		return stream === 'stdout' || stream === 'stderr' || stream === 'mixed' ? stream : 'mixed';
	}

	function queuePendingChunk(newLines: string[], stream: LineRow['stream']) {
		if (newLines.length === 0) return;
		let next = [...pendingChunks, { lines: newLines, stream }];
		let total = pausedLineCount + newLines.length;

		while (total > MAX_LINES && next.length > 0) {
			const overflow = total - MAX_LINES;
			const first = next[0];
			if (first.lines.length <= overflow) {
				total -= first.lines.length;
				next = next.slice(1);
			} else {
				next[0] = { ...first, lines: first.lines.slice(overflow) };
				total -= overflow;
			}
		}

		pendingChunks = next;
		pausedLineCount = total;
	}

	async function appendChunk(newLines: string[], stream: 'stdout' | 'stderr' | 'mixed') {
		await appendChunks([{ lines: newLines, stream }]);
	}

	async function appendChunks(chunks: PendingChunk[]) {
		if (chunks.length === 0) return;
		const next = lines.slice();
		let appended = false;
		for (const chunk of chunks) {
			for (const ln of chunk.lines) {
				next.push({ id: ++lineSeq, stream: chunk.stream, text: ln });
				appended = true;
			}
		}
		if (!appended) return;
		clearedByUser = false;
		// cap — 가장 오래된 부분 drop. 데이터 손실 의식적 (메모리 보호).
		if (next.length > MAX_LINES) next.splice(0, next.length - MAX_LINES);
		const added = next.length - lines.length;
		lines = next;
		if (stuckToBottom) {
			await tick();
			scrollToBottom();
		} else if (added > 0) {
			// 사용자가 위로 올려둔 상태 → 카운터만 증가. floating 버튼이 안내.
			unreadCount += added;
		}
	}

	function scrollToBottom() {
		if (!logBox) return;
		programmaticScroll = true;
		logBox.scrollTop = logBox.scrollHeight;
		stuckToBottom = true;
		unreadCount = 0;
		// onscroll 이 reentrant 로 호출돼도 우리가 강제한 거 무시되도록 미세 지연 후 reset.
		setTimeout(() => {
			programmaticScroll = false;
		}, 0);
	}

	function handleLogScroll() {
		if (!logBox || programmaticScroll) return;
		const distanceFromBottom = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight;
		const atBottom = distanceFromBottom <= STICK_THRESHOLD_PX;
		if (atBottom !== stuckToBottom) {
			stuckToBottom = atBottom;
			if (atBottom) unreadCount = 0;
		}
	}

	function clearPendingChunks() {
		pendingChunks = [];
		pausedLineCount = 0;
	}

	function clearLines() {
		lines = [];
		clearedByUser = true;
		clearPendingChunks();
		showActionMsg('로그를 지웠습니다');
	}

	function emptyStateKind() {
		if (clearedByUser || filter.trim() || endedReason) return 'empty';
		return subscribed ? 'loading' : 'loading';
	}

	function emptyStateMessage() {
		if (clearedByUser) return '표시된 로그를 지웠습니다. 새 로그가 들어오면 다시 표시됩니다.';
		if (filter.trim()) return '필터에 맞는 로그가 없습니다.';
		if (endedReason) return '로그가 없습니다.';
		return subscribed ? '새 로그를 기다리는 중...' : '구독 중...';
	}

	async function copyAll() {
		const text = displayed.map((l) => l.text).join('\n');
		if (!text) return;
		let ok = false;
		try {
			if (navigator.clipboard?.writeText && window.isSecureContext) {
				await navigator.clipboard.writeText(text);
				ok = true;
			}
		} catch {
			/* clipboard 권한 없음 */
		}
		if (!ok) ok = copyWithTextarea(text);
		showActionMsg(ok ? '복사 완료' : '복사 실패');
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
		showActionMsg('다운로드 시작');
	}

	function togglePanel() {
		open = !open;
		if (open) {
			clearedByUser = false;
			clearPendingChunks();
			startTail();
		} else {
			stopTail();
			lines = [];
			lineSeq = 0;
			clearedByUser = false;
			clearPendingChunks();
		}
	}

	function reconnect() {
		stopTail();
		lines = [];
		lineSeq = 0;
		clearedByUser = false;
		clearPendingChunks();
		unreadCount = 0;
		stuckToBottom = true;
		showActionMsg('스트림 재연결 중');
		setTimeout(() => startTail(), 100);
	}

	onMount(() => {
		if (open) startTail();
	});

	onDestroy(() => {
		stopTail();
		if (actionMsgTimer) clearTimeout(actionMsgTimer);
	});
</script>

<section class="panel" class:closed={!open}>
	<div class="panel-header slim">
		<div>
			<h2>실시간 로그<InfoTooltip text={HEADER_HELP} placement="bottom-start" /></h2>
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
			<span
				class="status"
				class:ok={subscribed && !paused}
				class:paused={subscribed && paused}
				class:err={!!errorMsg || endedReason}
			>
				{#if errorMsg}
					에러: {errorMsg}
				{:else if endedReason}
					종료됨 ({endedReason})
				{:else if subscribed && paused}
					일시정지
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
			<label class="chk log-pause">
				<input type="checkbox" bind:checked={paused} /> 일시정지
			</label>
			<div class="log-actions" aria-label="로그 작업">
				<button class="btn clear-btn" onclick={clearLines} disabled={lines.length === 0}>지우기</button>
				<button class="btn copy-btn" onclick={copyAll} disabled={displayed.length === 0}>복사</button>
				<button class="btn download-btn" onclick={downloadAll} disabled={displayed.length === 0}>다운로드</button>
				<button class="btn reconnect-btn" onclick={reconnect} title="WebSocket 스트림만 재연결합니다. 컨테이너는 영향 없음.">재연결</button>
			</div>
			<span class="action-msg" class:visible={!!toolbarMsg} aria-live="polite">{toolbarMsg || '\u00a0'}</span>
		</div>

		<div class="logbox-wrap">
			<div class="logbox" bind:this={logBox} onscroll={handleLogScroll}>
				{#if displayed.length === 0}
					<StateBox
						kind={emptyStateKind()}
						compact
						message={emptyStateMessage()}
					/>
				{:else}
					{#each displayed as line (line.id)}
						<div class="line {line.stream}">{line.text}</div>
					{/each}
				{/if}
			</div>
			{#if !stuckToBottom}
				<button
					type="button"
					class="jump-bottom"
					class:has-unread={unreadCount > 0}
					onclick={scrollToBottom}
					title="맨 아래로 이동 — 자동 추적 재개"
				>
					{#if unreadCount > 0}
						↓ 새 {unreadCount}줄
					{:else}
						↓ 맨 아래로
					{/if}
				</button>
			{/if}
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
		margin-top: 0;
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
		background: linear-gradient(90deg, rgba(48, 213, 200, 0.7), rgba(96, 165, 250, 0.12));
		opacity: 0.75;
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
		gap: 8px;
		padding: 14px 12px;
		min-height: 0;
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
		font-size: 20px;
		line-height: 1;
		color: var(--accent);
		opacity: 0.7;
	}
	.placeholder:hover .placeholder-icon {
		opacity: 1;
	}
	.placeholder-title {
		font-size: 12px;
		font-weight: 800;
		letter-spacing: 0.02em;
		color: var(--text-primary);
	}
	.placeholder-desc {
		font-size: 10.5px;
		font-weight: 500;
		text-align: center;
		line-height: 1.5;
		color: var(--text-muted);
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

	.toolbar {
		display: grid;
		grid-template-columns: auto minmax(120px, 1fr) auto auto;
		grid-template-rows: 24px 26px;
		grid-template-areas:
			"status filter msg pause"
			"actions actions actions actions";
		gap: 5px;
		align-items: center;
		min-width: 0;
		max-width: 100%;
		min-height: 58px;
		box-sizing: border-box;
		margin-bottom: 5px;
		padding: 5px 6px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.5);
		border: 1px solid rgba(100, 116, 139, 0.16);
	}
	.status {
		grid-area: status;
		justify-self: start;
		min-width: 54px;
		text-align: center;
		font-size: 10px;
		font-weight: 700;
		padding: 3px 7px;
		border-radius: 999px;
		background: rgba(100, 116, 139, 0.16);
		color: var(--text-secondary);
		border: 1px solid rgba(100, 116, 139, 0.32);
		white-space: nowrap;
	}
	.status.ok {
		background: rgba(16, 185, 129, 0.18);
		color: #34d399;
		border-color: rgba(16, 185, 129, 0.35);
	}
	.status.paused {
		background: rgba(245, 158, 11, 0.16);
		color: #fbbf24;
		border-color: rgba(245, 158, 11, 0.35);
	}
	.status.err {
		background: rgba(239, 68, 68, 0.18);
		color: #fca5a5;
		border-color: rgba(239, 68, 68, 0.4);
	}

	.filter {
		grid-area: filter;
		width: 100%;
		height: 23px;
		min-width: 0;
		box-sizing: border-box;
		padding: 4px 7px;
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 10.5px;
	}

	.chk {
		display: inline-flex;
		gap: 4px;
		align-items: center;
		min-height: 22px;
		font-size: 10px;
		color: var(--text-secondary);
		font-weight: 750;
		white-space: nowrap;
	}

	.chk input {
		appearance: none;
		position: relative;
		width: 26px;
		height: 14px;
		margin: 0;
		border-radius: 999px;
		background: rgba(100, 116, 139, 0.22);
		border: 1px solid rgba(100, 116, 139, 0.35);
		cursor: pointer;
		transition: background-color var(--ease-fast), border-color var(--ease-fast);
	}

	.chk input::before {
		content: '';
		position: absolute;
		left: 2px;
		top: 2px;
		width: 8px;
		height: 8px;
		border-radius: 999px;
		background: rgba(203, 213, 225, 0.9);
		transition: transform var(--ease-fast), background-color var(--ease-fast);
	}

	.chk input:checked {
		background: rgba(48, 213, 200, 0.2);
		border-color: rgba(48, 213, 200, 0.52);
	}

	.chk input:checked::before {
		transform: translateX(12px);
		background: var(--accent);
	}

	.log-pause {
		grid-area: pause;
	}

	.log-actions {
		grid-area: actions;
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 5px;
		min-width: 0;
	}

	.btn {
		width: 100%;
		min-width: 0;
		height: 25px;
		padding: 4px 7px;
		border-radius: 7px;
		background:
			linear-gradient(180deg, rgba(21, 27, 38, 0.78), rgba(8, 12, 19, 0.7)),
			rgba(13, 17, 23, 0.84);
		border: 1px solid rgba(100, 116, 139, 0.18);
		color: var(--text-secondary);
		font-family: inherit;
		font-size: 10px;
		font-weight: 700;
		cursor: pointer;
		white-space: nowrap;
	}
	.btn:hover:not(:disabled) {
		color: var(--accent);
		border-color: rgba(48, 213, 200, 0.4);
		background: rgba(48, 213, 200, 0.08);
	}
	.btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.reconnect-btn {
		color: var(--accent);
		border-color: rgba(48, 213, 200, 0.3);
		background: rgba(48, 213, 200, 0.08);
	}

	.action-msg {
		grid-area: msg;
		justify-self: end;
		align-self: center;
		max-width: 200px;
		overflow: hidden;
		text-overflow: ellipsis;
		padding: 2px 8px;
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.12);
		border: 1px solid rgba(48, 213, 200, 0.28);
		color: var(--accent);
		font-size: 10px;
		font-weight: 800;
		white-space: nowrap;
		visibility: hidden;
		opacity: 0;
		transition: opacity var(--ease-fast), visibility var(--ease-fast);
	}

	.action-msg.visible {
		visibility: visible;
		opacity: 1;
	}

	.logbox-wrap {
		position: relative;
		flex: 1 1 0;
		min-height: 0;
		min-width: 0;
		width: 100%;
		display: flex;
	}

	.jump-bottom {
		position: absolute;
		right: 12px;
		bottom: 10px;
		padding: 5px 11px;
		border-radius: 999px;
		border: 1px solid rgba(48, 213, 200, 0.45);
		background: rgba(13, 17, 23, 0.92);
		color: var(--accent);
		font-family: inherit;
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.02em;
		cursor: pointer;
		z-index: 2;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
		transition: background 0.15s ease, border-color 0.15s ease;
	}
	.jump-bottom:hover {
		background: rgba(48, 213, 200, 0.18);
		border-color: rgba(48, 213, 200, 0.7);
	}
	.jump-bottom.has-unread {
		background: rgba(48, 213, 200, 0.18);
		border-color: rgba(48, 213, 200, 0.6);
		animation: pulse-unread 1.6s ease-in-out infinite;
	}

	@keyframes pulse-unread {
		0%, 100% { box-shadow: 0 4px 12px rgba(48, 213, 200, 0.15); }
		50% { box-shadow: 0 4px 16px rgba(48, 213, 200, 0.55); }
	}

	.logbox {
		flex: 1 1 0;
		height: auto;
		min-height: 0;
		min-width: 0;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow-y: auto;
		padding: 7px;
		border-radius: 8px;
		background:
			linear-gradient(180deg, rgba(2, 6, 12, 0.85), rgba(2, 6, 12, 0.72)),
			rgba(2, 6, 12, 0.7);
		border: 1px solid rgba(100, 116, 139, 0.18);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 10.5px;
		line-height: 1.38;
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
		color: #cbd5e1;
	}
	/* stderr 는 "에러" 가 아니라 그냥 다른 stream 이다. uvicorn/tornado 처럼
	   access log 를 stderr 로 쏘는 프레임워크가 흔하기 때문에 일률적으로
	   빨갛게 칠하면 모든 줄이 위험해 보인다. 톤만 약간 따뜻하게 줘서 stream
	   구분만 유지하고, 진짜 ERROR/Traceback 강조는 content 매칭에 맡긴다. */
	.line.stderr {
		color: #d8c5b8;
	}
	.line.stdout,
	.line.mixed {
		color: #cbd5e1;
	}
</style>
