import { describe, expect, it } from 'vitest';
import {
	asNumber,
	clampPercent,
	compactBytes,
	deltaTone,
	formatDelta,
	levelLabel,
	pctRangeStatus,
	severity,
	shareOf,
} from './container-kpi';

describe('severity', () => {
	it('classifies by warn/crit thresholds', () => {
		expect(severity(0, 70, 90)).toBe('normal');
		expect(severity(69.99, 70, 90)).toBe('normal');
		expect(severity(70, 70, 90)).toBe('warn');
		expect(severity(89.99, 70, 90)).toBe('warn');
		expect(severity(90, 70, 90)).toBe('danger');
		expect(severity(100, 70, 90)).toBe('danger');
	});
	it('handles negative input as normal (defensive — cannot be < 0 in practice)', () => {
		expect(severity(-5, 70, 90)).toBe('normal');
	});
});

describe('asNumber', () => {
	it('returns finite number unchanged', () => {
		expect(asNumber(0)).toBe(0);
		expect(asNumber(42)).toBe(42);
		expect(asNumber(-1.5)).toBe(-1.5);
	});
	it('coerces null/undefined to 0', () => {
		expect(asNumber(null)).toBe(0);
		expect(asNumber(undefined)).toBe(0);
	});
	it('coerces non-finite to 0', () => {
		expect(asNumber(Number.NaN)).toBe(0);
		expect(asNumber(Number.POSITIVE_INFINITY)).toBe(0);
		expect(asNumber(Number.NEGATIVE_INFINITY)).toBe(0);
	});
});

describe('clampPercent', () => {
	it('clamps to [0, 100]', () => {
		expect(clampPercent(-10)).toBe(0);
		expect(clampPercent(0)).toBe(0);
		expect(clampPercent(50.5)).toBe(50.5);
		expect(clampPercent(100)).toBe(100);
		expect(clampPercent(150)).toBe(100);
	});
});

describe('shareOf', () => {
	it('returns 0 when total is non-positive', () => {
		expect(shareOf(10, 0)).toBe(0);
		expect(shareOf(10, -1)).toBe(0);
	});
	it('returns percentage of total clamped to 100', () => {
		expect(shareOf(50, 100)).toBe(50);
		expect(shareOf(25, 50)).toBe(50);
		expect(shareOf(200, 100)).toBe(100); // clamped
	});
});

describe('levelLabel', () => {
	it('maps severity to Korean label', () => {
		expect(levelLabel('normal')).toBe('정상');
		expect(levelLabel('warn')).toBe('주의');
		expect(levelLabel('danger')).toBe('위험');
	});
});

describe('compactBytes', () => {
	it('returns "0" for zero / null / NaN / undefined', () => {
		expect(compactBytes(0)).toBe('0');
		expect(compactBytes(null)).toBe('0');
		expect(compactBytes(undefined)).toBe('0');
		expect(compactBytes(Number.NaN)).toBe('0');
		expect(compactBytes(Number.POSITIVE_INFINITY)).toBe('0');
	});

	it('uses single-letter units (B/K/M/G/T)', () => {
		expect(compactBytes(1)).toBe('1.0B');
		expect(compactBytes(1024)).toBe('1.0K');
		expect(compactBytes(1024 * 1024)).toBe('1.0M');
		expect(compactBytes(1024 ** 3)).toBe('1.0G');
		expect(compactBytes(1024 ** 4)).toBe('1.0T');
	});

	it('caps at T for petabyte-scale (no PB in 5-unit set)', () => {
		expect(compactBytes(1024 ** 5)).toBe('1024T'); // overflow → keep in T
	});

	it('drops decimals for |v| ≥ 100 within unit', () => {
		// 384 MB ≈ 403MB - shows "384M" without decimal
		expect(compactBytes(384 * 1024 * 1024)).toBe('384M');
		expect(compactBytes(100 * 1024 * 1024)).toBe('100M');
		expect(compactBytes(99.9 * 1024 * 1024)).toBe('99.9M');
	});

	it('keeps 1 decimal for |v| < 100 within unit', () => {
		expect(compactBytes(1.2 * 1024 * 1024)).toBe('1.2M');
		expect(compactBytes(15.1 * 1024 * 1024 * 1024)).toBe('15.1G');
	});

	it('uses U+2212 minus for negative values', () => {
		expect(compactBytes(-1024)).toBe('−1.0K'); // U+2212 not ASCII -
	});

	it('matches the real API values from the production check', () => {
		// from the user-flow audit (current_metrics):
		// memory.usage = 403664896 B
		expect(compactBytes(403664896)).toBe('385M');
		// network.rx = 1241981
		expect(compactBytes(1241981)).toBe('1.2M');
		// network.tx = 15469628
		expect(compactBytes(15469628)).toBe('14.8M');
		// disk.read = 289550336
		expect(compactBytes(289550336)).toBe('276M');
		// disk.write = 110592
		expect(compactBytes(110592)).toBe('108K');
		// memFree = 16669347840 - 403664896 = 16265682944
		expect(compactBytes(16669347840 - 403664896)).toBe('15.1G');
	});
});

