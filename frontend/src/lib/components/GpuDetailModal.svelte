<!--
  GPU detail modal.

  - Info cards per detected GPU (vendor / model / memory capacity / live usage).
  - Three time-series charts — utilization, VRAM in use, temperature — driven
    by MetricTrendChart's `metricExtractor` hook so the chart pulls the right
    field out of the `gpu` array carried in each history row.
  - If the host reports multiple GPUs, a tab row lets the user switch which
    GPU the charts are focused on. Usage for the *primary* GPU (index 0) is
    what the sidebar sparkline shows.
  - Every field ships with an InfoTooltip explaining the number — GPU state
    reveals a lot about what a host is actually running (training jobs, idle
    inference, thermal trouble), so the explanations are intentionally long
    enough for a non-ops reader.
-->
<script lang="ts">
	import MetricTrendChart from './MetricTrendChart.svelte';
	import InfoTooltip from './InfoTooltip.svelte';
	import { formatBytes, type GpuMetric } from '$lib/utils/data-adapter';

	let {
		open = false,
		systemInfo = null,
		agentId = '',
		accessToken = '',
		onClose = () => {},
	}: {
		open: boolean;
		systemInfo?: any;
		agentId?: string;
		accessToken?: string;
		onClose: () => void;
	} = $props();

	let gpuList = $derived<GpuMetric[]>(systemInfo?.gpu ?? []);
	let selectedIndex = $state(0);

	// Clamp selection when the GPU list shrinks (e.g. switching servers).
	$effect(() => {
		if (gpuList.length === 0) return;
		if (selectedIndex >= gpuList.length) selectedIndex = 0;
	});

	let activeGpu = $derived(gpuList.find((g) => g.index === selectedIndex) ?? gpuList[0] ?? null);

	// Compact live readout shown in each section header — mirrors what the
	// charts will approach as new ticks come in.
	let liveUsage = $derived(activeGpu ? Number(activeGpu.usage ?? 0) : 0);
	let liveMemUsed = $derived(activeGpu ? Number(activeGpu.memoryUsed ?? 0) : 0);
	let liveTemp = $derived(activeGpu?.temperature ?? null);

	function memPercent(g: GpuMetric): number {
		if (!g || !g.memoryTotal) return 0;
		return Math.min(100, Math.round((g.memoryUsed / g.memoryTotal) * 100));
	}

	function formatTemp(v: number | null | undefined): string {
		if (v == null || Number.isNaN(v)) return '—';
		return `${Math.round(v)}°C`;
	}

	function tempClass(v: number | null | undefined): string {
		if (v == null) return '';
		if (v >= 85) return 'hot';
		if (v >= 75) return 'warm';
		return '';
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	$effect(() => {
		if (open) document.addEventListener('keydown', handleKeydown);
		else document.removeEventListener('keydown', handleKeydown);
	});

	// Chart extractors: read the chosen GPU out of the history row's `gpu`
	// array. Rows taken before the GPU came online, or rows from the other
	// agent in the same pool, filter out via NaN.
	function pickGpuField(row: any, field: 'usage' | 'memoryUsed' | 'temperature'): number | null {
		const arr = Array.isArray(row?.gpu) ? row.gpu : [];
		const g = arr.find((x: any) => x && x.index === selectedIndex) ?? arr[0];
		if (!g) return null;
		const v = g[field];
		return typeof v === 'number' ? v : null;
	}

	const extractUsage = (r: any) => pickGpuField(r, 'usage');
	const extractMem = (r: any) => pickGpuField(r, 'memoryUsed');
	const extractTemp = (r: any) => pickGpuField(r, 'temperature');
</script>

{#if open}
<div class="overlay" onclick={onClose} role="dialog">
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<span class="modal-title">GPU 상세 정보</span>
			<button class="close-btn" onclick={onClose} aria-label="닫기">
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			{#if gpuList.length === 0}
				<div class="notice-card muted">
					이 서버에는 감지된 GPU가 없어요. <code>nvidia-smi</code>가 설치된 호스트에만
					실시간 수치가 뜹니다.
				</div>
			{:else}
				<!-- ── 현재 상태 요약 ── -->
				<div class="section-label">
					현재 상태
					<InfoTooltip
						placement="bottom-start"
						text="Agent가 마지막 틱에 NVIDIA 드라이버(nvidia-smi)로부터 읽어온 값이에요. memoryUsed는 전체 VRAM에서 실제로 할당된 양, usage는 최근 샘플링 구간 동안 GPU 연산 유닛이 바빴던 비율입니다."
					/>
				</div>
				<div class="stats-row">
					{#each gpuList as g (g.index)}
						<button
							type="button"
							class="gpu-stat-card"
							class:active={g.index === selectedIndex}
							onclick={() => (selectedIndex = g.index)}
							aria-pressed={g.index === selectedIndex}
						>
							<div class="gpu-stat-head">
								<span class="gpu-chip">GPU {g.index}</span>
								<span class="gpu-vendor">{g.vendor}</span>
							</div>
							<div class="gpu-model" title={g.model}>{g.model}</div>
							<div class="gpu-metric-row">
								<div class="gpu-metric">
									<span class="gpu-metric-label">
										사용률
										<InfoTooltip
											placement="bottom-start"
											text="GPU의 연산 유닛이 얼마나 바빴는지(%). 학습/추론 작업이 없으면 0에 가까워요. 90% 근처가 오래 지속되면 해당 시간대에 작업이 돌아갔다는 뜻입니다."
										/>
									</span>
									<span class="gpu-metric-value">{Math.round(g.usage ?? 0)}%</span>
								</div>
								<div class="gpu-metric">
									<span class="gpu-metric-label">
										VRAM
										<InfoTooltip
											placement="bottom-start"
											text="할당된 VRAM 양 / 전체 VRAM. 모델 크기 추정에 가장 유용한 지표에요. 사용률이 낮은데 VRAM이 꽉 차있으면 '대기 중인' 큰 모델이 로드돼 있다는 신호입니다."
										/>
									</span>
									<span class="gpu-metric-value">
										{formatBytes(g.memoryUsed)} / {formatBytes(g.memoryTotal)}
										<small>({memPercent(g)}%)</small>
									</span>
								</div>
								<div class="gpu-metric">
									<span class="gpu-metric-label">
										온도
										<InfoTooltip
											placement="bottom-start"
											text="NVIDIA 드라이버가 보고한 GPU 다이 온도(°C). 85°C 이상이 유지되면 쿨링 점검을 권장해요. 값이 없으면 해당 드라이버가 온도 센서 정보를 노출하지 않은 것입니다."
										/>
									</span>
									<span class="gpu-metric-value {tempClass(g.temperature)}">
										{formatTemp(g.temperature)}
									</span>
								</div>
							</div>
						</button>
					{/each}
				</div>

				{#if activeGpu}
					<!-- ── 정체 정보 (타래 바뀌지 않는 값) ── -->
					<div class="section-label">
						장치 정보
						<InfoTooltip
							placement="bottom-start"
							text="장치의 정적 토폴로지예요. 모델명, 제조사, 총 VRAM 용량은 부팅 동안 변하지 않아요. GPU가 교체되면 여기 값도 바뀝니다."
						/>
					</div>
					<div class="topology-grid">
						<div class="topology-cell">
							<span class="topology-label">
								인덱스
								<InfoTooltip
									placement="bottom-start"
									text="같은 호스트에 GPU가 여러 개 있을 때 nvidia-smi가 부여한 순번. CUDA_VISIBLE_DEVICES 지정 시 이 값을 씁니다."
								/>
							</span>
							<span class="topology-value mono">{activeGpu.index}</span>
						</div>
						<div class="topology-cell">
							<span class="topology-label">
								제조사
								<InfoTooltip placement="bottom-start" text="GPU 벤더. 현재 Agent는 NVIDIA 드라이버를 우선 질의하고, 실패 시 systeminformation fallback으로 감지한 벤더명을 보고해요." />
							</span>
							<span class="topology-value">{activeGpu.vendor}</span>
						</div>
						<div class="topology-cell">
							<span class="topology-label">
								모델
								<InfoTooltip placement="bottom-start" text="GPU 제품명. '3060 Ti', '3090', 'A100' 같은 원본 이름이 그대로 노출돼요." />
							</span>
							<span class="topology-value" title={activeGpu.model}>{activeGpu.model}</span>
						</div>
						<div class="topology-cell">
							<span class="topology-label">
								전체 VRAM
								<InfoTooltip placement="bottom-start" text="GPU 카드에 탑재된 전체 비디오 메모리. 이 값보다 큰 모델은 이 카드에서 돌릴 수 없어요." />
							</span>
							<span class="topology-value mono">{formatBytes(activeGpu.memoryTotal)}</span>
						</div>
					</div>

					<!-- ── 사용률 차트 ── -->
					<div class="section-label">
						GPU 사용률 추이
						<InfoTooltip
							placement="bottom-start"
							text="선택한 GPU의 연산 사용률 시계열. 평소에는 낮다가 특정 시간대만 90%로 뛴다면 학습/추론 잡이 주기적으로 돌았다는 뜻이에요. 범위 탭으로 최근 1분 ~ 7일까지 볼 수 있어요."
						/>
						<span class="section-current">현재 {Math.round(liveUsage)}%</span>
					</div>
					<MetricTrendChart
						{agentId}
						{accessToken}
						metricField="__gpu_usage__"
						metricExtractor={extractUsage}
						liveValue={liveUsage}
						label={`GPU ${selectedIndex} 사용률`}
						color="#22d3ee"
						unit="percent"
						defaultRange="10m"
					/>

					<!-- ── VRAM 차트 ── -->
					<div class="section-label">
						VRAM 사용량 추이
						<InfoTooltip
							placement="bottom-start"
							text="VRAM 할당량의 절대값(bytes) 시계열. 학습이 끝나도 VRAM을 안 비우는 프레임워크(PyTorch 기본 등)가 있어, 작업 종료 후에도 값이 완만하게 남아있는 경우가 있어요."
						/>
						<span class="section-current">현재 {formatBytes(liveMemUsed)}</span>
					</div>
					<MetricTrendChart
						{agentId}
						{accessToken}
						metricField="__gpu_mem_used__"
						metricExtractor={extractMem}
						liveValue={liveMemUsed}
						label={`GPU ${selectedIndex} VRAM 사용량`}
						color="#a78bfa"
						unit="bytes"
						defaultRange="10m"
					/>

					<!-- ── 온도 차트 ── -->
					<div class="section-label">
						온도 추이
						<InfoTooltip
							placement="bottom-start"
							text="GPU 다이 온도(°C) 시계열. 연산이 많아질수록 올라가고, 쿨러가 정상이면 70°C 전후에서 평형을 이뤄요. 85°C를 자주 찍는다면 먼지/팬 점검이 필요합니다."
						/>
						<span class="section-current {tempClass(liveTemp)}">현재 {formatTemp(liveTemp)}</span>
					</div>
					{#if liveTemp == null}
						<div class="notice-card muted">
							이 GPU 드라이버가 온도 센서 값을 노출하지 않아요 (보통 가상/컨테이너 드라이버 fallback 경로).
						</div>
					{:else}
						<MetricTrendChart
							{agentId}
							{accessToken}
							metricField="__gpu_temp__"
							metricExtractor={extractTemp}
							liveValue={liveTemp}
							label={`GPU ${selectedIndex} 온도`}
							color="#f87171"
							unit="count"
							defaultRange="10m"
						/>
					{/if}
				{/if}
			{/if}
		</div>
	</div>
</div>
{/if}

<style>
	.overlay {
		position: fixed; inset: 0; z-index: 100;
		background: rgba(0,0,0,0.6); display: flex;
		align-items: center; justify-content: center;
		backdrop-filter: blur(4px);
	}
	.modal {
		width: min(1080px, 94vw); max-height: 90vh;
		background: #0d1117; border: 1px solid #22d3ee;
		border-radius: 12px; display: flex;
		flex-direction: column; overflow: hidden;
	}
	.modal-header {
		display: flex; justify-content: space-between; align-items: center;
		padding: 24px 28px; border-bottom: 1px solid #1f2937;
	}
	.modal-title { font-size: 17px; font-weight: 700; color: #d9d9d9; }
	.close-btn { background: none; border: none; cursor: pointer; padding: 6px; display: flex; }
	.close-btn:hover svg { stroke: #cbd5e1; }
	.modal-content {
		flex: 1;
		overflow-y: auto;
		overflow-x: hidden;
		padding: 28px;
		display: flex;
		flex-direction: column;
		gap: 28px;
		scrollbar-width: thin;
		scrollbar-color: rgba(148, 163, 184, 0.35) transparent;
	}
	.modal-content::-webkit-scrollbar { width: 10px; }
	.modal-content::-webkit-scrollbar-track { background: transparent; }
	.modal-content::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.3);
		border: 2px solid transparent;
		border-radius: 8px;
		background-clip: padding-box;
	}
	.modal-content::-webkit-scrollbar-thumb:hover {
		background: rgba(34, 211, 238, 0.55);
		background-clip: padding-box;
	}
	.modal-content > * { flex-shrink: 0; }

	.section-label {
		font-size: 14px; font-weight: 700; color: #64748b;
		display: flex; align-items: baseline; gap: 10px;
	}
	.section-current {
		margin-left: auto; font-size: 13px; font-weight: 700;
		color: #22d3ee; font-variant-numeric: tabular-nums;
	}
	.section-current.warm { color: #f59e0b; }
	.section-current.hot { color: #ef4444; }

	.stats-row {
		display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px;
	}
	.gpu-stat-card {
		background: #121720; border: 1px solid rgba(148,163,184,0.1);
		border-radius: 10px; padding: 16px;
		display: flex; flex-direction: column; gap: 10px;
		cursor: pointer; font-family: inherit; text-align: left;
		transition: border-color 0.18s, background-color 0.18s, transform 0.18s;
	}
	.gpu-stat-card:hover {
		border-color: rgba(34,211,238,0.4);
		background: rgba(34,211,238,0.06);
	}
	.gpu-stat-card.active {
		border-color: #22d3ee;
		background: rgba(34,211,238,0.1);
		box-shadow: 0 0 0 1px rgba(34,211,238,0.35) inset;
	}
	.gpu-stat-head {
		display: flex; align-items: center; gap: 10px;
	}
	.gpu-chip {
		font-size: 10px; font-weight: 700; letter-spacing: 0.1em;
		padding: 3px 8px; border-radius: 9999px;
		color: #22d3ee; background: rgba(34,211,238,0.12);
		border: 1px solid rgba(34,211,238,0.35);
	}
	.gpu-vendor {
		font-size: 11px; color: #64748b; letter-spacing: 0.05em;
	}
	.gpu-model {
		font-size: 13px; font-weight: 600; color: #cbd5e1;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
	}
	.gpu-metric-row {
		display: flex; flex-direction: column; gap: 6px;
	}
	.gpu-metric {
		display: flex; align-items: center; justify-content: space-between; gap: 8px;
	}
	.gpu-metric-label {
		font-size: 11px; color: #64748b; display: inline-flex; align-items: center;
	}
	.gpu-metric-value {
		font-size: 13px; font-weight: 700; color: #cbd5e1;
		font-variant-numeric: tabular-nums;
	}
	.gpu-metric-value small {
		font-size: 11px; font-weight: 400; color: #64748b;
	}
	.gpu-metric-value.warm { color: #f59e0b; }
	.gpu-metric-value.hot { color: #ef4444; }

	.topology-grid {
		display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
	}
	.topology-cell {
		background: #121720; border-radius: 10px; padding: 12px 14px;
		display: flex; flex-direction: column; gap: 4px;
		border: 1px solid rgba(148,163,184,0.1);
	}
	.topology-label {
		font-size: 11px; color: #64748b;
		display: inline-flex; align-items: center;
	}
	.topology-value {
		font-size: 13px; font-weight: 700; color: #cbd5e1;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
	}
	.topology-value.mono {
		font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
	}

	.notice-card {
		padding: 16px 18px; border-radius: 10px;
		background: rgba(34,211,238,0.06);
		border: 1px solid rgba(34,211,238,0.25);
		color: #cbd5e1; font-size: 13px; line-height: 1.55;
	}
	.notice-card.muted {
		background: #121720; border-color: rgba(100,116,139,0.2); color: #94a3b8;
	}
	.notice-card code {
		font-family: monospace; font-size: 12px;
		padding: 1px 6px; border-radius: 4px;
		background: rgba(148,163,184,0.12); color: #e2e8f0;
	}

	@media (max-width: 900px) {
		.topology-grid { grid-template-columns: repeat(2, 1fr); }
	}
</style>
