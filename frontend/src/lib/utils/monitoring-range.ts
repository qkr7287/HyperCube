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
		pollMs: 10_000,
		pollLabel: '10초',
		bucketSeconds: 5,
		bucketLabel: '5초',
		points: 30,
		windowMs: 30 * 5 * 1000,
		windowLabel: '약 2분 30초',
		maxRawRows: 240,
	},
	'5m': {
		label: '5분',
		pollMs: 30_000,
		pollLabel: '30초',
		bucketSeconds: 15,
		bucketLabel: '15초',
		points: 60,
		windowMs: 60 * 15 * 1000,
		windowLabel: '15분',
		maxRawRows: 800,
	},
	'1h': {
		label: '1시간',
		pollMs: 60_000,
		pollLabel: '1분',
		bucketSeconds: 60,
		bucketLabel: '1분',
		points: 240,
		windowMs: 240 * 60 * 1000,
		windowLabel: '4시간',
		maxRawRows: 2_000,
	},
	'24h': {
		label: '24시간',
		pollMs: 300_000,
		pollLabel: '5분',
		bucketSeconds: 300,
		bucketLabel: '5분',
		points: 500,
		windowMs: 500 * 300 * 1000,
		windowLabel: '약 41시간',
		maxRawRows: 4_000,
	},
	'7d': {
		label: '7일',
		pollMs: 1_800_000,
		pollLabel: '30분',
		bucketSeconds: 1_800,
		bucketLabel: '30분',
		points: 600,
		windowMs: 600 * 1_800 * 1000,
		windowLabel: '약 12.5일',
		maxRawRows: 8_000,
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