describe('formatDelta', () => {
	it('uses ± when |v| < epsilon (10^-digits / 2)', () => {
		expect(formatDelta(0, 1)).toBe('±0.0%');
		expect(formatDelta(0.04, 1)).toBe('±0.0%'); // 0.04 < 0.05
		expect(formatDelta(-0.002, 1)).toBe('±0.0%');
		expect(formatDelta(0.001, 2)).toBe('±0.00%'); // epsilon=0.005
	});

	it('uses + / − (U+2212) for values above epsilon', () => {
		expect(formatDelta(0.05, 1)).toBe('+0.1%'); // rounds to 0.1 (but ≥ epsilon)
		// .05 with toFixed(1) -> "0.1" because banker's rounding may go either way;
		// JS toFixed(1) of 0.05 is "0.1" or "0.0" depending on impl. Skip exact decimal edge.
		expect(formatDelta(1, 1)).toBe('+1.0%');
		expect(formatDelta(-1, 1)).toBe('−1.0%');
		expect(formatDelta(15.34, 1)).toBe('+15.3%');
	});

	it('respects digits parameter', () => {
		expect(formatDelta(1.234567, 2)).toBe('+1.23%');
		expect(formatDelta(1.234567, 0)).toBe('+1%');
	});

	it('matches real-world cases from production audit', () => {
		// GPU 코어 Δ: 0 − 0.2 = −0.2  → "−0.2%"
		expect(formatDelta(0 - 0.2, 1)).toBe('−0.2%');
		// CPU Δ: ±0.0% when near-zero
		expect(formatDelta(-0.0023, 1)).toBe('±0.0%');
	});
});

describe('deltaTone', () => {
	it('classifies as "flat" within ±0.5', () => {
		expect(deltaTone(0)).toBe('flat');
		expect(deltaTone(0.2)).toBe('flat');
		expect(deltaTone(-0.49)).toBe('flat');
	});

	it('returns "up" between [warnAt, 2*warnAt)', () => {
		expect(deltaTone(5)).toBe('up');
		expect(deltaTone(9.99)).toBe('up');
	});

	it('returns "up-warn" when v ≥ 2*warnAt', () => {
		expect(deltaTone(10)).toBe('up-warn');
		expect(deltaTone(50)).toBe('up-warn');
	});

	it('returns "down" when v ≤ -warnAt', () => {
		expect(deltaTone(-5)).toBe('down');
		expect(deltaTone(-20)).toBe('down');
	});

	it('values between (0.5, warnAt) and (-warnAt, -0.5) are flat', () => {
		expect(deltaTone(1)).toBe('flat');
		expect(deltaTone(4.99)).toBe('flat');
		expect(deltaTone(-1)).toBe('flat');
		expect(deltaTone(-4.99)).toBe('flat');
	});

	it('respects custom warnAt', () => {
		expect(deltaTone(10, 10)).toBe('up'); // == warnAt → up
		expect(deltaTone(20, 10)).toBe('up-warn'); // == 2*warnAt
		expect(deltaTone(-10, 10)).toBe('down');
	});
});

describe('pctRangeStatus', () => {
	it('normal message includes both thresholds', () => {
		expect(pctRangeStatus('normal', 70, 90)).toBe('정상 · 임계 70/90%');
		expect(pctRangeStatus('normal', 75, 90)).toBe('정상 · 임계 75/90%');
		expect(pctRangeStatus('normal', 80, 95)).toBe('정상 · 임계 80/95%');
	});

	it('warn shows warn threshold only', () => {
		expect(pctRangeStatus('warn', 70, 90)).toBe('주의 · ≥ 70%');
		expect(pctRangeStatus('warn', 80, 95)).toBe('주의 · ≥ 80%');
	});

	it('danger shows crit threshold only', () => {
		expect(pctRangeStatus('danger', 70, 90)).toBe('위험 · ≥ 90%');
		expect(pctRangeStatus('danger', 80, 95)).toBe('위험 · ≥ 95%');
	});

	it('messages stay within 135px width budget (≤ 19 chars rough heuristic)', () => {
		const widthBudget = 19;
		for (const level of ['normal', 'warn', 'danger'] as const) {
			for (const [w, c] of [
				[70, 90],
				[75, 90],
				[80, 95],
			] as const) {
				const msg = pctRangeStatus(level, w, c);
				expect(msg.length, `"${msg}" too long`).toBeLessThanOrEqual(widthBudget);
			}
		}
	});
});
