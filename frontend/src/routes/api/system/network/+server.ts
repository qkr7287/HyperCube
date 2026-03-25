import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const GET: RequestHandler = async () => {
	try {
		// 호스트 네임스페이스 직접 사용 - 정확한 네트워크 정보 가져오기
		const [interfacesOutput, statsOutput, connectionsOutput] = await Promise.all([
			execAsync('ip addr show'),
			execAsync('cat /host/proc/net/dev'),
			execAsync('nsenter -t 1 -n ss -tuln 2>/dev/null || ss -tuln')
		]);
		
		const interfaces = parseIpAddrOutput(interfacesOutput.stdout);
		const stats = parseNetworkStats(statsOutput.stdout);
		
		// 네트워크 연결 수 계산 (ss 명령어 사용)
		const lines = connectionsOutput.stdout.split('\n').filter(line => line.trim());
		const connections = lines.filter(line => !line.startsWith('Netid')).length;

		return json({
			success: true,
			data: {
				interfaces: interfaces,
				stats: {
					rx_bytes: stats.total.rx_bytes,
					tx_bytes: stats.total.tx_bytes,
					rx_packets: stats.total.rx_packets,
					tx_packets: stats.total.tx_packets,
					rx_errors: stats.total.rx_errors,
					tx_errors: stats.total.tx_errors
				},
				connections: connections
			}
		});
	} catch (error) {
		console.error('Network API Error:', error);
		return json({
			success: false,
			error: '네트워크 정보를 가져오는데 실패했습니다.'
		}, { status: 500 });
	}
};

function parseNetworkStats(output: string) {
	const lines = output.split('\n').filter(line => line.trim() && !line.includes('Inter-'));
	const stats: any = { total: { rx_bytes: 0, tx_bytes: 0, rx_packets: 0, tx_packets: 0, rx_errors: 0, tx_errors: 0 } };

	lines.forEach(line => {
		const parts = line.trim().split(/\s+/);
		if (parts.length >= 10) {
			const iface = parts[0].replace(':', '');
			const rx_bytes = parseInt(parts[1]) || 0;
			const rx_packets = parseInt(parts[2]) || 0;
			const rx_errors = parseInt(parts[3]) || 0;
			const tx_bytes = parseInt(parts[9]) || 0;
			const tx_packets = parseInt(parts[10]) || 0;
			const tx_errors = parseInt(parts[11]) || 0;

			stats[iface] = { rx_bytes, tx_bytes, rx_packets, tx_packets, rx_errors, tx_errors };
			
			// 총합 계산
			stats.total.rx_bytes += rx_bytes;
			stats.total.tx_bytes += tx_bytes;
			stats.total.rx_packets += rx_packets;
			stats.total.tx_packets += tx_packets;
			stats.total.rx_errors += rx_errors;
			stats.total.tx_errors += tx_errors;
		}
	});

	return stats;
}

function parseIpAddrOutput(output: string) {
	const interfaces: any[] = [];
	const lines = output.split('\n');
	let currentInterface: any = null;
	
	for (const line of lines) {
		const trimmedLine = line.trim();
		
		// 인터페이스 시작 라인 (예: "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536")
		if (trimmedLine.match(/^\d+:/)) {
			if (currentInterface) {
				interfaces.push(currentInterface);
			}
			
			const parts = trimmedLine.split(':');
			const ifaceName = parts[1].trim();
			const status = trimmedLine.includes('UP') ? 'UP' : 'DOWN';
			
			currentInterface = {
				name: ifaceName,
				up: status === 'UP',
				mac: '',
				addresses: [],
				speed: null,
				mtu: null
			};
		}
		// MAC 주소 라인 (예: "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00")
		else if (trimmedLine.startsWith('link/') && currentInterface) {
			const macMatch = trimmedLine.match(/link\/\w+\s+([0-9a-fA-F:]+)/);
			if (macMatch) {
				currentInterface.mac = macMatch[1];
			}
		}
		// IP 주소 라인 (예: "    inet 127.0.0.1/8 scope host lo")
		else if (trimmedLine.startsWith('inet') && currentInterface) {
			const ipMatch = trimmedLine.match(/inet\s+([0-9.]+)/);
			if (ipMatch) {
				currentInterface.addresses.push({
					address: ipMatch[1],
					family: 'IPv4'
				});
			}
		}
		// IPv6 주소 라인
		else if (trimmedLine.startsWith('inet6') && currentInterface) {
			const ipMatch = trimmedLine.match(/inet6\s+([0-9a-fA-F:]+)/);
			if (ipMatch) {
				currentInterface.addresses.push({
					address: ipMatch[1],
					family: 'IPv6'
				});
			}
		}
	}
	
	// 마지막 인터페이스 추가
	if (currentInterface) {
		interfaces.push(currentInterface);
	}
	
	return interfaces;
}
