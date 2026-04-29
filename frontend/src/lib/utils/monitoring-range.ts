export type MonitoringRange = '10s' | '1m' | '5m' | '1h' | '24h' | '7d';

export type MonitoringRangeConfig = {
	label: string;
	pollMs: number;
	pollLabel: string;
	bucketSeconds: number;
	bucketLabel: string;
	points: number;
	windowMs: number;
	windowLabel: string;
	maxRawRows: number;
};

// Bucket size = range 라벨 그 자체. 1m = 1분 단위, 7d = 1주일 단위.
// 각 range의 표시 점 개수만 살짝씩 다르게 (10~14점).
export const MONITORING_RANGE_CONFIG: Record<MonitoringRange, MonitoringRangeConfig> = {
	'10s': {
		// 테스트/디버그용 단축 range. 10초 단위 bucket + 10초 polling 으로 chart
		// 누적 동작(메모리 leak / RangeError 등)을 빠르게 재현 검증한다. 일반
		// 사용자가 평소 쓸 단위는 아니지만, 운영 환경에서도 짧은 troubleshooting
		// 시 유용해 1m 보다 앞에 노출.
		label: '10초',
		pollMs: 10_000,
		pollLabel: '10초마다 갱신',
		bucketSeconds: 10,
		bucketLabel: '10초',
		points: 10,
		windowMs: 10 * 10 * 1000,
		windowLabel: '100초',
		maxRawRows: 600,
	},
	'1m': {
		label: '1분',
		pollMs: 60_000,
		pollLabel: '1분마다 갱신',
		bucketSeconds: 60,
		bucketLabel: '1분',
		points: 10,
		windowMs: 10 * 60 * 1000,
		windowLabel: '10분',
		maxRawRows: 600,
	},
	'5m': {
		label: '5분',
		pollMs: 300_000,
		pollLabel: '5분마다 갱신',
		bucketSeconds: 300,
		bucketLabel: '5분',
		points: 10,
		windowMs: 10 * 300 * 1000,
		windowLabel: '50분',
		maxRawRows: 600,
	},
	'1h': {
		label: '1시간',
		pollMs: 3_600_000,
		pollLabel: '1시간마다 갱신',
		bucketSeconds: 3_600,
		bucketLabel: '1시간',
		points: 12,
		windowMs: 12 * 3_600 * 1000,
		windowLabel: '12시간',
		maxRawRows: 1_200,
	},
	'24h': {
		label: '24시간',
		pollMs: 86_400_000,
		pollLabel: '24시간마다 갱신',
		bucketSeconds: 86_400,
		bucketLabel: '1일',
		points: 7,
		windowMs: 7 * 86_400 * 1000,
		windowLabel: '7일',
		maxRawRows: 2_000,
	},
	'7d': {
		label: '7일',
		pollMs: 604_800_000,
		pollLabel: '7일마다 갱신',
		bucketSeconds: 604_800,
		bucketLabel: '1주일',
		points: 4,
		windowMs: 4 * 604_800 * 1000,
		windowLabel: '4주',
		maxRawRows: 2_000,
	},
};

export function bucketEpoch(value: string | number, seconds: number): number {
	const ms = typeof value === 'number' ? value : new Date(value).getTime();
	if (!Number.isFinite(ms)) return 0;
	const epoch = Math.floor(ms / 1000);
	return epoch - (epoch % seconds);
}

export function buildRangeBuckets(range: MonitoringRange, anchorMs = Date.now()): number[] {
	const config = MONITORING_RANGE_CONFIG[range];
	const end = bucketEpoch(anchorMs, config.bucketSeconds);
	const start = end - (config.points - 1) * config.bucketSeconds;
	return Array.from({ length: config.points }, (_, index) => start + index * config.bucketSeconds);
}

export function formatRangeTick(epochSeconds: number, range: MonitoringRange): string {
	const date = new Date(epochSeconds * 1000);
	if (Number.isNaN(date.getTime())) return '';
	const pad = (value: number) => value.toString().padStart(2, '0');

	// 10s     → HH:MM:SS (초 단위까지)
	// 1m / 5m / 1h → HH:MM
	// 24h / 7d → MM/DD
	if (range === '24h' || range === '7d') {
		return `${pad(date.getMonth() + 1)}/${pad(date.getDate())}`;
	}
	if (range === '10s') {
		return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
	}
	return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function clampPercent(value: number): number {
	return Math.max(0, Math.min(100, value));
}
