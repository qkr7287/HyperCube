import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { base } from '$app/paths';

export const systemStore = writable<any>(null);
export const containersStore = writable<any[]>([]);
export const cpuDetailStore = writable<any>(null);
export const wsConnected = writable(false);

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let activeSubscriptions = new Set<string>();

const RECONNECT_DELAY = 3000;

function getWsUrl(): string {
	if (!browser) return '';
	const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
	return `${protocol}//${location.host}${base}/ws`;
}

function handleMessage(event: MessageEvent) {
	try {
		const msg = JSON.parse(event.data);
		switch (msg.type) {
			case 'system':
				systemStore.set(msg.data);
				break;
			case 'containers':
				containersStore.set(msg.data);
				break;
			case 'cpu-detail':
				cpuDetailStore.set(msg.data);
				break;
		}
	} catch {
		// ignore malformed messages
	}
}

function scheduleReconnect() {
	if (reconnectTimer) return;
	reconnectTimer = setTimeout(() => {
		reconnectTimer = null;
		connect();
	}, RECONNECT_DELAY);
}

export function connect() {
	if (!browser) return;
	if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return;

	const url = getWsUrl();
	ws = new WebSocket(url);

	ws.onopen = () => {
		wsConnected.set(true);
		console.log('[WS] Connected');
		// Re-subscribe after reconnect
		for (const channel of activeSubscriptions) {
			ws!.send(JSON.stringify({ type: 'subscribe', channel }));
		}
	};

	ws.onmessage = handleMessage;

	ws.onclose = () => {
		wsConnected.set(false);
		ws = null;
		scheduleReconnect();
	};

	ws.onerror = () => {
		// onclose will fire after onerror
	};
}

export function disconnect() {
	if (reconnectTimer) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}
	if (ws) {
		ws.onclose = null; // prevent reconnect
		ws.close();
		ws = null;
	}
	wsConnected.set(false);
}

export function subscribe(channel: string) {
	activeSubscriptions.add(channel);
	if (ws && ws.readyState === WebSocket.OPEN) {
		ws.send(JSON.stringify({ type: 'subscribe', channel }));
	}
}

export function unsubscribe(channel: string) {
	activeSubscriptions.delete(channel);
	if (ws && ws.readyState === WebSocket.OPEN) {
		ws.send(JSON.stringify({ type: 'unsubscribe', channel }));
	}
}
