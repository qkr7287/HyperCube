import { sveltekit } from '@sveltejs/kit/vite';
import { connect, type Socket } from 'node:net';
import type { IncomingMessage } from 'node:http';
import { defineConfig, loadEnv, type Plugin } from 'vite';

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), '');
	const apiTarget = env.API_TARGET || 'http://192.168.0.16:3334';

	return {
		plugins: [workspaceWebSocketProxy(apiTarget), sveltekit()],
		server: {
			host: true,
			port: 3334,
			proxy: {
				'/api': {
					target: apiTarget,
					changeOrigin: true,
				},
				'/django-admin': {
					target: apiTarget,
					changeOrigin: true,
				},
				'/static': {
					target: apiTarget,
					changeOrigin: true,
				},
				'/ws': {
					target: apiTarget,
					changeOrigin: true,
					ws: true,
				},
				'/workspace': {
					target: apiTarget,
					changeOrigin: true,
					ws: true,
				}
			}
		}
	};
});

function workspaceWebSocketProxy(apiTarget: string): Plugin {
	return {
		name: 'hypercube-workspace-ws-proxy',
		configureServer(server) {
			return () => {
				const httpServer = server.httpServer;
				if (!httpServer) return;

				const originalUpgradeListeners = httpServer.listeners('upgrade');
				httpServer.removeAllListeners('upgrade');
				httpServer.on('upgrade', (req, socket, head) => {
					if (req.url?.startsWith('/workspace/')) {
						proxyWorkspaceUpgrade(apiTarget, req, socket, head);
						return;
					}
					for (const listener of originalUpgradeListeners) {
						listener.call(httpServer, req, socket, head);
					}
				});
			};
		}
	};
}

function proxyWorkspaceUpgrade(
	apiTarget: string,
	req: IncomingMessage,
	socket: Socket,
	head: Buffer
): void {
	let target: URL;
	try {
		target = new URL(apiTarget);
	} catch {
		socket.end('HTTP/1.1 500 Invalid API_TARGET\r\n\r\n');
		return;
	}

	const port = Number(target.port || (target.protocol === 'https:' ? 443 : 80));
	const upstream = connect(port, target.hostname);
	let settled = false;

	upstream.on('connect', () => {
		settled = true;
		upstream.write(`${req.method ?? 'GET'} ${req.url ?? '/'} HTTP/${req.httpVersion}\r\n`);
		for (const [name, value] of Object.entries(req.headers)) {
			if (value === undefined) continue;
			if (name.toLowerCase() === 'host') {
				upstream.write(`host: ${target.host}\r\n`);
				continue;
			}
			if (Array.isArray(value)) {
				for (const item of value) upstream.write(`${name}: ${item}\r\n`);
			} else {
				upstream.write(`${name}: ${value}\r\n`);
			}
		}
		upstream.write('\r\n');
		if (head.length > 0) upstream.write(head);
		socket.pipe(upstream);
		upstream.pipe(socket);
	});

	upstream.on('error', () => {
		if (!settled) socket.end('HTTP/1.1 502 Workspace WebSocket proxy failed\r\n\r\n');
		else socket.destroy();
	});
	socket.on('error', () => upstream.destroy());
}
