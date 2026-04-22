<script lang="ts">
	import MetricTrendChart from './MetricTrendChart.svelte';
	import InfoTooltip from './InfoTooltip.svelte';

	let {
		open = false,
		systemInfo = null,
		agentId = '',
		accessToken = '',
		onClose = () => {},
	}: {
		open: boolean;
		systemInfo: any;
		agentId?: string;
		accessToken?: string;
		onClose: () => void;
	} = $props();

	let usagePercent = $derived(Math.round(systemInfo?.disk?.usage ?? 0));

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	$effect(() => {
		if (open) {
			document.addEventListener('keydown', handleKeydown);
		} else {
			document.removeEventListener('keydown', handleKeydown);
		}
	});
</script>

{#if open && systemInfo}
<div class="overlay" onclick={onClose} role="dialog">
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<span class="modal-title">디스크 상세 정보</span>
			<button class="close-btn" onclick={onClose}>
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			<div class="section-label">디스크 사용 현황</div>
			<div class="stats-row">
				<div class="stat-card">
					<div class="stat-icon total">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
					</div>
					<div class="stat-info">
						<span class="stat-label">전체 용량</span>
						<span class="stat-value">{systemInfo.disk?.total ?? 'N/A'}</span>
					</div>
				</div>
				<div class="stat-card">
					<div class="stat-icon used">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
					</div>
					<div class="stat-info">
						<span class="stat-label">사용 중</span>
						<span class="stat-value">{systemInfo.disk?.used ?? 'N/A'}</span>
					</div>
				</div>
				<div class="stat-card">
					<div class="stat-icon free">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="15"/><line x1="15" y1="9" x2="9" y2="15"/></svg>
					</div>
					<div class="stat-info">
						<span class="stat-label">사용 가능</span>
						<span class="stat-value">{systemInfo.disk?.free ?? 'N/A'}</span>
					</div>
				</div>
				<div class="stat-card">
					<div class="stat-icon percent">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
					</div>
					<div class="stat-info">
						<span class="stat-label">사용률</span>
						<span class="stat-value">{usagePercent}<small>%</small></span>
					</div>
				</div>
			</div>

			<div class="section-label">사용률 게이지</div>
			<div class="gauge-card">
				<div class="gauge-bar-track">
					<div class="gauge-bar-fill" style="width: {usagePercent}%; background: {usagePercent > 80 ? '#ef4444' : usagePercent > 50 ? '#f59e0b' : '#30d5c8'};"></div>
				</div>
				<div class="gauge-info">
					<span class="gauge-used">{systemInfo.disk?.used ?? '0G'} 사용</span>
					<span class="gauge-free">{systemInfo.disk?.free ?? '0G'} 여유</span>
				</div>
			</div>

			<div class="section-label">
				디스크 사용률 추이
				<InfoTooltip
					placement="right"
					text="디스크(SSD/HDD)가 얼마나 차 있는지 시간 순서로 보여줘요. 90% 넘으면 공간 부족 경고, 꾸준히 올라가기만 하면 로그나 임시 파일이 계속 쌓이는 중이라 정리가 필요할 수 있어요."
				/>
				<span class="section-current">현재 {usagePercent}%</span>
			</div>
			<MetricTrendChart
				{agentId}
				{accessToken}
				metricField="disk_usage"
				liveValue={usagePercent}
				label="디스크 사용률 (%)"
				color="#f59e0b"
				unit="percent"
				defaultRange="1h"
			/>

			{#if systemInfo.docker}
				<div class="section-label">Docker 스토리지</div>
				<div class="stats-row">
					<div class="stat-card">
						<div class="stat-icon docker">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">컨테이너</span>
							<span class="stat-value">{systemInfo.docker.containers ?? 0} <small>개</small></span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon images">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">이미지</span>
							<span class="stat-value">{systemInfo.docker.images ?? 0} <small>개</small></span>
						</div>
					</div>
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
		width: 700px; max-height: 85vh;
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
	.modal-content {
		flex: 1;
		overflow-y: auto;
		padding: 28px;
		display: flex;
		flex-direction: column;
		gap: 24px;
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
		background: rgba(48, 213, 200, 0.55);
		background-clip: padding-box;
	}

	.section-label {
		font-size: 14px;
		font-weight: 700;
		color: #64748b;
		display: flex;
		align-items: baseline;
		gap: 10px;
	}
	.section-current {
		margin-left: auto;
		font-size: 13px;
		font-weight: 700;
		color: #f59e0b;
		font-variant-numeric: tabular-nums;
	}

	.stats-row { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
	.stat-card {
		background: #121720; border-radius: 10px; padding: 16px;
		display: flex; align-items: center; gap: 12px;
	}
	.stat-icon {
		width: 40px; height: 40px; border-radius: 50%;
		display: flex; align-items: center; justify-content: center; flex-shrink: 0;
	}
	.stat-icon.total { background: rgba(48,213,200,0.15); color: #30d5c8; }
	.stat-icon.used { background: rgba(245,158,11,0.15); color: #f59e0b; }
	.stat-icon.free { background: rgba(34,197,94,0.15); color: #22c55e; }
	.stat-icon.percent { background: rgba(99,102,241,0.15); color: #6366f1; }
	.stat-icon.docker { background: rgba(56,189,248,0.15); color: #38bdf8; }
	.stat-icon.images { background: rgba(139,92,246,0.15); color: #8b5cf6; }
	.stat-info { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
	.stat-label { font-size: 12px; color: #64748b; }
	.stat-value { font-size: 15px; font-weight: 700; color: #cbd5e1; }
	.stat-value small { font-size: 12px; font-weight: 400; color: #64748b; }

	.gauge-card {
		background: #121720; border-radius: 10px; padding: 20px;
		display: flex; flex-direction: column; gap: 10px;
	}
	.gauge-bar-track {
		height: 14px; background: #1f2937; border-radius: 7px; overflow: hidden;
	}
	.gauge-bar-fill {
		height: 100%; border-radius: 7px; transition: width 0.5s ease;
	}
	.gauge-info {
		display: flex; justify-content: space-between;
		font-size: 12px; color: #64748b;
	}
	.gauge-used { color: #f59e0b; }
	.gauge-free { color: #22c55e; }
</style>
