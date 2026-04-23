export function formatPercent(value?: number | null, digits = 1): string {
	const next = Number(value ?? 0);
	return `${Number.isFinite(next) ? next.toFixed(digits) : '0.0'}%`;
}

export function formatBytes(bytes?: number | null): string {
	const value = Number(bytes ?? 0);
	if (!Number.isFinite(value) || value === 0) return '0 B';

	const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
	let scaled = Math.abs(value);
	let unitIndex = 0;

	while (scaled >= 1024 && unitIndex < units.length - 1) {
		scaled /= 1024;
		unitIndex += 1;
	}

	const signed = value < 0 ? -scaled : scaled;
	const digits = scaled >= 10 || unitIndex === 0 ? 0 : 1;
	return `${signed.toFixed(digits)} ${units[unitIndex]}`;
}

export function formatRate(bytesPerSecond?: number | null): string {
	return `${formatBytes(bytesPerSecond ?? 0)}/s`;
}

export function formatRelative(value?: string | null): string {
	if (!value) return '-';
	const at = new Date(value).getTime();
	if (Number.isNaN(at)) return '-';

	const diff = Math.max(0, Math.floor((Date.now() - at) / 1000));
	if (diff < 15) return '실시간';
	if (diff < 60) return `${diff}초 전`;
	if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
	if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
	return `${Math.floor(diff / 86400)}일 전`;
}

export function formatClock(value?: string | null): string {
	if (!value) return '-';
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return '-';
	return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function healthLabel(value?: string | null): string {
	return ({
		healthy: '정상',
		warning: '주의',
		critical: '위험',
		offline: '오프라인',
		stale: '지연',
	} as Record<string, string>)[value ?? ''] ?? '-';
}

export function freshnessLabel(ageSeconds?: number | null): string {
	if (ageSeconds == null) return '데이터 없음';
	if (ageSeconds <= 15) return '실시간';
	if (ageSeconds <= 30) return '관찰';
	if (ageSeconds <= 60) return '지연';
	return '만료';
}

export type RangeKey = '1m' | '5m' | '1h' | '24h' | '7d';

export function rangeLabel(range: RangeKey): string {
	return ({
		'1m': '최근 1분',
		'5m': '최근 5분',
		'1h': '최근 1시간',
		'24h': '최근 24시간',
		'7d': '최근 7일',
	} as Record<RangeKey, string>)[range];
}

export function rangeBucketLabel(range: RangeKey): string {
	return ({
		'1m': '5초 간격',
		'5m': '15초 간격',
		'1h': '60초 간격',
		'24h': '5분 간격',
		'7d': '30분 간격',
	} as Record<RangeKey, string>)[range];
}

const REASON_MAP: Array<[RegExp | string, string]> = [
	['Agent is offline', '에이전트 오프라인 (Agent가 응답하지 않음)'],
	['No recent metrics', '최근 메트릭 없음 (Agent 부팅 중이거나 연결 지연)'],
	[/^Metrics older than (\d+) seconds$/, '메트릭 수신 지연 ($1초 이상 갱신 안 됨)'],
	[/^CPU >= (\d+)%$/, 'CPU 사용률 $1% 초과 (과부하 가능성)'],
	[/^Memory >= (\d+)%$/, '메모리 사용률 $1% 초과 (OOM 위험)'],
	[/^Disk >= (\d+)%$/, '디스크 사용량 $1% 초과 (공간 부족)'],
	[/^GPU >= (\d+)%$/, 'GPU 사용률 $1% 초과'],
	['Dead container detected', '비정상 종료 컨테이너 발견'],
	['Restarting container detected', '재시작 반복 컨테이너 발견'],
];

export function humanizeReason(reason: string): string {
	for (const [pattern, replacement] of REASON_MAP) {
		if (typeof pattern === 'string') {
			if (reason === pattern) return replacement;
		} else if (pattern.test(reason)) {
			return reason.replace(pattern, replacement);
		}
	}
	return reason;
}

const SHORT_REASON_MAP: Array<[RegExp | string, string]> = [
	['Agent is offline', '응답 없음'],
	['No recent metrics', '메트릭 없음'],
	[/^Metrics older than (\d+) seconds$/, '메트릭 $1초 지연'],
	[/^CPU >= (\d+)%$/, 'CPU $1%↑'],
	[/^Memory >= (\d+)%$/, '메모리 $1%↑'],
	[/^Disk >= (\d+)%$/, '디스크 $1%↑'],
	[/^GPU >= (\d+)%$/, 'GPU $1%↑'],
	['Dead container detected', '컨테이너 중단'],
	['Restarting container detected', '컨테이너 재시작'],
];

export function shortReason(reason: string): string {
	for (const [pattern, replacement] of SHORT_REASON_MAP) {
		if (typeof pattern === 'string') {
			if (reason === pattern) return replacement;
		} else if (pattern.test(reason)) {
			return reason.replace(pattern, replacement);
		}
	}
	return reason;
}

export function rangePollLabel(range: RangeKey): string {
	return ({
		'1m': '10초 주기 갱신',
		'5m': '30초 주기 갱신',
		'1h': '1분 주기 갱신',
		'24h': '5분 주기 갱신',
		'7d': '30분 주기 갱신',
	} as Record<RangeKey, string>)[range];
}
