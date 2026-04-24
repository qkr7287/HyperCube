<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import { view, type Server2dStateFilter } from '$lib/stores/server2d-view.svelte';

	let {
		total,
		running,
		paused,
		problem,
		stopped,
		networkRate = 0,
		imageCount = 0,
		dockerVersion = '-',
	}: {
		total: number;
		running: number;
		paused: number;
		problem: number;
		stopped: number;
		networkRate?: number;
		imageCount?: number;
		dockerVersion?: string;
	} = $props();

	function toggleFilter(next: Server2dStateFilter) {
		view.stateFilter = view.stateFilter === next && next !== 'all' ? 'all' : next;
	}

	function formatRate(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let index = 0;
		while (next >= 1024 && index < units.length - 1) {
			next /= 1024;
			index += 1;
		}
		return `${next.toFixed(next >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
	}
</script>

<div class="kpi-row">
	<button
		type="button"
		class="kpi all"
		class:active={view.stateFilter === 'all'}
		onclick={() => toggleFilter('all')}
		title="모든 컨테이너 보기"
	>
		<span>전체 <InfoTooltip text="서버에서 관찰된 컨테이너 총 개수입니다. 중지·일시정지·문제 포함 전체." placement="bottom-start" /></span>
		<strong>{total}</strong>
	</button>
	<button
		type="button"
		class="kpi running"
		class:active={view.stateFilter === 'running'}
		onclick={() => toggleFilter('running')}
		title="실행 중 컨테이너만 보기"
	>
		<span>실행 <InfoTooltip text="정상적으로 동작 중인 컨테이너입니다. 클릭하면 하단 Stack Explorer가 실행 상태만 필터합니다." placement="bottom-start" /></span>
		<strong>{running}</strong>
	</button>
	<button
		type="button"
		class="kpi paused"
		class:active={view.stateFilter === 'paused'}
		onclick={() => toggleFilter('paused')}
		title="일시정지 컨테이너만 보기"
	>
		<span>일시정지 <InfoTooltip text="docker pause로 멈춰 있는 상태입니다. 프로세스는 살아있지만 동작하지 않습니다." placement="bottom-start" /></span>
		<strong>{paused}</strong>
	</button>
	<button
		type="button"
		class="kpi problem"
		class:active={view.stateFilter === 'problem'}
		onclick={() => toggleFilter('problem')}
		title="문제 컨테이너만 보기"
	>
		<span>문제 <InfoTooltip text="재시작 루프 또는 비정상 종료된 컨테이너입니다. 먼저 확인이 필요합니다." placement="bottom-start" /></span>
		<strong>{problem}</strong>
	</button>
	<button
		type="button"
		class="kpi stopped"
		class:active={view.stateFilter === 'stopped'}
		onclick={() => toggleFilter('stopped')}
		title="중지 컨테이너만 보기"
	>
		<span>중지 <InfoTooltip text="정상적으로 중지된 컨테이너입니다. 문제와 구분됩니다." placement="bottom-start" /></span>
		<strong>{stopped}</strong>
	</button>

	<div class="kpi passive">
		<span>트래픽 <InfoTooltip text="모든 컨테이너 네트워크의 현재 송수신 속도 합계입니다." placement="bottom-end" /></span>
		<strong>{formatRate(networkRate)}</strong>
	</div>
	<div class="kpi passive">
		<span>이미지 <InfoTooltip text="서버에 저장된 Docker 이미지 개수입니다." placement="bottom-end" /></span>
		<strong>{imageCount}</strong>
	</div>
	<div class="kpi passive">
		<span>Docker <InfoTooltip text="Docker 엔진 버전입니다." placement="bottom-end" /></span>
		<strong class="version">{dockerVersion}</strong>
	</div>
</div>

<style>
	.kpi-row {
		display: grid;
		grid-template-columns: repeat(8, minmax(0, 1fr));
		gap: 5px;
		min-width: 0;
	}

	.kpi {
		display: grid;
		align-content: center;
		gap: 2px;
		padding: 6px 10px;
		border: 1px solid var(--border);
		border-radius: 9px;
		background: rgba(15, 23, 42, 0.55);
		color: var(--text-primary);
		text-align: left;
		min-width: 0;
		cursor: pointer;
		transition: border-color 0.12s ease, background-color 0.12s ease, transform 0.12s ease;
	}

	.kpi:hover:not(.passive) {
		transform: translateY(-1px);
	}

	.kpi.passive {
		cursor: default;
	}

	.kpi:hover:not(.passive) {
		border-color: rgba(48, 213, 200, 0.38);
	}

	.kpi.active {
		border-color: rgba(48, 213, 200, 0.7);
		background: rgba(48, 213, 200, 0.12);
		box-shadow: 0 0 0 1px rgba(48, 213, 200, 0.4) inset;
	}

	.kpi span {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 800;
		display: inline-flex;
		align-items: center;
		letter-spacing: 0.02em;
	}

	.kpi strong {
		font-size: 18px;
		line-height: 1.05;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 900;
	}

	.kpi.all strong { color: #e2e8f0; }
	.kpi.running strong { color: #34d399; }
	.kpi.paused strong { color: #fbbf24; }
	.kpi.problem strong { color: #f87171; }
	.kpi.stopped strong { color: #94a3b8; }

	.version {
		font-size: 16px !important;
	}

	@media (max-width: 1100px) {
		.kpi-row {
			grid-template-columns: repeat(4, minmax(0, 1fr));
		}
	}

	@media (max-width: 640px) {
		.kpi-row {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
