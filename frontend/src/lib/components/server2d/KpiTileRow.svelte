<script lang="ts">
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
		title="전체 컨테이너 수. 중지·일시정지·문제 포함. 클릭하면 모든 상태 표시."
	>
		<span>전체</span>
		<strong>{total}</strong>
	</button>
	<button
		type="button"
		class="kpi running"
		class:active={view.stateFilter === 'running'}
		onclick={() => toggleFilter('running')}
		title="정상 동작 중. 클릭 = 실행 상태만 필터."
	>
		<span>실행</span>
		<strong>{running}</strong>
	</button>
	<button
		type="button"
		class="kpi paused"
		class:active={view.stateFilter === 'paused'}
		onclick={() => toggleFilter('paused')}
		title="docker pause로 멈춤. 프로세스는 살아있음. 클릭 = 일시정지만 필터."
	>
		<span>일시정지</span>
		<strong>{paused}</strong>
	</button>
	<button
		type="button"
		class="kpi problem"
		class:active={view.stateFilter === 'problem'}
		onclick={() => toggleFilter('problem')}
		title="재시작 루프 또는 비정상 종료. 먼저 확인 필요. 클릭 = 문제만 필터."
	>
		<span>문제</span>
		<strong>{problem}</strong>
	</button>
	<button
		type="button"
		class="kpi stopped"
		class:active={view.stateFilter === 'stopped'}
		onclick={() => toggleFilter('stopped')}
		title="정상적으로 중지. 문제 컨테이너와 구분. 클릭 = 중지만 필터."
	>
		<span>중지</span>
		<strong>{stopped}</strong>
	</button>

	<div class="kpi passive" title="모든 컨테이너 네트워크의 현재 송수신 속도 합계">
		<span>트래픽</span>
		<strong>{formatRate(networkRate)}</strong>
	</div>
	<div class="kpi passive" title="서버에 저장된 Docker 이미지 개수">
		<span>이미지</span>
		<strong>{imageCount}</strong>
	</div>
	<div class="kpi passive" title="Docker 엔진 버전">
		<span>Docker</span>
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
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding: 7px 11px;
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
		letter-spacing: 0.02em;
		flex: 0 0 auto;
		white-space: nowrap;
	}

	.kpi strong {
		font-size: 20px;
		line-height: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 900;
		text-align: right;
		min-width: 0;
	}

	.kpi.all strong { color: #e2e8f0; }
	.kpi.running strong { color: #34d399; }
	.kpi.paused strong { color: #fbbf24; }
	.kpi.problem strong { color: #f87171; }
	.kpi.stopped strong { color: #94a3b8; }

	.version {
		font-size: 15px !important;
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
