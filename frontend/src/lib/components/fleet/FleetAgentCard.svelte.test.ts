// @vitest-environment jsdom
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { FleetAgentRow } from '$lib/stores/fleet-store';
import FleetAgentCard from './FleetAgentCard.svelte';

function makeAgent(overrides: { gpuCount?: number; gpuUsage?: number; gpuTemp?: number | null } = {}): FleetAgentRow {
	const gpuCount = overrides.gpuCount ?? 0;
	const gpuUsage = overrides.gpuUsage ?? 0;
	const gpuTemp = overrides.gpuTemp ?? null;
	return {
		agent: {
			id: 'agent-1',
			hostname: 'test-server',
			ip_address: '10.0.0.1',
			is_active: true
		} as any,
		health: 'healthy' as any,
		health_reasons: [],
		latest: {
			timestamp: new Date().toISOString(),
			cpu_usage: 10,
			cpu_cores: 8,
			cpu_threads: 16,
			cpu_load_avg_1m: 0.5,
			memory_usage: 40,
			memory_used: 4 * 1024 ** 3,
			memory_total: 16 * 1024 ** 3,
			disk_usage: 30,
			disk_used: 100 * 1024 ** 3,
			disk_total: 500 * 1024 ** 3,
			network_rx_rate: 1024,
			network_tx_rate: 512,
			processes_total: 200,
			processes_running: 5,
			logins_total: 1,
			gpu_usage: gpuUsage,
			gpu_temperature: gpuTemp,
			gpu_memory_used: gpuCount > 0 ? 4 * 1024 ** 3 : null,
			gpu_memory_total: gpuCount > 0 ? 16 * 1024 ** 3 : null,
			gpu_count: gpuCount
		},
		containers: { running: 2, non_running: 3, problem: 0 } as any,
		sparkline: { cpu: [10, 10], memory: [40, 40], rx: [1024], tx: [512], gpu: [gpuUsage, gpuUsage] }
	} as unknown as FleetAgentRow;
}

describe('FleetAgentCard — GPU thermal/power chips', () => {
	it('no GPU → no thermal/power chips', () => {
		const { container } = render(FleetAgentCard, { props: { agent: makeAgent({ gpuCount: 0 }) } });
		expect(container.querySelector('.ct-chip.thermal')).toBeNull();
		expect(container.querySelector('.ct-chip.power')).toBeNull();
	});

	it('GPU 60°C 50% → thermal normal + power ~165W', () => {
		const { container } = render(FleetAgentCard, {
			props: { agent: makeAgent({ gpuCount: 1, gpuUsage: 50, gpuTemp: 60 }) }
		});
		const thermal = container.querySelector('.ct-chip.thermal') as HTMLElement;
		const power = container.querySelector('.ct-chip.power') as HTMLElement;
		expect(thermal).not.toBeNull();
		expect(power).not.toBeNull();
		expect(thermal.textContent).toMatch(/60°C/);
		expect(thermal.dataset.level).toBe('normal');
		// 30 + (300-30)*0.5 = 165W
		expect(power.textContent).toMatch(/~165W/);
	});

	it('GPU 75°C → thermal warn', () => {
		const { container } = render(FleetAgentCard, {
			props: { agent: makeAgent({ gpuCount: 1, gpuUsage: 80, gpuTemp: 75 }) }
		});
		const thermal = container.querySelector('.ct-chip.thermal') as HTMLElement;
		expect(thermal.dataset.level).toBe('warn');
	});

	it('GPU 86°C → thermal danger', () => {
		const { container } = render(FleetAgentCard, {
			props: { agent: makeAgent({ gpuCount: 1, gpuUsage: 90, gpuTemp: 86 }) }
		});
		const thermal = container.querySelector('.ct-chip.thermal') as HTMLElement;
		expect(thermal.dataset.level).toBe('danger');
	});

	it('GPU temp null → thermal "—" with informational title', () => {
		const { container } = render(FleetAgentCard, {
			props: { agent: makeAgent({ gpuCount: 1, gpuUsage: 0, gpuTemp: null }) }
		});
		const thermal = container.querySelector('.ct-chip.thermal') as HTMLElement;
		expect(thermal.textContent).toMatch(/—/);
		expect(thermal.title).toMatch(/온도값을 보내지 않음/);
	});

	it('power formula boundary: 0% → ~30W, 100% → ~300W', () => {
		const { container: c0 } = render(FleetAgentCard, {
			props: { agent: makeAgent({ gpuCount: 1, gpuUsage: 0, gpuTemp: 35 }) }
		});
		expect((c0.querySelector('.ct-chip.power') as HTMLElement).textContent).toMatch(/~30W/);
		const { container: c100 } = render(FleetAgentCard, {
			props: { agent: makeAgent({ gpuCount: 1, gpuUsage: 100, gpuTemp: 80 }) }
		});
		expect((c100.querySelector('.ct-chip.power') as HTMLElement).textContent).toMatch(/~300W/);
	});

	it('power chip tooltip mentions TDP assumption', () => {
		const { container } = render(FleetAgentCard, {
			props: { agent: makeAgent({ gpuCount: 1, gpuUsage: 50, gpuTemp: 60 }) }
		});
		const power = container.querySelector('.ct-chip.power') as HTMLElement;
		expect(power.title).toMatch(/TDP 300W/);
		expect(power.title).toMatch(/±100W/);
	});
});
