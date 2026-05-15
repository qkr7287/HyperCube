<script lang="ts">
	let {
		cpuPercent = $bindable(100),
		memoryMb = $bindable(2048),
		workspaceGb = $bindable(10),
		useRecommendation = $bindable(true),
		recommendedCpuPercent = 100,
		recommendedMemoryMb = 2048,
		recommendedWorkspaceGb = 10,
		minCpuPercent = 100,
		minMemoryMb = 2048,
		minWorkspaceGb = 10,
		hostCpuCores = null as number | null,
		hostMemoryMb = null as number | null,
		hostLvmPoolGb = null as number | null,
		loading = false,
	}: {
		cpuPercent?: number;
		memoryMb?: number;
		workspaceGb?: number;
		useRecommendation?: boolean;
		recommendedCpuPercent?: number;
		recommendedMemoryMb?: number;
		recommendedWorkspaceGb?: number;
		minCpuPercent?: number;
		minMemoryMb?: number;
		minWorkspaceGb?: number;
		hostCpuCores?: number | null;
		hostMemoryMb?: number | null;
		hostLvmPoolGb?: number | null;
		loading?: boolean;
	} = $props();

	let cpuMax = $derived(Math.max(100, (hostCpuCores ?? 0) * 100, recommendedCpuPercent, minCpuPercent, cpuPercent));
	let memoryMax = $derived(
		Math.max(1024, (hostMemoryMb ? Math.max(1024, hostMemoryMb - 4096) : 0), recommendedMemoryMb, minMemoryMb, memoryMb),
	);
	let workspaceMax = $derived(Math.max(10, hostLvmPoolGb ?? 0, recommendedWorkspaceGb, minWorkspaceGb, workspaceGb));
	let cpuHostShare = $derived(hostCpuCores ? Math.round((cpuPercent / (hostCpuCores * 100)) * 100) : null);
	let memoryHostShare = $derived(hostMemoryMb ? Math.round((memoryMb / hostMemoryMb) * 100) : null);
	let workspaceHostShare = $derived(hostLvmPoolGb ? Math.round((workspaceGb / hostLvmPoolGb) * 100) : null);
	let hasWarning = $derived(cpuPercent < minCpuPercent || memoryMb < minMemoryMb || workspaceGb < minWorkspaceGb);

	$effect(() => {
		if (!useRecommendation) return;
		cpuPercent = recommendedCpuPercent;
		memoryMb = recommendedMemoryMb;
		workspaceGb = recommendedWorkspaceGb;
	});

	function gb(value: number) {
		return Math.round(value / 1024);
	}
</script>

<section class="resource-form" aria-label="자원 한도">
	<div class="resource-head">
		<div>
			<h3>2. 자원 한도</h3>
			<p>{loading ? '추천값 계산 중' : 'host capacity 기반 추천값을 사용할 수 있습니다.'}</p>
		</div>
		<label class="mode-toggle">
			<input type="checkbox" bind:checked={useRecommendation} />
			<span>{useRecommendation ? '추천 사용' : '직접 입력'}</span>
		</label>
	</div>

	<div class="limit-grid">
		<div class="limit-row" data-warning={cpuPercent < minCpuPercent}>
			<div class="limit-label">
				<span>CPU</span>
				<strong>{(cpuPercent / 100).toFixed(1)} cores</strong>
			</div>
			<input
				name="cpu-percent"
				type="range"
				min="100"
				max={cpuMax}
				step="50"
				bind:value={cpuPercent}
				disabled={useRecommendation}
			/>
			<div class="limit-meta">
				<span>최소 {(minCpuPercent / 100).toFixed(1)} cores</span>
				<span>{cpuHostShare === null ? 'host 정보 없음' : `host의 ${cpuHostShare}% 점유`}</span>
			</div>
			<input class="limit-input" type="number" min="0" step="50" bind:value={cpuPercent} disabled={useRecommendation} />
		</div>

		<div class="limit-row" data-warning={memoryMb < minMemoryMb}>
			<div class="limit-label">
				<span>메모리</span>
				<strong>{gb(memoryMb)} GB</strong>
			</div>
			<input
				name="memory-mb"
				type="range"
				min="1024"
				max={memoryMax}
				step="1024"
				bind:value={memoryMb}
				disabled={useRecommendation}
			/>
			<div class="limit-meta">
				<span>최소 {gb(minMemoryMb)} GB</span>
				<span>{memoryHostShare === null ? 'host 정보 없음' : `host의 ${memoryHostShare}% 점유`}</span>
			</div>
			<input class="limit-input" type="number" min="0" step="1024" bind:value={memoryMb} disabled={useRecommendation} />
		</div>

		<div class="limit-row" data-warning={workspaceGb < minWorkspaceGb}>
			<div class="limit-label">
				<span>Workspace</span>
				<strong>{workspaceGb} GB</strong>
			</div>
			<input
				name="workspace-gb"
				type="range"
				min="10"
				max={workspaceMax}
				step="10"
				bind:value={workspaceGb}
				disabled={useRecommendation}
			/>
			<div class="limit-meta">
				<span>최소 {minWorkspaceGb} GB</span>
				<span>{workspaceHostShare === null ? 'thin pool 정보 없음' : `host의 ${workspaceHostShare}% 점유`}</span>
			</div>
			<input class="limit-input" type="number" min="0" step="10" bind:value={workspaceGb} disabled={useRecommendation} />
		</div>
	</div>

	{#if hasWarning}
		<div class="limit-warning">작업 손실 위험: 템플릿의 최소 실행 한도보다 낮습니다.</div>
	{/if}
</section>

<style>
	.resource-form {
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
		padding: 12px;
	}

	.resource-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 12px;
		margin-bottom: 12px;
	}

	h3,
	p {
		margin: 0;
	}

	h3 {
		font-size: 13px;
		color: var(--text-secondary);
	}

	p,
	.limit-meta {
		font-size: 11px;
		color: var(--text-muted);
	}

	.mode-toggle {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 32px;
		padding: 0 10px;
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 900;
		cursor: pointer;
		white-space: nowrap;
	}

	.mode-toggle input {
		width: 16px;
		min-height: 16px;
		accent-color: var(--accent);
	}

	.limit-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 10px;
	}

	.limit-row {
		display: grid;
		gap: 8px;
		min-width: 0;
		padding: 10px;
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-radius: 8px;
		background: rgba(2, 6, 12, 0.26);
	}

	.limit-row[data-warning='true'] {
		border-color: rgba(239, 68, 68, 0.48);
	}

	.limit-label,
	.limit-meta {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		align-items: center;
	}

	.limit-label span {
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 900;
	}

	.limit-label strong {
		color: var(--text-primary);
		font-size: 14px;
	}

	input[type='range'] {
		width: 100%;
		accent-color: var(--accent);
	}

	.limit-input {
		width: 100%;
		min-height: 32px;
		padding: 0 8px;
		border: 1px solid var(--border);
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.64);
		color: var(--text-primary);
		font: inherit;
	}

	.limit-warning {
		margin-top: 10px;
		padding: 9px 10px;
		border: 1px solid rgba(239, 68, 68, 0.32);
		border-radius: 8px;
		background: rgba(239, 68, 68, 0.08);
		color: var(--error);
		font-size: 12px;
		font-weight: 800;
	}

	@media (max-width: 900px) {
		.resource-head,
		.limit-label,
		.limit-meta {
			flex-direction: column;
			align-items: flex-start;
		}

		.limit-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
