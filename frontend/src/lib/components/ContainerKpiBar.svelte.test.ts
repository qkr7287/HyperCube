// @vitest-environment jsdom
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import ContainerKpiBar from './ContainerKpiBar.svelte';

const baseProps = {
	currentMetrics: {
		cpu: { usage: 5 },
		memory: { usage: 1024 * 1024 * 200, limit: 1024 * 1024 * 1024 * 4, percent: 5 },
		network: { rx: 1024 * 1024, tx: 1024 * 1024 * 2 },
		disk: { read: 1024 * 1024 * 10, write: 1024 * 5 }
	},
	history: [
		{
			cpu_usage: 5,
			cpu_usage_max: 8,
			memory_percent: 5,
			memory_percent_max: 5,
			network_rx: 1024 * 1024,
			network_tx: 1024 * 1024 * 2,
			disk_read: 1024 * 1024 * 10,
			disk_write: 1024 * 5,
			gpu_usage: null
		}
	],
	rangeLabel: '1H',
	cpuAvg: 4.5,
	cpuPeak: 8.0,
	memAvgPct: 5.0,
	memPeakPct: 5.0,
	netRxDelta: 0,
	netTxDelta: 0,
	diskReadDelta: 0,
	diskWriteDelta: 0
};

describe('ContainerKpiBar', () => {
	it('renders 4 cards (CPU/Memory/Network/Disk) for non-GPU container', () => {
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const cards = container.querySelectorAll('.kpi');
		expect(cards.length).toBe(4);
	});

	it('renders 6 cards (adds GPU core + VRAM) when hasGpu + hasGpuMem', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				hasGpu: true,
				currentGpuUsage: 0,
				gpuAvg: 0.2,
				gpuPeak: 99.0,
				hasGpuMem: true,
				currentGpuMemPct: 66.63,
				gpuMemAvg: 66.6,
				gpuMemPeak: 69.3
			}
		});
		const cards = container.querySelectorAll('.kpi');
		expect(cards.length).toBe(6);
		expect(screen.getByText('GPU (코어)')).toBeInTheDocument();
		expect(screen.getByText('GPU (VRAM)')).toBeInTheDocument();
	});

	it('CPU normal severity → status-line "정상" + scope dot data-level=normal', () => {
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const cpuCard = container.querySelector('.kpi[data-level="normal"]');
		expect(cpuCard).not.toBeNull();
		const statusLine = cpuCard!.querySelector('.status-line') as HTMLElement;
		expect(statusLine.dataset.level).toBe('normal');
		expect(statusLine.textContent).toContain('정상');
		expect(statusLine.textContent).toContain('70/90');
		const dot = cpuCard!.querySelector('.scope.dot') as HTMLElement;
		expect(dot.dataset.level).toBe('normal');
	});

	it('CPU at warn threshold (70%) → status-line "주의 · ≥ 70%"', () => {
		const props = {
			...baseProps,
			currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 70 } }
		};
		const { container } = render(ContainerKpiBar, { props });
		const cpuCard = container.querySelector('.kpi') as HTMLElement;
		expect(cpuCard.dataset.level).toBe('warn');
		expect(cpuCard.querySelector('.status-line')?.textContent).toContain('주의');
		expect(cpuCard.querySelector('.status-line')?.textContent).toContain('≥ 70%');
	});

	it('CPU danger (95%) → status-line "위험 · ≥ 90%"', () => {
		const props = {
			...baseProps,
			currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 95 } }
		};
		const { container } = render(ContainerKpiBar, { props });
		const cpuCard = container.querySelector('.kpi') as HTMLElement;
		expect(cpuCard.dataset.level).toBe('danger');
		expect(cpuCard.querySelector('.status-line')?.textContent).toContain('위험');
	});

	it('Δ 평균 pill shows ±0.0% when current ≈ avg (near-zero epsilon)', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 4.5 } },
				cpuAvg: 4.5
			}
		});
		const deltaPill = container.querySelector(
			'.kpi[data-level] .insight-row > span[data-tone]'
		) as HTMLElement;
		expect(deltaPill).not.toBeNull();
		expect(deltaPill.textContent).toContain('±0.0%');
		expect(deltaPill.dataset.tone).toBe('flat');
	});

	it('Δ 평균 pill shows "+" tone "up-warn" when current >> avg', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 25 } },
				cpuAvg: 5
			}
		});
		const cpuCard = container.querySelector('.kpi') as HTMLElement;
		const deltaPill = cpuCard.querySelector(
			'.insight-row > span[data-tone]'
		) as HTMLElement;
		expect(deltaPill.textContent).toContain('+20.0%');
		expect(deltaPill.dataset.tone).toBe('up-warn');
	});

	it('Δ 평균 pill shows tone "down" when current << avg', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 5 } },
				cpuAvg: 15
			}
		});
		const cpuCard = container.querySelector('.kpi') as HTMLElement;
		const deltaPill = cpuCard.querySelector(
			'.insight-row > span[data-tone]'
		) as HTMLElement;
		expect(deltaPill.textContent).toContain('−10.0%');
		expect(deltaPill.dataset.tone).toBe('down');
	});

	it('memory insight pills use compactBytes (no "MB" word)', () => {
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const memCard = container.querySelectorAll('.kpi')[1] as HTMLElement;
		const text = memCard.querySelector('.insight-row.triple')?.textContent ?? '';
		// 200 MB usage / 4 GB limit → 사용 200M, 여유 ~3.8G, 피크 5.0%
		expect(text).toMatch(/사용\s*200M/);
		expect(text).toMatch(/여유\s*3\.8G/);
		expect(text).not.toMatch(/200\s*MB/); // verbose form excluded
	});

	it('network status-line shows "정체" when no delta', () => {
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const netCard = container.querySelectorAll('.kpi')[2];
		expect(netCard.querySelector('.status-line')?.textContent).toContain('정체');
		expect(netCard.querySelector('.status-line')?.getAttribute('data-flow')).toBe('idle');
	});

	it('network status-line shows "+" when delta > 0', () => {
		const props = { ...baseProps, netRxDelta: 1024 * 10, netTxDelta: 1024 * 5 };
		const { container } = render(ContainerKpiBar, { props });
		const netCard = container.querySelectorAll('.kpi')[2];
		const sl = netCard.querySelector('.status-line') as HTMLElement;
		expect(sl.textContent).toContain('+');
		expect(sl.dataset.flow).toBe('active');
	});

	it('Δ near-zero variants from production audit', () => {
		// VRAM 평균 = 66.6, 현재 = 66.63 → delta 0.03 → ±0.0%
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				hasGpuMem: true,
				currentGpuMemPct: 66.63,
				gpuMemAvg: 66.6,
				gpuMemPeak: 69.3
			}
		});
		const vramCard = [...container.querySelectorAll('.kpi')].at(-1) as HTMLElement;
		const deltaPill = vramCard.querySelector(
			'.insight-row > span[data-tone]'
		) as HTMLElement;
		expect(deltaPill.textContent).toContain('±0.0%');
	});
});
