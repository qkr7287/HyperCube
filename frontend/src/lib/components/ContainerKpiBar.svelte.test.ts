// @vitest-environment jsdom
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import ContainerKpiBar from './ContainerKpiBar.svelte';

const baseProps = {
	currentMetrics: {
		cpu: { usage: 5, cores: 12 },
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
				gpuMemPeak: 69.3,
				currentMetrics: {
					...baseProps.currentMetrics,
					gpu: { usage: 0, memoryUsed: 5723127808, memoryTotal: 8589934592 }
				}
			}
		});
		const cards = container.querySelectorAll('.kpi');
		expect(cards.length).toBe(6);
		expect(screen.getByText('GPU 코어')).toBeInTheDocument();
		expect(screen.getByText('GPU VRAM')).toBeInTheDocument();
	});

	it('CPU normal → kpi level=normal + chip "정상"', () => {
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const cpuCard = container.querySelector('.kpi[data-level="normal"]');
		expect(cpuCard).not.toBeNull();
		const chip = cpuCard!.querySelector('.kpi-chip') as HTMLElement;
		expect(chip.dataset.level).toBe('normal');
		expect(chip.textContent?.trim()).toBe('정상');
	});

	it('CPU at warn threshold (70%) → level=warn + chip "주의"', () => {
		const props = {
			...baseProps,
			currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 70, cores: 12 } }
		};
		const { container } = render(ContainerKpiBar, { props });
		const cpuCard = container.querySelector('.kpi') as HTMLElement;
		expect(cpuCard.dataset.level).toBe('warn');
		expect(cpuCard.querySelector('.kpi-chip')?.textContent?.trim()).toBe('주의');
	});

	it('CPU danger (95%) → level=danger + chip "위험"', () => {
		const props = {
			...baseProps,
			currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 95, cores: 12 } }
		};
		const { container } = render(ContainerKpiBar, { props });
		const cpuCard = container.querySelector('.kpi') as HTMLElement;
		expect(cpuCard.dataset.level).toBe('danger');
		expect(cpuCard.querySelector('.kpi-chip')?.textContent?.trim()).toBe('위험');
	});

	it('Δ row shows ±0.0% + tone=flat when current ≈ avg', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 4.5, cores: 12 } },
				cpuAvg: 4.5
			}
		});
		const cpuCard = container.querySelectorAll('.kpi')[0] as HTMLElement;
		const deltaRow = cpuCard.querySelector('.foot-row.delta[data-tone]') as HTMLElement;
		expect(deltaRow).not.toBeNull();
		expect(deltaRow.textContent).toContain('±0.0%');
		expect(deltaRow.dataset.tone).toBe('flat');
	});

	it('Δ row shows "+" tone=up-warn when current >> avg', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 25, cores: 12 } },
				cpuAvg: 5
			}
		});
		const cpuCard = container.querySelectorAll('.kpi')[0] as HTMLElement;
		const deltaRow = cpuCard.querySelector('.foot-row.delta[data-tone]') as HTMLElement;
		expect(deltaRow.textContent).toContain('+20.0%');
		expect(deltaRow.dataset.tone).toBe('up-warn');
	});

	it('Δ row shows tone=down when current << avg', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				currentMetrics: { ...baseProps.currentMetrics, cpu: { usage: 5, cores: 12 } },
				cpuAvg: 15
			}
		});
		const cpuCard = container.querySelectorAll('.kpi')[0] as HTMLElement;
		const deltaRow = cpuCard.querySelector('.foot-row.delta[data-tone]') as HTMLElement;
		expect(deltaRow.textContent).toContain('−10.0%');
		expect(deltaRow.dataset.tone).toBe('down');
	});

	it('CPU hero shows both % and raw cores ("0.60 cores" 형태)', () => {
		// 5% * 12 cores / 100 = 0.60 cores
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const cpuCard = container.querySelectorAll('.kpi')[0] as HTMLElement;
		const hero = cpuCard.querySelector('.kpi-hero') as HTMLElement;
		expect(hero.textContent).toMatch(/5\.00/);
		expect(hero.textContent).toMatch(/cores/);
	});

	it('memory hero shows both % and raw bytes (예: "200M")', () => {
		// memory.usage = 200MB → compactBytes "200M"
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const memCard = container.querySelectorAll('.kpi')[1] as HTMLElement;
		const hero = memCard.querySelector('.kpi-hero') as HTMLElement;
		expect(hero.textContent).toMatch(/5\.00/);
		expect(hero.textContent).toMatch(/M/);
	});

	it('shows quota limit chips and used over limit raw text', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				cpuPercentLimit: 400,
				memoryMbLimit: 16 * 1024
			}
		});
		const cpuCard = container.querySelectorAll('.kpi')[0] as HTMLElement;
		const memCard = container.querySelectorAll('.kpi')[1] as HTMLElement;
		expect(cpuCard.querySelector('.limit-chip')?.textContent).toContain('limit 4 cores');
		expect(memCard.querySelector('.limit-chip')?.textContent).toContain('limit 16 GB');
		expect(cpuCard.querySelector('.kpi-hero')?.textContent).toContain('/ 4 cores');
		expect(memCard.querySelector('.kpi-hero')?.textContent).toContain('/ 16G');
	});

	it('shows unlimited when container limit fields are missing', () => {
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const cpuCard = container.querySelectorAll('.kpi')[0] as HTMLElement;
		expect(cpuCard.querySelector('.limit-chip')?.textContent).toContain('unlimited');
	});

	it('adds workspace disk card when workspace quota or metric exists', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				workspaceGbLimit: 100,
				currentMetrics: {
					...baseProps.currentMetrics,
					workspace: { hardGb: 100, usedGb: 12, usedPct: 12, path: '/var/lib/hypercube/workspaces/abc' }
				}
			}
		});
		const cards = container.querySelectorAll('.kpi');
		expect(cards.length).toBe(5);
		expect(screen.getByText('Workspace')).toBeInTheDocument();
		expect([...container.querySelectorAll('.limit-chip')].some((el) => el.textContent?.includes('limit 100 GB'))).toBe(true);
	});

	it('falls back to legacy sizeGb wire from a pre-rework agent', () => {
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				workspaceGbLimit: null,
				currentMetrics: {
					...baseProps.currentMetrics,
					workspace: { sizeGb: 80, usedGb: 8, usedPct: 10, device: '/dev/vg0/cid_legacy' }
				}
			}
		});
		const cards = container.querySelectorAll('.kpi');
		expect(cards.length).toBe(5);
	});

	it('memory foot rows show raw bytes alongside %', () => {
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const memCard = container.querySelectorAll('.kpi')[1] as HTMLElement;
		const foot = memCard.querySelector('.kpi-foot')?.textContent ?? '';
		expect(foot).toMatch(/AVG/);
		expect(foot).toMatch(/PEAK/);
		// memAvgPct=5, memLimit=4GB → 200MB → "200M" raw
		expect(foot).toMatch(/M/);
	});

	it('network card uses split bar (.kpi.flow) and shows RX/TX bytes', () => {
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const netCard = container.querySelectorAll('.kpi')[2] as HTMLElement;
		expect(netCard.classList.contains('flow')).toBe(true);
		expect(netCard.dataset.colorA).toBe('teal');
		expect(netCard.dataset.colorB).toBe('amber');
		expect(netCard.querySelector('.split-meter')).not.toBeNull();
		const foot = netCard.querySelector('.kpi-foot')?.textContent ?? '';
		expect(foot).toMatch(/RX/);
		expect(foot).toMatch(/TX/);
	});

	it('network Δ row shows "—" + tone=flat when no delta', () => {
		const { container } = render(ContainerKpiBar, { props: baseProps });
		const netCard = container.querySelectorAll('.kpi')[2];
		const delta = netCard.querySelector('.foot-row.delta') as HTMLElement;
		expect(delta.textContent).toContain('—');
		expect(delta.dataset.tone).toBe('flat');
	});

	it('network Δ row shows "+X" + tone=up when delta > 0', () => {
		const props = { ...baseProps, netRxDelta: 1024 * 10, netTxDelta: 1024 * 5 };
		const { container } = render(ContainerKpiBar, { props });
		const netCard = container.querySelectorAll('.kpi')[2];
		const delta = netCard.querySelector('.foot-row.delta') as HTMLElement;
		expect(delta.textContent).toContain('+');
		expect(delta.dataset.tone).toBe('up');
	});

	it('Δ near-zero variants from production audit (VRAM)', () => {
		// VRAM 평균 = 66.6, 현재 = 66.63 → delta 0.03 → ±0.0%
		const { container } = render(ContainerKpiBar, {
			props: {
				...baseProps,
				hasGpuMem: true,
				currentGpuMemPct: 66.63,
				gpuMemAvg: 66.6,
				gpuMemPeak: 69.3,
				currentMetrics: {
					...baseProps.currentMetrics,
					gpu: { memoryUsed: 5723127808, memoryTotal: 8589934592 }
				}
			}
		});
		const vramCard = [...container.querySelectorAll('.kpi')].at(-1) as HTMLElement;
		const deltaRow = vramCard.querySelector('.foot-row.delta[data-tone]') as HTMLElement;
		expect(deltaRow.textContent).toContain('±0.0%');
	});
});
