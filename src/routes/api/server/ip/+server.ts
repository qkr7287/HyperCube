import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function GET() {
	try {
		// ifconfig를 사용하여 네트워크 인터페이스 정보 가져오기
		const { stdout } = await execAsync('ifconfig');
		
		// IP 주소 추출 (inet으로 시작하는 라인에서 IP 주소 찾기)
		const lines = stdout.split('\n');
		const ipAddresses: string[] = [];
		
		for (const line of lines) {
			if (line.includes('inet ') && !line.includes('127.0.0.1')) {
				const match = line.match(/inet (\d+\.\d+\.\d+\.\d+)/);
				if (match) {
					const ip = match[1];
					// localhost와 private IP 제외하고 실제 외부 IP만 선택
					if (!ip.startsWith('127.') && !ip.startsWith('169.254.')) {
						ipAddresses.push(ip);
					}
				}
			}
		}
		
		// 우선순위: 192.168.x.x, 10.x.x.x, 172.16-31.x.x, 기타 순으로 선택
		let selectedIP = '';
		if (ipAddresses.length > 0) {
			// 192.168.x.x 대역 우선 선택 (일반적인 로컬 네트워크)
			const localIP = ipAddresses.find(ip => ip.startsWith('192.168.'));
			if (localIP) {
				selectedIP = localIP;
			} else {
				// 10.x.x.x 대역 선택 (사설 네트워크)
				const privateIP = ipAddresses.find(ip => ip.startsWith('10.'));
				if (privateIP) {
					selectedIP = privateIP;
				} else {
					// Docker 네트워크(172.16-31.x.x) 제외하고 첫 번째 IP 선택
					const nonDockerIP = ipAddresses.find(ip => !ip.startsWith('172.'));
					if (nonDockerIP) {
						selectedIP = nonDockerIP;
					} else {
						// 마지막으로 첫 번째 IP 선택
						selectedIP = ipAddresses[0];
					}
				}
			}
		}
		
		// IP 주소만 반환 (http, 포트 제거)
		const displayIP = selectedIP || 'localhost';
		
		return new Response(JSON.stringify({ 
			ip: displayIP,
			rawIP: selectedIP,
			allIPs: ipAddresses 
		}), {
			headers: {
				'Content-Type': 'application/json'
			}
		});
		
	} catch (error) {
		console.error('서버 IP 가져오기 실패:', error);
		
		// 폴백: localhost 반환
		return new Response(JSON.stringify({ 
			ip: 'localhost',
			rawIP: '127.0.0.1',
			allIPs: ['127.0.0.1']
		}), {
			status: 200,
			headers: {
				'Content-Type': 'application/json'
			}
		});
	}
}
