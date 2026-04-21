/**
 * Global Events WebSocket — Backend의 cross-cutting 이벤트 채널.
 *
 * Agent 상태 변화(online/offline)를 실시간으로 받아서:
 *   - activeAgentIds: 메인 UI 표시용 active set (Set<string>)
 *   - statusEvents: 최근 알림 이벤트 history (toast/panel용, 최근 20건)
 * 두 store에 반영한다.
 */
import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { base } from '$app/paths';

export type AgentStatusEvent = {
	type: 'agent_status_change';
	status: 'online' | 'offline';
	server_id: string;
	hostname: string;
	last_seen_at: string;
	previous_offline_seconds?: number | null;
	receivedAt: number; // 클라이언트 도착 시각 (epoch ms)
};

export const activeAgentIds = writable<Set<string>>(new Set());
export const statusEvents = writable<AgentStatusEvent[]>([]);
export const globalConnected = writable(false);

// pending 컨테이너 요청 개수 (admin 헤더 배지).
// Backend에서 request_status_change / request_created 이벤트를 푸시하면 증감.
export const pendingRequestCount = writable<number>(0);

const MAX_EVENTS = 20;

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let currentToken = '';
let attempts = 0;
const RECONNECT_BASE = 3000;
const RECONNECT_MAX = 30000;

function url(token: string): string {
	if (!browser) return '';
	const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
	return `${protocol}//${location.host}${base}/ws/global/?token=${token}`;
}

export function connectGlobal(token: string) {
	if (!browser || !token) return;
	if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
		if (currentToken === token) return;
		disconnectGlobal();
	}
	currentToken = token;
	ws = new WebSocket(url(token));
	ws.onopen = () => {
		attempts = 0;
		globalConnected.set(true);
		console.log('[GlobalWS] connected');
	};
	ws.onmessage = (ev) => {
		try {
			const msg = JSON.parse(ev.data);
			handleEvent(msg);
		} catch {
			/* ignore */
		}
	};
	ws.onclose = (ev) => {
		globalConnected.set(false);
		ws = null;
		if (ev.code === 4001 || ev.code === 4003) {
			console.warn(`[GlobalWS] auth rejected (${ev.code}). Not reconnecting.`);
			return;
		}
		scheduleReconnect();
	};
	ws.onerror = () => {
		/* close 핸들러가 처리 */
	};
}

export function disconnectGlobal() {
	if (reconnectTimer) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}
	attempts = 0;
	if (ws) {
		ws.onclose = null;
		ws.close();
		ws = null;
	}
	globalConnected.set(false);
	currentToken = '';
}

export function seedActiveAgents(ids: string[]) {
	activeAgentIds.set(new Set(ids));
}

function handleEvent(msg: any) {
	if (msg?.type === 'agent_status_change') {
		const evt: AgentStatusEvent = {
			type: 'agent_status_change',
			status: msg.status,
			server_id: String(msg.server_id),
			hostname: String(msg.hostname ?? ''),
			last_seen_at: String(msg.last_seen_at ?? ''),
			previous_offline_seconds: msg.previous_offline_seconds ?? null,
			receivedAt: Date.now(),
		};

		activeAgentIds.update((set) => {
			const next = new Set(set);
			if (evt.status === 'online') next.add(evt.server_id);
			else next.delete(evt.server_id);
			return next;
		});

		statusEvents.update((list) => [evt, ...list].slice(0, MAX_EVENTS));
		return;
	}

	if (msg?.type === 'request_created') {
		pendingRequestCount.update((n) => n + 1);
		return;
	}

	if (msg?.type === 'request_status_change') {
		// 승인/반려/배포완료 등으로 pending 에서 빠지면 감소.
		// Backend가 new_status를 같이 보내면 더 정확하지만, 일단 최소 구현.
		if (msg.previous_status === 'pending' && msg.new_status !== 'pending') {
			pendingRequestCount.update((n) => Math.max(0, n - 1));
		}
		return;
	}
}

function scheduleReconnect() {
	if (reconnectTimer || !currentToken) return;
	const delay = Math.min(RECONNECT_BASE * Math.pow(2, attempts), RECONNECT_MAX);
	attempts++;
	console.log(`[GlobalWS] reconnect in ${Math.round(delay / 1000)}s`);
	reconnectTimer = setTimeout(() => {
		reconnectTimer = null;
		connectGlobal(currentToken);
	}, delay);
}
