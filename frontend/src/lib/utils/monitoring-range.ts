export type MonitoringRange = '1m' | '5m' | '1h' | '24h' | '7d';

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

export const MONITORING_RANGE_CONFIG: Record<MonitoringRange, MonitoringRangeConfig> = {
	'1m': {
		label: '1분',
		pollMs: 60_000,
		pollLabel: '1분마다 갱신',
		bucketSeconds: 5,
		bucketLabel: '5초',
		points: 12,
		windowMs: 12 * 5 * 1000,
		windowLabel: '1분',
		maxRawRows: 240,
	},
	'5m': {
		label: '5분',
		pollMs: 300_000,
		pollLabel: '5분마다 갱신',
		bucketSeconds: 15,
		bucketLabel: '15초',
		points: 20,
		windowMs: 20 * 15 * 1000,
		windowLabel: '5분',
		maxRawRows: 400,
	},
	'1h': {
		label: '1시간',
		pollMs: 3_600_000,
		pollLabel: '1시간마다 갱신',
		bucketSeconds: 60,
		bucketLabel: '1분',
		points: 60,
		windowMs: 60 * 60 * 1000,
		windowLabel: '1시간',
		maxRawRows: 1_200,
	},
	'24h': {
		label: '24시간',
		pollMs: 86_400_000,
		pollLabel: '24시간마다 갱신',
		bucketSeconds: 600,
		bucketLabel: '10분',
		points: 144,
		windowMs: 144 * 600 * 1000,
		windowLabel: '24시간',
		maxRawRows: 3_000,
	},
	'7d': {
		label: '7일',
		pollMs: 604_800_000,
		pollLabel: '7일마다 갱신',
		bucketSeconds: 3_600,
		bucketLabel: '1시간',
		points: 168,
		windowMs: 168 * 3_600 * 1000,
		windowLabel: '7일',
		maxRawRows: 4_000,
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

	if (range === '7d') {
		return `${pad(date.getMonth() + 1)}/${pad(date.getDate())}`;
	}
	if (range === '24h') {
		return `${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
	}
	return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function clampPercent(value: number): number {
	return Math.max(0, Math.min(100, value));
}
