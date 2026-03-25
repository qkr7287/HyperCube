<script lang="ts">
	import { base } from '$app/paths';
	import { untrack } from 'svelte';
	import { cpuDetailStore, wsConnected, subscribe as wsSubscribe, unsubscribe as wsUnsubscribe } from '$lib/stores/ws-store';

	let {
		open = false,
		systemInfo = null,
		onClose = () => {},
	}: {
		open: boolean;
		systemInfo: any;
		onClose: () => void;
	} = $props();

	let loading = $state(true);
	let data: any = $state(null);
	let unsubStore: (() => void) | null = null;
	let fallbackInterval: ReturnType<typeof setInterval> | null = null;

	function getHeatColor(usage: number): string {
		if (usage < 15) return '#0d4f3c';
		if (usage < 30) return '#166534';
		if (usage < 45) return '#15803d';
		if (usage < 60) return '#a3a310';
		if (usage < 75) return '#ca8a04';
		if (usage < 85) return '#ea580c';
		if (usage < 95) return '#dc2626';
		return '#991b1b';
	}

	function getHeatGlow(usage: number): string {
		if (usage < 30) return 'none';
		if (usage < 60) return '0 0 8px rgba(202,138,4,0.3)';
		if (usage < 85) return '0 0 12px rgba(234,88,12,0.4)';
		return '0 0 16px rgba(220,38,38,0.5)';
	}

	async function fetchDataRest() {
		try {
			const res = await fetch(`${base}/api/system/cpu`);
			const result = await res.json();
			if (result.success) {
				data = result.data;
				loading = false;
			}
		} catch (e) {
			console.error('Failed to fetch CPU data:', e);
		}
	}

	function startFallbackPolling() {
		stopFallbackPolling();
		fetchDataRest();
		fallbackInterval = setInterval(fetchDataRest, 3000);
	}

	function stopFallbackPolling() {
		if (fallbackInterval) { clearInterval(fallbackInterval); fallbackInterval = null; }
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	$effect(() => {
		const isOpen = open;
		untrack(() => {
			if (isOpen) {
				loading = true;
				// Subscribe to cpu-detail WebSocket channel
				wsSubscribe('cpu-detail');
				unsubStore = cpuDetailStore.subscribe((storeData) => {
					if (storeData) {
						data = storeData;
						loading = false;
						// WS is delivering data, stop REST fallback
						stopFallbackPolling();
					}
				});
				// REST fallback: if WS doesn't deliver within 2s, start polling
				setTimeout(() => {
					if (loading) startFallbackPolling();
				}, 2000);
				document.addEventListener('keydown', handleKeydown);
			} else {
				wsUnsubscribe('cpu-detail');
				if (unsubStore) { unsubStore(); unsubStore = null; }
				stopFallbackPolling();
				document.removeEventListener('keydown', handleKeydown);
			}
		});
	});
</script>

{#if open}
<div class="overlay" onclick={onClose} role="dialog">
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<span class="modal-title">CPU 상세 정보</span>
			<button class="close-btn" onclick={onClose}>
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			{#if loading}
				<div class="loading-state">CPU 정보를 불러오는 중...</div>
			{:else if data}
				<!-- Overall stats -->
				<div class="stats-row">
					<div class="stat-card">
						<div class="stat-icon overall">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">전체 사용률</span>
							<span class="stat-value">{data.overall?.toFixed(1) ?? 0}<small>%</small></span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon cores">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="12" y1="2" x2="12" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="7" x2="22" y2="7"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="17" x2="22" y2="17"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">코어 수</span>
							<span class="stat-value">{data.cores} <small>cores</small></span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon load">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">Load Average</span>
							<span class="stat-value load-values">{data.loadAvg?.avg1?.toFixed(2)} <small>/</small> {data.loadAvg?.avg5?.toFixed(2)} <small>/</small> {data.loadAvg?.avg15?.toFixed(2)}</span>
						</div>
					</div>
				</div>

				<!-- Model -->
				<div class="model-row">
					<span class="model-label">Processor</span>
					<span class="model-text">{data.model}</span>
				</div>

				<!-- Heatmap -->
				<div class="section-label">코어별 사용률 히트맵</div>
				<div class="heatmap-legend">
					<span class="legend-label">Low</span>
					<div class="legend-gradient"></div>
					<span class="legend-label">High</span>
				</div>
				<div class="heatmap-grid" style="grid-template-columns: repeat({Math.min(data.perCore?.length ?? 4, 8)}, 1fr);">
					{#each (data.perCore || []) as core}
						<div
							class="heat-cell"
							style="background: {getHeatColor(core.usage)}; box-shadow: {getHeatGlow(core.usage)};"
							title="Core {core.core}: {core.usage.toFixed(1)}%"
						>
							<span class="heat-core-id">C{core.core}</span>
							<span class="heat-value">{core.usage.toFixed(0)}%</span>
						</div>
					{/each}
				</div>

				<!-- Legend scale -->
				<div class="scale-row">
					<span class="scale-item" style="background: #0d4f3c;">0-15%</span>
					<span class="scale-item" style="background: #166534;">15-30%</span>
					<span class="scale-item" style="background: #15803d;">30-45%</span>
					<span class="scale-item" style="background: #a3a310;">45-60%</span>
					<span class="scale-item" style="background: #ca8a04;">60-75%</span>
					<span class="scale-item" style="background: #ea580c;">75-85%</span>
					<span class="scale-item" style="background: #dc2626;">85-95%</span>
					<span class="scale-item" style="background: #991b1b;">95%+</span>
				</div>
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
		width: 720px; max-height: 85vh;
		background: #0d1117; border: 1px solid #30d5c8;
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
	.modal-content { flex: 1; overflow-y: auto; padding: 28px; display: flex; flex-direction: column; gap: 20px; }
	.loading-state { text-align: center; color: #64748b; font-size: 14px; padding: 32px; }
	.section-label { font-size: 14px; font-weight: 700; color: #64748b; }

	.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
	.stat-card {
		background: #121720; border-radius: 10px; padding: 16px;
		display: flex; align-items: center; gap: 12px;
	}
	.stat-icon {
		width: 40px; height: 40px; border-radius: 50%;
		display: flex; align-items: center; justify-content: center; flex-shrink: 0;
	}
	.stat-icon.overall { background: rgba(48,213,200,0.15); color: #30d5c8; }
	.stat-icon.cores { background: rgba(99,102,241,0.15); color: #6366f1; }
	.stat-icon.load { background: rgba(245,158,11,0.15); color: #f59e0b; }
	.stat-info { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
	.stat-label { font-size: 12px; color: #64748b; }
	.stat-value { font-size: 15px; font-weight: 700; color: #cbd5e1; }
	.stat-value small { font-size: 12px; font-weight: 400; color: #64748b; }
	.load-values { font-size: 13px; }

	.model-row {
		background: #121720; border-radius: 10px; padding: 12px 16px;
		display: flex; align-items: center; gap: 12px;
	}
	.model-label { font-size: 12px; color: #64748b; white-space: nowrap; }
	.model-text { font-size: 12px; color: #cbd5e1; font-family: monospace; }

	/* Heatmap */
	.heatmap-legend {
		display: flex; align-items: center; gap: 8px;
	}
	.legend-label { font-size: 10px; color: #475569; }
	.legend-gradient {
		flex: 1; height: 6px; border-radius: 3px;
		background: linear-gradient(to right, #0d4f3c, #166534, #15803d, #a3a310, #ca8a04, #ea580c, #dc2626, #991b1b);
	}

	.heatmap-grid {
		display: grid;
		gap: 6px;
	}

	.heat-cell {
		aspect-ratio: 1;
		border-radius: 8px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		transition: background 0.5s ease, box-shadow 0.5s ease;
		cursor: default;
		min-height: 56px;
	}

	.heat-core-id {
		font-size: 10px;
		font-weight: 700;
		color: rgba(255,255,255,0.5);
		font-family: monospace;
	}

	.heat-value {
		font-size: 14px;
		font-weight: 700;
		color: rgba(255,255,255,0.9);
		font-family: monospace;
	}

	.scale-row {
		display: flex; gap: 4px; justify-content: center;
	}
	.scale-item {
		padding: 3px 8px; border-radius: 4px;
		font-size: 9px; font-weight: 600; color: rgba(255,255,255,0.7);
		font-family: monospace;
	}
</style>
