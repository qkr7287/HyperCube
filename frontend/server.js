import { createServer } from 'http';
import { handler } from './build/handler.js';
import { setupWebSocket } from './build/ws-server.js';

const PORT = process.env.PORT || 3334;
const BASE_PATH = process.env.BASE_PATH || '';

const server = createServer(handler);

setupWebSocket(server, BASE_PATH);

server.listen(PORT, () => {
	console.log(`[Server] Listening on http://localhost:${PORT}`);
	if (BASE_PATH) console.log(`[Server] Base path: ${BASE_PATH}`);
});
