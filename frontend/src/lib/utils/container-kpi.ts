/**
 * ContainerKpiBar 의 pure helper 모음 — 컴포넌트와 단위 테스트가 함께 import.
 *
 * 모두 부수효과 없는 순수 함수. 입력 → 출력 형태로 컨테이너 KPI bar
 * (CPU/메모리/네트워크/디스크/GPU/VRAM) 의 표시 로직을 결정한다.
 */

export type Severity = 'normal' | 'warn' | 'danger';
export type DeltaTone = 'flat' | 'up' | 'up-warn' | 'down';

/** value ≥ crit → danger, value ≥ warn → warn, 아니면 normal. */
export function severity(value: number, warn: number, crit: number): Severity {
	if (value >= crit) return 'danger';
	if (value >= warn) return 'warn';
	return 'normal';
}

/** null / undefined / NaN / Infinity 를 0 으로 정규화 후 number 로 반환. */
export function asNumber(value: number | null | undefined): number {
	const n = Number(value ?? 0);
	return Number.isFinite(n) ? n : 0;
}

/** 0..100 으로 clamp (음수, 100 초과 안전). */
export function clampPercent(value: number): number {
	return Math.max(0, Math.min(100, value));
}

/** total 이 양수이면 (value/total)*100 을 0..100 으로 clamp, 아니면 0. */
export function shareOf(value: number, total: number): number {
	if (total <= 0) return 0;
	return clampPercent((value / total) * 100);
}

/** severity → 한국어 라벨. */
export function levelLabel(level: Severity): string {
	if (level === 'danger') return '위험';
	if (level === 'warn') return '주의';
	return '정상';
}

const COMPACT_UNITS = ['B', 'K', 'M', 'G', 'T'];

/**
 * 좁은 KPI 인사이트 pill(≈30~50px 내부 폭)에 들어가도록 단위를 한 글자로 압축.
 * 본문 차트와 hover tooltip 에서는 formatBytesValue 가 유지돼 정밀 단위 보임.
 *
 * - 0 / null / NaN / Infinity → '0'
 * - |v| ≥ 100 (해당 단위 안에서) → 정수 표기 ("384M")
 * - 그 외 → 소수 1자리 ("1.2M")
 * - 음수면 '−' (minus sign U+2212) 부호.
 */
export function compactBytes(value: number | null | undefined): string {
	if (value == null || !Number.isFinite(value) || value === 0) return '0';
	const abs = Math.abs(value);
	const i = Math.floor(Math.log(abs) / Math.log(1024));
	const idx = Math.max(0, Math.min(i, COMPACT_UNITS.length - 1));
	const v = value / Math.pow(1024, idx);
	const sign = v < 0 ? '−' : '';
	const av = Math.abs(v);
	const num = av >= 100 ? `${Math.round(av)}` : `${av.toFixed(1)}`;
	return `${sign}${num}${COMPACT_UNITS[idx]}`;
}

/**
 * 현재값 − 기간 평균 형태의 편차(% 단위)를 화면용 부호 표기로.
 *
 * - |v| < 10^(-digits)/2 (표시 자리수 미만 편차) → '±0.0%' — "−0.0%" 같은
 *   헷갈리는 부호 방지.
 * - 그 외 양수 → '+1.2%', 음수 → '−0.5%' (U+2212).
 */
export function formatDelta(value: number, digits = 1): string {
	const epsilon = Math.pow(10, -digits) / 2;
	if (Math.abs(value) < epsilon) return `±0.${'0'.repeat(digits)}%`;
	const sign = value > 0 ? '+' : '−';
	return `${sign}${Math.abs(value).toFixed(digits)}%`;
}

/**
 * Δ 편차값을 색조 등급으로 분류.
 *
 * 임계 (warnAt=5 기준):
 *   |v| < 0.5      → flat   (눈에 안 보이는 변화)
 *   v ≤ −5         → down   (의미 있는 하락)
 *   v ≥ 10         → up-warn (큰 상승)
 *   v ≥ 5          → up     (상승)
 *   그 외           → flat
 */
export function deltaTone(value: number, warnAt = 5): DeltaTone {
	if (Math.abs(value) < 0.5) return 'flat';
	if (value <= -warnAt) return 'down';
	if (value >= warnAt * 2) return 'up-warn';
	if (value >= warnAt) return 'up';
	return 'flat';
}

/**
 * status-line 자연어. severity 임계 정보 + 현재 위치를 한 줄로 요약.
 * 본문 차트의 markLine 과 의미 일치. 좁은 KPI 카드(135~150px) 에 들어가도록
 * 단어 압축 — 정상에선 raw 임계값만, 경보 시엔 등급 라벨 + 임계.
 */
export function pctRangeStatus(level: Severity, warn: number, crit: number): string {
	if (level === 'danger') return `위험 · ≥ ${crit}%`;
	if (level === 'warn') return `주의 · ≥ ${warn}%`;
	return `정상 · 임계 ${warn}/${crit}%`;
}
