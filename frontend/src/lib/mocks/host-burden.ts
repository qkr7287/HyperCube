/**
 * HostBurdenPanel mock data — Level 1 추정 (단순 비율, host idle 미보정).
 *
 * 진짜 데이터 path:
 *   - host CPU power (W): RAPL package energy (agent 미수집, TODO)
 *   - host GPU power (W): nvidia-smi power.draw (agent 미수집, TODO)
 *   - host GPU temp (°C): nvidia-smi temperature.gpu (agent payload 에 없음, TODO)
 *   - container CPU% / GPU%: ContainerMetricsHistory (이미 수집 중)
 *
 * 실 데이터 들어오면 generateSample() 자리만 fetcher 로 교체. 게이지/sparkline 컴포넌트
 * (HostBurdenPanel.svelte) 는 BurdenSnapshot 구조에 의존하므로 schema 만 동일하게 유지.
 */

export type BurdenMetric = {
	hostValue: number;       // 호스트 현재값 (W or °C)
	hostMax: number;         // 100% 환산 기준 (TDP / 임계 max temp)
	containerShare: number;  // 0~1 — 호스트 값 중 컨테이너 기여 비율 (Level 1: cpu_pct ratio)
	zones?: {                // 게이지 색 zone 경계
		ok: number;
		warn: number;
		danger: number;
	};
	sparkline: number[];     // 최근 N 포인트 (호스트 값 추세)
};

export type BurdenBreakdown = {
	thisContainerW: number;     // 이 컨테이너 추정 W
	otherContainersW: number;   // 다른 컨테이너 합산 추정 W (mock)
	idleW: number;              // host idle baseline 추정 W (RAPL package - dynamic 등)
	headroomW: number;          // max - 현재 host total
};

export type BurdenSnapshot = {
	gpuTemp: BurdenMetric;   // °C
	gpuPower: BurdenMetric;  // W
	cpuPower: BurdenMetric;  // W
	totalPower: BurdenMetric & {
		breakdown: BurdenBreakdown;
		thisContainerPct: number; // hostValue 중 이 컨테이너 비율 (0~1)
	};
	// 호스트 최고 온도 — GPU 와 CPU 중 더 뜨거운 값. mock 은 GPU 만 추적해서 그대로 사용.
	// containerDeltaC = 이 컨테이너 워크로드가 idle 대비 끌어올린 추정 온도 상승분.
	maxTemp: BurdenMetric & {
		hotspot: 'GPU' | 'CPU';
		idleBaselineC: number;   // ambient + cooling 으로 도달 가능한 호스트 최저 (대략)
		containerDeltaC: number; // (현재 - idle) × 컨테이너 사용량 비율
	};
	updatedAt: number;       // epoch ms
};

const SPARK_LEN = 32;

function clamp(value: number, min: number, max: number): number {
	return Math.min(Math.max(value, min), max);
}

function jitter(base: number, amplitude: number): number {
	return base + (Math.random() - 0.5) * 2 * amplitude;
}

function rollSpark(prev: number[], next: number): number[] {
	const tail = prev.length >= SPARK_LEN ? prev.slice(1) : prev.slice();
	tail.push(next);
	return tail;
}

function seedSpark(base: number, amplitude: number): number[] {
	return Array.from({ length: SPARK_LEN }, () => Math.max(0, jitter(base, amplitude)));
}

let lastSnapshot: BurdenSnapshot | null = null;

/**
 * 호출할 때마다 살짝 흔들리는 새 snapshot 반환.
 * containerShare 는 0.18 ~ 0.62 사이를 천천히 움직임 — "이 컨테이너가 호스트의 N% 부담".
 */
export function generateSample(): BurdenSnapshot {
	const prevGpuT = lastSnapshot?.gpuTemp.hostValue ?? 62;
	const prevGpuP = lastSnapshot?.gpuPower.hostValue ?? 95;
	const prevCpuP = lastSnapshot?.cpuPower.hostValue ?? 48;
	const prevShare = lastSnapshot?.gpuPower.containerShare ?? 0.42;

	const nextGpuT = clamp(jitter(prevGpuT, 1.2), 35, 88);
	const nextGpuP = clamp(jitter(prevGpuP, 5), 30, 200);
	const nextCpuP = clamp(jitter(prevCpuP, 2.5), 12, 110);
	const nextShare = clamp(jitter(prevShare, 0.04), 0.05, 0.85);

	const cpuContainerShare = clamp(nextShare * 0.6, 0.03, 0.7);
	const idleW = 45; // mock — RAPL package idle 추정
	const gpuContainerW = nextGpuP * nextShare;
	const cpuContainerWVal = nextCpuP * cpuContainerShare;
	const thisContainerW = gpuContainerW + cpuContainerWVal;
	const hostTotalNow = nextGpuP + nextCpuP + idleW;
	const totalMax = 200 + 125 + idleW; // gpu TDP + cpu PL2 + idle
	const otherContainersW = clamp((hostTotalNow - idleW - thisContainerW) * 0.35, 0, hostTotalNow);
	const headroomW = Math.max(0, totalMax - hostTotalNow);
	const thisContainerPct = hostTotalNow > 0 ? thisContainerW / hostTotalNow : 0;

	const snap: BurdenSnapshot = {
		gpuTemp: {
			hostValue: nextGpuT,
			hostMax: 90,
			containerShare: nextShare,
			zones: { ok: 70, warn: 80, danger: 85 },
			sparkline: rollSpark(lastSnapshot?.gpuTemp.sparkline ?? seedSpark(prevGpuT, 4), nextGpuT),
		},
		gpuPower: {
			hostValue: nextGpuP,
			hostMax: 200, // RTX 3060 Ti TDP
			containerShare: nextShare,
			zones: { ok: 120, warn: 160, danger: 185 },
			sparkline: rollSpark(lastSnapshot?.gpuPower.sparkline ?? seedSpark(prevGpuP, 15), nextGpuP),
		},
		cpuPower: {
			hostValue: nextCpuP,
			hostMax: 125, // i5-10400 PL2 근사
			containerShare: cpuContainerShare,
			zones: { ok: 70, warn: 95, danger: 115 },
			sparkline: rollSpark(lastSnapshot?.cpuPower.sparkline ?? seedSpark(prevCpuP, 8), nextCpuP),
		},
		totalPower: {
			hostValue: hostTotalNow,
			hostMax: totalMax,
			containerShare: thisContainerPct,
			thisContainerPct,
			zones: {
				ok: totalMax * 0.55,
				warn: totalMax * 0.75,
				danger: totalMax * 0.9,
			},
			sparkline: rollSpark(
				lastSnapshot?.totalPower.sparkline ?? seedSpark(hostTotalNow, 20),
				hostTotalNow,
			),
			breakdown: {
				thisContainerW,
				otherContainersW,
				idleW,
				headroomW,
			},
		},
		maxTemp: {
			hostValue: nextGpuT,
			hostMax: 90,
			containerShare: nextShare, // 발열 기여 ≈ GPU 사용량 비율
			zones: { ok: 70, warn: 80, danger: 85 },
			sparkline: rollSpark(
				lastSnapshot?.maxTemp.sparkline ?? seedSpark(prevGpuT, 4),
				nextGpuT,
			),
			hotspot: 'GPU',
			idleBaselineC: 38, // mock — GPU idle 평형 온도
			containerDeltaC: Math.max(0, (nextGpuT - 38) * nextShare),
		},
		updatedAt: Date.now(),
	};

	lastSnapshot = snap;
	return snap;
}

export function resetMock(): void {
	lastSnapshot = null;
}
