// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import ResourceLimitForm from './ResourceLimitForm.svelte';

describe('ResourceLimitForm', () => {
	it('renders recommended resource values and host share labels', () => {
		render(ResourceLimitForm, {
			props: {
				cpuPercent: 400,
				memoryMb: 16384,
				workspaceGb: 100,
				recommendedCpuPercent: 400,
				recommendedMemoryMb: 16384,
				recommendedWorkspaceGb: 100,
				hostCpuCores: 24,
				hostMemoryMb: 262144,
				hostWorkspacePoolGb: 3000,
				hostWorkspacePoolFreeGb: 2900,
				hostWorkspaceHardEnforcement: true,
			},
		});

		expect(screen.getByText('4.0 cores')).toBeInTheDocument();
		expect(screen.getByText('16 GB')).toBeInTheDocument();
		expect(screen.getByText('100 GB')).toBeInTheDocument();
		// CPU 400 / (24 cores * 100) ≈ 17%
		expect(screen.getByText('host의 17% 점유')).toBeInTheDocument();
		// Workspace label inlines the hard-enforced status via an {#if} block,
		// so the rendered DOM contains the suffix in a sibling text node.
		expect(screen.getByText(/hard enforced/)).toBeInTheDocument();
	});

	it('shows warning when direct input goes below template floors', async () => {
		const { container } = render(ResourceLimitForm, {
			props: {
				cpuPercent: 200,
				memoryMb: 4096,
				workspaceGb: 20,
				useRecommendation: false,
				minCpuPercent: 200,
				minMemoryMb: 4096,
				minWorkspaceGb: 20,
			},
		});

		const cpuInput = container.querySelector('input[name="cpu-percent"]') as HTMLInputElement;
		await fireEvent.input(cpuInput, { target: { value: '100' } });

		expect(screen.getByText(/작업 손실 위험/)).toBeInTheDocument();
	});
});
