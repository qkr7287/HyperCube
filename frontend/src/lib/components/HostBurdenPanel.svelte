<!--
  HostBurdenPanel — 호스트 자원 부담 + 이 컨테이너의 기여도 (mock).

  지금은 frontend/src/lib/mocks/host-burden.ts 의 generateSample() 로 더미 값을 5초마다
  생성. 실 데이터 path 는 mock 모듈 상단 주석 참고. 차트/레이아웃은 BurdenSnapshot
  shape 에만 의존하므로 fetcher 만 갈아끼우면 그대로 사용 가능.

  추정 모델: Level 1 (단순 비율). MOCK pill hover 시 disclaimer 노출.
-->
<script lang="ts">
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { onDestroy, onMount } from 'svelte';
	import EChartBase from './charts/EChartBase.svelte';
	import InfoTooltip from './InfoTooltip.svelte';
	import type { EChartsOption } from './charts/echart-registry';
	import { generateSample, type BurdenMetric, type BurdenSnapshot } from '$lib/mocks/host-burden';

	const headerHelp = `이 컨테이너가 호스트에 주는 추정 영향.

· GPU 온도·전력 게이지: 호스트 현재값 (nvidia-smi 실측)
· CPU 전력 게이지: RAPL 실측 또는 Fan 모델 추정 (±15%)
· "컨테이너 기여": 이 컨테이너의 CPU·GPU 사용량 비율로 분배한 추정치

per-container 전력은 직접 측정 불가능 — 절대값 신뢰 X, 추세·비교 용도로 사용.`;

	let { containerId }: { containerId: string } = $props();

	// 초기 mock — backend 응답 받기 전 짧은 시점에 빈 chart 가 깜빡이지 않게 한 frame 채움.
	let snapshot = $state<BurdenSnapshot>(generateSample());
	let usingMock = $state(true);
	let timer: ReturnType<typeof setInterval> | null = null;

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function loadFromBackend(): Promise<void> {
		if (!containerId) return;
		const t = token();
		if (!t) return;
		try {
			const r = await fetch(`${base}/api/my-containers/${containerId}/burden/`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (!r.ok) throw new Error(`HTTP ${r.status}`);
			const j = await r.json();
			// backend 가 DRF middleware 로 { success, data } 로 wrap 함. data 안의 BurdenSnapshot 추출.
			const payload = (j?.data ?? j) as BurdenSnapshot;
			if (payload && typeof payload === 'object' && 'totalPower' in payload) {
				snapshot = payload;
				usingMock = false;
			}
		} catch {
			// backend 미가용 / endpoint 실패 → mock fallback 으로 시각화는 계속 유지.
			snapshot = generateSample();
			usingMock = true;
		}
	}

	onMount(() => {
		loadFromBackend();
		timer = setInterval(loadFromBackend, 5000);
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});

	function gaugeOption(metric: BurdenMetric, unit: string): EChartsOption {
		const { hostValue, hostMax, zones } = metric;
		const z = zones ?? {
			ok: hostMax * 0.7,
			warn: hostMax * 0.85,
			danger: hostMax * 0.95,
		};
		return {
			series: [
				{
					type: 'gauge',
					startAngle: 210,
					endAngle: -30,
					min: 0,
					max: hostMax,
					radius: '92%',
					center: ['50%', '68%'],
					splitNumber: 5,
					axisLine: {
						lineStyle: {
							width: 7,
							color: [
								[z.ok / hostMax, 'rgba(16, 185, 129, 0.55)'],
								[z.warn / hostMax, 'rgba(234, 179, 8, 0.6)'],
								[z.danger / hostMax, 'rgba(249, 115, 22, 0.65)'],
								[1, 'rgba(239, 68, 68, 0.75)'],
							],
						},
					},
					pointer: {
						width: 3,
						length: '60%',
						itemStyle: {
							color: '#e2e8f0',
							shadowColor: 'rgba(0,0,0,0.4)',
							shadowBlur: 3,
						},
					},
					anchor: {
						show: true,
						size: 7,
						itemStyle: { color: '#94a3b8', borderColor: '#0f172a', borderWidth: 2 },
					},
					axisTick: {
						length: 3,
						distance: -7,
						lineStyle: { color: 'rgba(226, 232, 240, 0.4)', width: 1 },
					},
					splitLine: {
						length: 6,
						distance: -7,
						lineStyle: { color: 'rgba(226, 232, 240, 0.7)', width: 1.5 },
					},
					axisLabel: {
						show: true,
						distance: -22,
						color: 'rgba(148, 163, 184, 0.75)',
						fontSize: 9,
						fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace',
						formatter: (v: number) => `${Math.round(v)}`,
					},
					title: { show: false },
					detail: {
						valueAnimation: true,
						formatter: (v: number) => `${v.toFixed(1)} ${unit}`,
						color: '#f1f5f9',
						fontSize: 16,
						fontWeight: 800,
						fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace',
						offsetCenter: [0, '46%'],
					},
					data: [{ value: hostValue }],
				},
			],
		};
	}

	function sparkPolyline(values: number[]): string {
		if (values.length === 0) return '';
		const max = Math.max(...values);
		const min = Math.min(...values);
		const range = Math.max(0.0001, max - min);
		const step = 100 / Math.max(1, values.length - 1);
		return values
			.map((v, i) => {
				const x = i * step;
				const y = 36 - ((v - min) / range) * 32;
				return `${x.toFixed(2)},${y.toFixed(2)}`;
			})
			.join(' ');
	}

	function sparkArea(values: number[]): string {
		const line = sparkPolyline(values);
		if (!line) return '';
		// area fill = line 끝점에서 baseline 으로 닫음
		return `0,40 ${line} 100,40`;
	}

	function sharePct(metric: BurdenMetric): number {
		return Math.round(metric.containerShare * 100);
	}

	function shareTone(pct: number): string {
		if (pct >= 60) return 'danger';
		if (pct >= 35) return 'warn';
		return 'ok';
	}

	type Card = {
		key: string;
		label: string;
		unit: string;
		metric: BurdenMetric;
	};

	let cards = $derived<Card[]>([
		{ key: 'gpuTemp', label: 'GPU 온도', unit: '°C', metric: snapshot.gpuTemp },
		{ key: 'gpuPower', label: 'GPU 전력', unit: 'W', metric: snapshot.gpuPower },
		{ key: 'cpuPower', label: 'CPU 전력', unit: 'W', metric: snapshot.cpuPower },
	]);

	type ViewKey = 'detail' | 'total';
	let view = $state<ViewKey>('detail');

	let total = $derived(snapshot.totalPower);
	let totalContainerW = $derived(total.breakdown.thisContainerW);
	let totalContainerPct = $derived(Math.round(total.thisContainerPct * 100));
	// breakdown bar 비율 계산: hostValue 기준으로 4 segment (이 컨테이너 / 다른 / idle / headroom)
	let breakdownPct = $derived.by(() => {
		const max = total.hostMax;
		const b = total.breakdown;
		const pct = (v: number) => (max > 0 ? (v / max) * 100 : 0);
		return {
			thisC: pct(b.thisContainerW),
			otherC: pct(b.otherContainersW),
			idle: pct(b.idleW),
			head: pct(b.headroomW),
		};
	});
	let temp = $derived(snapshot.maxTemp);
	let tempDeltaC = $derived(temp.containerDeltaC);
	let tempContainerPct = $derived(Math.round(temp.containerShare * 100));
</script>

<section class="panel">
	<div class="panel-header slim">
		<h2>
			호스트 자원 부담
			<InfoTooltip text={headerHelp} placement="bottom-start" />
		</h2>
		<div class="head-right">
			<div class="view-tabs" role="tablist" aria-label="부담 보기">
				<button
					type="button"
					role="tab"
					aria-selected={view === 'detail'}
					class:active={view === 'detail'}
					onclick={() => (view = 'detail')}
				>상세</button>
				<button
					type="button"
					role="tab"
					aria-selected={view === 'total'}
					class:active={view === 'total'}
					onclick={() => (view = 'total')}
				>총합</button>
			</div>
			{#if usingMock}
				<span class="mock-pill" title="Backend burden endpoint 응답 실패 — mock 값으로 표시 중.">MOCK</span>
			{/if}
		</div>
	</div>

	{#if view === 'detail'}
		<div class="gauge-grid">
			{#each cards as card (card.key)}
				{@const pct = sharePct(card.metric)}
				{@const tone = shareTone(pct)}
				<article class="gauge-card">
					<header class="gauge-head">
						<span class="gauge-label">{card.label}</span>
						<span class="gauge-max">/ {card.metric.hostMax}{card.unit}</span>
					</header>
					<div class="gauge-host" aria-label={card.label}>
						<EChartBase option={gaugeOption(card.metric, card.unit)} ariaLabel={card.label} />
					</div>
					<div class="share" data-tone={tone}>
						<div class="share-meta">
							<span class="share-label">컨테이너 기여</span>
							<span class="share-pct">{pct}%</span>
						</div>
						<span class="share-bar" aria-hidden="true">
							<i style:width="{pct}%"></i>
						</span>
					</div>
					<div class="trend">
						<svg class="spark" viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
							<polygon class="spark-area" points={sparkArea(card.metric.sparkline)} />
							<polyline class="spark-line" points={sparkPolyline(card.metric.sparkline)} />
						</svg>
						<span class="trend-label">최근 추세</span>
					</div>
				</article>
			{/each}
		</div>
	{:else}
		{@const powerTone = shareTone(totalContainerPct)}
		{@const tempTone = shareTone(tempContainerPct)}
		<div class="total-view">
			<div class="total-gauges">
				<article class="gauge-card total-card">
					<header class="gauge-head">
						<span class="gauge-label">서버 총 전력</span>
						<span class="gauge-max">/ {total.hostMax}W</span>
					</header>
					<div class="gauge-host" aria-label="서버 총 전력">
						<EChartBase option={gaugeOption(total, 'W')} ariaLabel="서버 총 전력" />
					</div>
				</article>
				<article class="gauge-card total-card">
					<header class="gauge-head">
						<span class="gauge-label">최고 온도 · {temp.hotspot}</span>
						<span class="gauge-max">/ {temp.hostMax}°C</span>
					</header>
					<div class="gauge-host" aria-label="호스트 최고 온도">
						<EChartBase option={gaugeOption(temp, '°C')} ariaLabel="호스트 최고 온도" />
					</div>
				</article>
			</div>

			<div class="impact-stack">
				<article class="impact-card" data-tone={powerTone}>
					<div class="impact-head">
						<span class="impact-label">컨테이너 전력 기여</span>
						<span class="impact-meta">호스트 {total.hostValue.toFixed(0)}W 중</span>
					</div>
					<div class="impact-value">
						<span class="impact-watts">{totalContainerW.toFixed(0)}<em>W</em></span>
						<span class="impact-pct">{totalContainerPct}%</span>
					</div>

					<div class="breakdown" aria-label="전력 분담 breakdown">
						<div class="breakdown-bar" aria-hidden="true">
							<i class="seg seg-this" style:width="{breakdownPct.thisC}%" title="이 컨테이너"></i>
							<i class="seg seg-other" style:width="{breakdownPct.otherC}%" title="다른 컨테이너"></i>
							<i class="seg seg-idle" style:width="{breakdownPct.idle}%" title="호스트 idle"></i>
							<i class="seg seg-head" style:width="{breakdownPct.head}%" title="여유"></i>
						</div>
						<div class="breakdown-legend">
							<span><i class="dot dot-this"></i>이 컨테이너 {total.breakdown.thisContainerW.toFixed(0)}W</span>
							<span><i class="dot dot-other"></i>다른 컨테이너 {total.breakdown.otherContainersW.toFixed(0)}W</span>
							<span><i class="dot dot-idle"></i>idle {total.breakdown.idleW}W</span>
							<span><i class="dot dot-head"></i>여유 {total.breakdown.headroomW.toFixed(0)}W</span>
						</div>
					</div>
				</article>

				<article class="impact-card" data-tone={tempTone}>
					<div class="impact-head">
						<span class="impact-label">컨테이너 발열 기여</span>
						<span class="impact-meta">호스트 {temp.hostValue.toFixed(1)}°C · idle {temp.idleBaselineC}°C</span>
					</div>
					<div class="impact-value">
						<span class="impact-watts">+{tempDeltaC.toFixed(1)}<em>°C</em></span>
						<span class="impact-pct">{tempContainerPct}%</span>
					</div>
					<div class="trend total-trend">
						<svg class="spark" viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
							<polygon class="spark-area" points={sparkArea(temp.sparkline)} />
							<polyline class="spark-line" points={sparkPolyline(temp.sparkline)} />
						</svg>
						<span class="trend-label">호스트 온도 추세</span>
					</div>
				</article>
			</div>
		</div>
	{/if}
</section>

<style>
	.panel {
		background:
			linear-gradient(180deg, rgba(21, 27, 38, 0.98), rgba(15, 20, 29, 0.98)),
			rgba(18, 23, 32, 0.96);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: var(--radius-panel);
		padding: clamp(5px, 0.45vw, 8px);
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		height: 100%;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
		position: relative;
		box-shadow:
			0 8px 24px rgba(0, 0, 0, 0.16),
			inset 0 1px 0 rgba(255, 255, 255, 0.025);
	}
	.panel::before {
		content: '';
		position: absolute;
		inset: 0 0 auto;
		height: 2px;
		background: linear-gradient(90deg, rgba(244, 114, 182, 0.55), rgba(96, 165, 250, 0.12));
		opacity: 0.75;
	}

	.panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		margin-bottom: 5px;
		padding-bottom: 5px;
		border-bottom: 1px solid rgba(100, 116, 139, 0.12);
		flex: 0 0 auto;
	}

	h2 {
		font-size: 14px;
		margin: 0;
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.head-right {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.view-tabs {
		display: inline-flex;
		padding: 2px;
		background: rgba(2, 6, 12, 0.5);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: 7px;
	}
	.view-tabs button {
		padding: 3px 9px;
		border: 0;
		background: transparent;
		color: var(--text-muted);
		font: inherit;
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.04em;
		border-radius: 5px;
		cursor: pointer;
	}
	.view-tabs button:hover { color: var(--text-secondary); }
	.view-tabs button.active {
		background: rgba(48, 213, 200, 0.18);
		color: var(--accent);
		box-shadow: inset 0 0 0 1px rgba(48, 213, 200, 0.3);
	}

	.mock-pill {
		font-size: 9.5px;
		font-weight: 800;
		letter-spacing: 0.06em;
		padding: 2px 6px;
		border-radius: 5px;
		cursor: help;
		background: rgba(244, 114, 182, 0.18);
		color: #f9a8d4;
		border: 1px solid rgba(244, 114, 182, 0.35);
	}

	.gauge-grid {
		flex: 1 1 auto;
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 6px;
		min-height: 0;
	}

	.gauge-card {
		min-width: 0;
		min-height: 0;
		display: grid;
		grid-template-rows: minmax(0, 1.2fr) auto auto;
		gap: 4px;
		padding: 6px 8px 8px;
		border-radius: 9px;
		background:
			linear-gradient(180deg, rgba(13, 17, 23, 0.76), rgba(8, 12, 19, 0.7)),
			rgba(13, 17, 23, 0.8);
		border: 1px solid rgba(100, 116, 139, 0.18);
		overflow: hidden;
		position: relative;
	}

	/* 라벨/max 를 absolute 좌상·우상 코너로 빼서 게이지가 카드 위 공간 다 차지하도록.
	   게이지 호 양 끝 위쪽이 자연스럽게 비어 있어 라벨이 시각적으로 안 겹침. */
	.gauge-head {
		position: absolute;
		top: 6px;
		left: 10px;
		right: 10px;
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 6px;
		pointer-events: none;
		z-index: 1;
	}
	.gauge-label {
		font-size: 10.5px;
		font-weight: 850;
		color: var(--text-secondary);
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	.gauge-max {
		font-size: 9.5px;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.gauge-host {
		min-height: 0;
		min-width: 0;
		width: 100%;
		overflow: hidden;
	}

	.share {
		display: flex;
		flex-direction: column;
		gap: 3px;
		padding: 4px 6px 5px;
		border-radius: 6px;
		background: rgba(2, 6, 12, 0.4);
		border: 1px solid rgba(100, 116, 139, 0.16);
	}
	.share-meta {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 6px;
	}
	.share-label {
		font-size: 9.5px;
		font-weight: 800;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--text-muted);
	}
	.share-pct {
		font-size: 16px;
		font-weight: 900;
		font-variant-numeric: tabular-nums;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		color: #5eead4;
		line-height: 1;
	}
	.share-bar {
		position: relative;
		height: 5px;
		background: rgba(0, 0, 0, 0.5);
		border-radius: 999px;
		overflow: hidden;
	}
	.share-bar i {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: rgba(48, 213, 200, 0.9);
		transition: width 0.4s var(--ease-fast);
	}
	.share[data-tone='warn'] .share-pct { color: #fde047; }
	.share[data-tone='warn'] .share-bar i { background: #facc15; }
	.share[data-tone='danger'] .share-pct { color: #fca5a5; }
	.share[data-tone='danger'] .share-bar i { background: #f87171; }

	.trend {
		display: grid;
		grid-template-columns: 1fr auto;
		align-items: center;
		gap: 6px;
		padding: 3px 6px 4px;
		border-radius: 6px;
		background: rgba(2, 6, 12, 0.4);
		border: 1px solid rgba(100, 116, 139, 0.14);
	}
	.spark {
		width: 100%;
		height: 22px;
		display: block;
	}
	.spark-line {
		fill: none;
		stroke: rgba(48, 213, 200, 0.85);
		stroke-width: 1.4;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.spark-area {
		fill: rgba(48, 213, 200, 0.1);
		stroke: none;
	}
	.trend-label {
		font-size: 9px;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--text-muted);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	/* 총합 탭: 좌측에 게이지 2개 stack (전력+온도) + 우측 impact stack (전력기여+발열기여) */
	.total-view {
		flex: 1 1 auto;
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr);
		gap: 8px;
		min-height: 0;
	}
	.total-gauges {
		display: grid;
		grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
		gap: 6px;
		min-height: 0;
	}
	.impact-stack {
		display: grid;
		grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
		gap: 6px;
		min-height: 0;
	}
	.total-card {
		grid-template-rows: minmax(0, 1fr);
	}

	.impact-card {
		min-width: 0;
		min-height: 0;
		display: grid;
		grid-template-rows: auto auto 1fr;
		gap: 4px;
		padding: 6px 9px 8px;
		border-radius: 9px;
		background:
			linear-gradient(180deg, rgba(13, 17, 23, 0.78), rgba(8, 12, 19, 0.72)),
			rgba(13, 17, 23, 0.82);
		border: 1px solid rgba(48, 213, 200, 0.28);
		overflow: hidden;
		position: relative;
	}
	.impact-card::before {
		content: '';
		position: absolute;
		inset: 0 0 auto;
		height: 2px;
		background: linear-gradient(90deg, rgba(48, 213, 200, 0.6), rgba(96, 165, 250, 0.18));
	}
	.impact-card[data-tone='warn'] { border-color: rgba(250, 204, 21, 0.4); }
	.impact-card[data-tone='warn']::before {
		background: linear-gradient(90deg, rgba(250, 204, 21, 0.7), rgba(244, 114, 182, 0.18));
	}
	.impact-card[data-tone='danger'] { border-color: rgba(248, 113, 113, 0.45); }
	.impact-card[data-tone='danger']::before {
		background: linear-gradient(90deg, rgba(248, 113, 113, 0.8), rgba(244, 114, 182, 0.22));
	}

	.impact-head { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; }
	.impact-label {
		font-size: 11px;
		font-weight: 850;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-secondary);
	}

	.impact-value {
		display: flex;
		align-items: baseline;
		gap: 10px;
		min-width: 0;
	}
	.impact-watts {
		font-size: 34px;
		font-weight: 900;
		font-variant-numeric: tabular-nums;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		color: #5eead4;
		line-height: 1;
	}
	.impact-watts em {
		font-size: 14px;
		font-style: normal;
		font-weight: 700;
		color: var(--text-muted);
		margin-left: 2px;
	}
	.impact-pct {
		font-size: 16px;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		color: var(--text-primary);
		padding: 2px 7px;
		border-radius: 5px;
		background: rgba(48, 213, 200, 0.16);
		border: 1px solid rgba(48, 213, 200, 0.3);
	}
	.impact-card[data-tone='warn'] .impact-watts { color: #fde047; }
	.impact-card[data-tone='warn'] .impact-pct {
		background: rgba(250, 204, 21, 0.16);
		border-color: rgba(250, 204, 21, 0.4);
	}
	.impact-card[data-tone='danger'] .impact-watts { color: #fca5a5; }
	.impact-card[data-tone='danger'] .impact-pct {
		background: rgba(248, 113, 113, 0.16);
		border-color: rgba(248, 113, 113, 0.4);
	}

	.impact-meta {
		font-size: 10.5px;
		color: var(--text-muted);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.breakdown { display: flex; flex-direction: column; gap: 5px; }
	.breakdown-bar {
		display: flex;
		height: 12px;
		border-radius: 5px;
		overflow: hidden;
		background: rgba(0, 0, 0, 0.55);
		border: 1px solid rgba(100, 116, 139, 0.18);
	}
	.seg { display: block; height: 100%; transition: width 0.4s var(--ease-fast); }
	.seg-this  { background: rgba(48, 213, 200, 0.9); }
	.seg-other { background: rgba(96, 165, 250, 0.75); }
	.seg-idle  { background: rgba(148, 163, 184, 0.55); }
	.seg-head  { background: rgba(100, 116, 139, 0.22); }

	.breakdown-legend {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1px 8px;
		font-size: 9.5px;
		line-height: 1.25;
		color: var(--text-muted);
	}
	.breakdown-legend span {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		min-width: 0;
	}
	.dot { width: 7px; height: 7px; border-radius: 2px; display: inline-block; flex: 0 0 auto; }
	.dot-this  { background: rgba(48, 213, 200, 0.9); }
	.dot-other { background: rgba(96, 165, 250, 0.75); }
	.dot-idle  { background: rgba(148, 163, 184, 0.55); }
	.dot-head  { background: rgba(100, 116, 139, 0.4); }

	.total-trend { margin-top: auto; }
</style>
