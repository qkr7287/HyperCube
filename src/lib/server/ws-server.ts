import { WebSocketServer, WebSocket } from 'ws';
import type { Server } from 'http';
import { getSystemInfo, getCpuDetail, getContainerList } from './services/system-service.js';

const SYSTEM_INTERVAL = 2000;
const CONTAINERS_INTERVAL = 3000;
const CPU_DETAIL_INTERVAL = 2000;

interface ClientState {
	subscriptions: Set<string>;
}

const clients = new Map<WebSocket, ClientState>();

let wss: WebSocketServer;
let systemTimer: ReturnType<typeof setInterval> | null = null;
let containersTimer: ReturnType<typeof setInterval> | null = null;
let cpuDetailTimer: ReturnType<typeof setInterval> | null = null;

export function setupWebSocket(server: Server, basePath: string = '') {
	wss = new WebSocketServer({ noServer: true });

	server.on('upgrade', (req, socket, head) => {
		const url = req.url || '';
		// Accept /ws or /basePath/ws
		const wsPath = basePath ? `${basePath}/ws` : '/ws';
		if (url === wsPath || url === '/ws') {
			wss.handleUpgrade(req, socket, head, (ws) => {
				wss.emit('connection', ws, req);
			});
		} else {
			socket.destroy();
		}
	});

	wss.on('connection', (ws) => {
		clients.set(ws, { subscriptions: new Set() });
		console.log(`[WS] Client connected (total: ${clients.size})`);

		ws.on('message', (raw) => {
			try {
				const msg = JSON.parse(raw.toString());
				handleClientMessage(ws, msg);
			} catch {
				// ignore malformed messages
			}
		});

		ws.on('close', () => {
			clients.delete(ws);
			console.log(`[WS] Client disconnected (total: ${clients.size})`);
			updateCpuDetailTimer();
		});

		ws.on('error', () => {
			clients.delete(ws);
			updateCpuDetailTimer();
		});
	});

	startBroadcastLoops();
	console.log(`[WS] WebSocket server ready (path: ${basePath}/ws)`);
}

function handleClientMessage(ws: WebSocket, msg: { type: string; channel?: string }) {
	const state = clients.get(ws);
	if (!state) return;

	if (msg.type === 'subscribe' && msg.channel) {
		state.subscriptions.add(msg.channel);
		console.log(`[WS] Subscribe: ${msg.channel}`);
		if (msg.channel === 'cpu-detail') {
			updateCpuDetailTimer();
			// Send immediate data on subscribe
			sendCpuDetail(ws);
		}
	} else if (msg.type === 'unsubscribe' && msg.channel) {
		state.subscriptions.delete(msg.channel);
		console.log(`[WS] Unsubscribe: ${msg.channel}`);
		if (msg.channel === 'cpu-detail') {
			updateCpuDetailTimer();
		}
	}
}

function broadcast(type: string, data: unknown) {
	const payload = JSON.stringify({ type, data });
	for (const [ws] of clients) {
		if (ws.readyState === WebSocket.OPEN) {
			ws.send(payload);
		}
	}
}

function broadcastToSubscribers(channel: string, data: unknown) {
	const payload = JSON.stringify({ type: channel, data });
	for (const [ws, state] of clients) {
		if (ws.readyState === WebSocket.OPEN && state.subscriptions.has(channel)) {
			ws.send(payload);
		}
	}
}

async function sendCpuDetail(ws: WebSocket) {
	try {
		const data = await getCpuDetail();
		if (ws.readyState === WebSocket.OPEN) {
			ws.send(JSON.stringify({ type: 'cpu-detail', data }));
		}
	} catch (e) {
		console.error('[WS] CPU detail fetch error:', e);
	}
}

function hasCpuDetailSubscribers(): boolean {
	for (const [, state] of clients) {
		if (state.subscriptions.has('cpu-detail')) return true;
	}
	return false;
}

function updateCpuDetailTimer() {
	if (hasCpuDetailSubscribers() && !cpuDetailTimer) {
		cpuDetailTimer = setInterval(async () => {
			if (!hasCpuDetailSubscribers()) {
				clearInterval(cpuDetailTimer!);
				cpuDetailTimer = null;
				return;
			}
			try {
				const data = await getCpuDetail();
				broadcastToSubscribers('cpu-detail', data);
			} catch (e) {
				console.error('[WS] CPU detail broadcast error:', e);
			}
		}, CPU_DETAIL_INTERVAL);
	} else if (!hasCpuDetailSubscribers() && cpuDetailTimer) {
		clearInterval(cpuDetailTimer);
		cpuDetailTimer = null;
	}
}

function startBroadcastLoops() {
	// System info (always broadcast)
	systemTimer = setInterval(async () => {
		if (clients.size === 0) return;
		try {
			const data = await getSystemInfo();
			broadcast('system', data);
		} catch (e) {
			console.error('[WS] System broadcast error:', e);
		}
	}, SYSTEM_INTERVAL);

	// Container list (always broadcast)
	containersTimer = setInterval(async () => {
		if (clients.size === 0) return;
		try {
			const data = await getContainerList();
			broadcast('containers', data);
		} catch (e) {
			console.error('[WS] Containers broadcast error:', e);
		}
	}, CONTAINERS_INTERVAL);
}

export function shutdownWebSocket() {
	if (systemTimer) clearInterval(systemTimer);
	if (containersTimer) clearInterval(containersTimer);
	if (cpuDetailTimer) clearInterval(cpuDetailTimer);
	if (wss) wss.close();
}
