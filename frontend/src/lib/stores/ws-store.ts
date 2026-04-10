/**
 * Backend WebSocket Store
 *
 * Django Channels MonitoringConsumer에 연결하여 Agent 실시간 데이터를 수신한다.
 * Agent 데이터는 data-adapter를 통해 Frontend 인터페이스로 변환 후 store에 저장.
 */
import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { base } from '$app/paths';
import { transformSystemMetrics, transformContainers, mergeSystemInfo } from '$lib/utils/data-adapter';
import type { SystemInfo, ContainerInfo } from '$lib/utils/data-adapter';

// ----- Stores -----

export const systemStore = writable<SystemInfo | null>(null);
export const containersStore = writable<ContainerInfo[]>([]);
export const containerMetricsStore = writable<Map<string, any>>(new Map());
export const cpuDetailStore = writable<any>(null);
export const wsConnected = writable(false);

// ----- Internal State -----

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let currentServerId = '';
let currentToken = '';

const RECONNECT_BASE = 3000;
const RECONNECT_MAX = 30000;
let reconnectAttempts = 0;

// ----- Connection -----

function getWsUrl(serverId: string, token: string): string {
	if (!browser) return '';
	const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
	return `${protocol}//${location.host}${base}/ws/server/${serverId}/?token=${token}`;
}

export function connect(serverId: string, token: string) {
	if (!browser) return;
	if (!serverId || !token) return;

	// 이미 같은 서버에 연결 중이면 무시
	if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
		if (currentServerId === serverId) return;
		disconnect(); // 다른 서버로 전환
	}

	currentServerId = serverId;
	currentToken = token;

	const url = getWsUrl(serverId, token);
	console.log(`[WS] Connecting to server ${serverId.substring(0, 8)}...`);
	ws = new WebSocket(url);

	ws.onopen = () => {
		reconnectAttempts = 0;
		wsConnected.set(true);
		console.log('[WS] Connected');
		// Delta Sync 때문에 WS로 system_metrics가 늦게 올 수 있으므로
		// REST API로 초기 데이터를 한번 가져온다
		fetchInitialMetrics(serverId, token);
	};

	ws.onmessage = handleMessage;

	ws.onclose = (event) => {
		wsConnected.set(false);
		ws = null;
		if (event.code === 4001) {
			console.warn('[WS] Auth rejected (4001). Not reconnecting.');
			return;
		}
		scheduleReconnect();
	};

	ws.onerror = () => {
		// onclose fires after onerror
	};
}

export function disconnect() {
	if (reconnectTimer) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}
	reconnectAttempts = 0;
	if (ws) {
		ws.onclose = null;
		ws.close();
		ws = null;
	}
	wsConnected.set(false);
	systemStore.set(null);
	containersStore.set([]);
	containerMetricsStore.set(new Map());
}

// ----- Message Handling -----

function handleMessage(event: MessageEvent) {
	try {
		const msg = JSON.parse(event.data);
		switch (msg.type) {
			case 'system_metrics':
				// Delta Sync: 기존 store 값과 merge (빈 필드로 덮어쓰기 방지)
				systemStore.update((prev) => {
					const incoming = transformSystemMetrics(msg);
					if (!prev) return incoming;
					return mergeSystemInfo(prev, incoming);
				});
				break;
			case 'containers':
				containersStore.set(transformContainers(msg));
				break;
			case 'container_metrics': {
				const containerId = msg.data?.containerId ?? '';
				if (containerId) {
					containerMetricsStore.update((map) => {
						const next = new Map(map);
						next.set(containerId, msg.data);
						return next;
					});
				}
				break;
			}
			case 'connection':
				console.log(`[WS] Server: ${msg.message}`);
				break;
		}
	} catch {
		// ignore malformed messages
	}
}

// ----- Reconnect -----

function scheduleReconnect() {
	if (reconnectTimer) return;
	if (!currentServerId || !currentToken) return;

	const delay = Math.min(RECONNECT_BASE * Math.pow(2, reconnectAttempts), RECONNECT_MAX);
	reconnectAttempts++;
	console.log(`[WS] Reconnecting in ${Math.round(delay / 1000)}s...`);

	reconnectTimer = setTimeout(() => {
		reconnectTimer = null;
		connect(currentServerId, currentToken);
	}, delay);
}

// ----- Initial Fetch (Delta Sync 보완) -----

async function fetchInitialMetrics(serverId: string, token: string) {
	try {
		const res = await fetch(`${base}/api/agents/${serverId}/latest-metrics/`, {
			headers: { 'Authorization': `Bearer ${token}` },
		});
		if (!res.ok) return;
		const json = await res.json();
		const data = json.data ?? json;
		if (data.cpu || data.memory || data.disk) {
			// latest-metrics 응답을 system_metrics 형태로 변환
			systemStore.set(transformSystemMetrics({ data }));
			console.log('[WS] Initial system metrics loaded via REST');
		}
	} catch {
		// 실패해도 무시 - WS delta가 나중에 채움
	}
}

// ----- Backward Compatibility -----
// CpuDetailModal에서 import하는 subscribe/unsubscribe를 no-op으로 유지

export function subscribe(_channel: string) {
	// Backend WS는 자동 브로드캐스트이므로 subscribe 불필요
}

export function unsubscribe(_channel: string) {
	// no-op
}
