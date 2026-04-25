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
		title={`전체 컨테이너 수입니다.\n모든 상태(실행·일시정지·문제·중지)를 합친 숫자입니다.\n클릭하면 필터를 해제하고 전체를 표시합니다.`}
	>
		<svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<path d="M3 7l9-4 9 4-9 4-9-4z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
			<path d="M3 12l9 4 9-4M3 17l9 4 9-4" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
		</svg>
		<span class="text">
			<small>전체</small>
			<strong>{total}</strong>
		</span>
	</button>
	<button
		type="button"
		class="kpi running"
		class:active={view.stateFilter === 'running'}
		onclick={() => toggleFilter('running')}
		title={`정상적으로 동작 중인 컨테이너입니다.\n클릭하면 실행 상태만 필터해서 보여줍니다.\n다시 클릭하면 해제됩니다.`}
	>
		<svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<polygon points="6,4 20,12 6,20" fill="currentColor"/>
		</svg>
		<span class="text">
			<small>실행</small>
			<strong>{running}</strong>
		</span>
	</button>
	<button
		type="button"
		class="kpi paused"
		class:active={view.stateFilter === 'paused'}
		onclick={() => toggleFilter('paused')}
		title={`docker pause 상태입니다.\n프로세스는 살아 있지만 동작하지 않습니다.\n클릭하면 일시정지 컨테이너만 필터합니다.`}
	>
		<svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<rect x="6" y="4" width="4" height="16" fill="currentColor" rx="1"/>
			<rect x="14" y="4" width="4" height="16" fill="currentColor" rx="1"/>
		</svg>
		<span class="text">
			<small>일시정지</small>
			<strong>{paused}</strong>
		</span>
	</button>
	<button
		type="button"
		class="kpi problem"
		class:active={view.stateFilter === 'problem'}
		onclick={() => toggleFilter('problem')}
		title={`재시작 루프 또는 비정상 종료된 컨테이너입니다.\n가장 먼저 확인해야 할 항목입니다.\n클릭하면 문제 컨테이너만 필터합니다.`}
	>
		<svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<path d="M12 3l10 18H2L12 3z" fill="currentColor"/>
			<rect x="11" y="10" width="2" height="6" fill="#0b1320" rx="1"/>
			<rect x="11" y="17" width="2" height="2" fill="#0b1320" rx="1"/>
		</svg>
		<span class="text">
			<small>문제</small>
			<strong>{problem}</strong>
		</span>
	</button>
	<button
		type="button"
		class="kpi stopped"
		class:active={view.stateFilter === 'stopped'}
		onclick={() => toggleFilter('stopped')}
		title={`정상적으로 종료된 컨테이너입니다.\n문제 컨테이너와 구분됩니다.\n클릭하면 중지 컨테이너만 필터합니다.`}
	>
		<svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<rect x="5" y="5" width="14" height="14" fill="currentColor" rx="2"/>
		</svg>
		<span class="text">
			<small>중지</small>
			<strong>{stopped}</strong>
		</span>
	</button>

	<div class="kpi passive traffic" title={`모든 컨테이너 네트워크의 현재 송수신 속도 합계입니다.\n단위: B/s → KB/s → MB/s → GB/s 자동 환산.`}>
		<svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<path d="M4 14l4-4 4 4 8-8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
			<path d="M16 6h4v4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
		</svg>
		<span class="text">
			<small>트래픽</small>
			<strong>{formatRate(networkRate)}</strong>
		</span>
	</div>
	<div class="kpi passive images" title={`서버에 저장된 Docker 이미지 개수입니다.\n실행 중이 아닌 이미지도 포함합니다.`}>
		<svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<rect x="4" y="4" width="16" height="16" stroke="currentColor" stroke-width="1.8" rx="2"/>
			<path d="M4 16l5-5 4 4 3-3 4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
			<circle cx="9" cy="9" r="1.5" fill="currentColor"/>
		</svg>
		<span class="text">
			<small>이미지</small>
			<strong>{imageCount}</strong>
		</span>
	</div>
	<div class="kpi passive docker" title={`Docker 엔진 버전입니다.`}>
		<svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<rect x="3" y="10" width="3" height="3" fill="currentColor"/>
			<rect x="7" y="10" width="3" height="3" fill="currentColor"/>
			<rect x="11" y="10" width="3" height="3" fill="currentColor"/>
			<rect x="7" y="6" width="3" height="3" fill="currentColor"/>
			<rect x="11" y="6" width="3" height="3" fill="currentColor"/>
			<rect x="11" y="2" width="3" height="3" fill="currentColor"/>
			<path d="M22 11c-1 4-5 7-12 7H2c0-2 1-4 3-5 1 3 6 3 8 1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" fill="none"/>
		</svg>
		<span class="text">
			<small>Docker</small>
			<strong class="version">{dockerVersion}</strong>
		</span>
	</div>
</div>

<style>
	.kpi-row {
		display: grid;
		grid-template-columns: repeat(8, minmax(0, 1fr));
		gap: 6px;
		min-width: 0;
	}

	.kpi {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 7px 12px 8px 10px;
		border: 1px solid var(--border);
		border-radius: 10px;
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
		border-color: rgba(48, 213, 200, 0.45);
	}

	.kpi.active {
		border-color: rgba(48, 213, 200, 0.7);
		background: rgba(48, 213, 200, 0.12);
		box-shadow: 0 0 0 1px rgba(48, 213, 200, 0.4) inset;
	}

	.icon {
		width: 22px;
		height: 22px;
		flex: 0 0 auto;
		color: var(--text-muted);
	}

	.all .icon { color: #94a3b8; }
	.running .icon { color: #34d399; }
	.paused .icon { color: #fbbf24; }
	.problem .icon { color: #f87171; }
	.stopped .icon { color: #64748b; }
	.traffic .icon { color: #22d3ee; }
	.images .icon { color: #a78bfa; }
	.docker .icon { color: #60a5fa; }

	.kpi.active .icon { color: #30d5c8; }

	.text {
		display: grid;
		gap: 1px;
		min-width: 0;
		flex: 1;
	}

	.text small {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		line-height: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.text strong {
		font-size: 19px;
		line-height: 1.05;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 900;
	}

	.all strong { color: #e2e8f0; }
	.running strong { color: #34d399; }
	.paused strong { color: #fbbf24; }
	.problem strong { color: #f87171; }
	.stopped strong { color: #94a3b8; }
	.traffic strong { color: #22d3ee; }
	.images strong { color: #c4b5fd; }
	.docker strong { color: #93c5fd; }

	.version {
		font-size: 14px !important;
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
