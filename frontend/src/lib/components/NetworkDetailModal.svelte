<script lang="ts">
	import { sendCommand } from '$lib/stores/ws-store';
	import { adaptNetworkDetail } from '$lib/utils/data-adapter';
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
		systemInfo?: any;
		agentId?: string;
		accessToken?: string;
		onClose: () => void;
	} = $props();

	let liveConns = $derived(systemInfo?.network?.connections ?? 0);

	let loading = $state(true);
	let data: any = $state(null);

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		if (bytes < 1024) return bytes + ' B';
		if (bytes < 1048576) return (bytes / 1024).toFixed(2) + ' KB';
		if (bytes < 1073741824) return (bytes / 1048576).toFixed(2) + ' MB';
		return (bytes / 1073741824).toFixed(2) + ' GB';
	}

	function formatNumber(n: number): string {
		return n.toLocaleString();
	}

	async function fetchData() {
		loading = true;
		try {
			const raw = await sendCommand('system_info', { subCommand: 'network_detail' });
			data = adaptNetworkDetail(raw);
		} catch (e) {
			console.error('[NetworkDetailModal] sendCommand failed:', e);
		}
		loading = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	$effect(() => {
		if (open) {
			fetchData();
			document.addEventListener('keydown', handleKeydown);
		} else {
			document.removeEventListener('keydown', handleKeydown);
		}
	});
</script>

{#if open}
<div class="overlay" onclick={onClose} role="dialog">
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<span class="modal-title">네트워크 상세 정보</span>
			<button class="close-btn" onclick={onClose}>
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			<div class="section-label">
				네트워크 연결 수 추이
				<InfoTooltip
					placement="bottom-start"
					text="지금 서버가 열어두고 있는 TCP 연결 개수예요. 평소 대비 갑자기 치솟으면 외부에서 요청이 몰렸거나 어떤 프로그램이 연결을 정리하지 않고 쌓고 있는 상황일 수 있어요."
				/>
				<span class="section-current">현재 {liveConns}</span>
			</div>
			<MetricTrendChart
				{agentId}
				{accessToken}
				metricField="network_connections"
				liveValue={liveConns}
				label="TCP 연결 수"
				color="#4ade80"
				unit="count"
				defaultRange="5m"
			/>

			{#if loading}
				<div class="loading-state">네트워크 정보를 불러오는 중...</div>
			{:else if data}
				<div class="section-label">네트워크 통계 (연결 수: {data.connections ?? 0}개)</div>
				<div class="stats-row">
					<div class="stat-card">
						<div class="stat-icon rx">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">수신 바이트</span>
							<span class="stat-value">{formatBytes(data.stats?.rx_bytes || 0)}</span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon tx">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">송신 바이트</span>
							<span class="stat-value">{formatBytes(data.stats?.tx_bytes || 0)}</span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon pkt">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">수신 패킷</span>
							<span class="stat-value">{formatNumber(data.stats?.rx_packets || 0)}</span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon pkt">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">송신 패킷</span>
							<span class="stat-value">{formatNumber(data.stats?.tx_packets || 0)}</span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon err">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">수신 오류</span>
							<span class="stat-value">{data.stats?.rx_errors ?? 0}</span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon err">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">송신 오류</span>
							<span class="stat-value">{data.stats?.tx_errors ?? 0}</span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon conn">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">활성 연결</span>
							<span class="stat-value">{data.connections ?? 0} <small>개</small></span>
						</div>
					</div>
				</div>

				<div class="section-label">네트워크 인터페이스 ({data.interfaces?.length ?? 0}개)</div>
				<div class="table-wrapper">
					<table>
						<thead>
							<tr>
								<th>MAC 주소</th>
								<th>IP 주소</th>
								<th>속도</th>
								<th>MTU</th>
								<th>상태</th>
							</tr>
						</thead>
						<tbody>
							{#each (data.interfaces || []) as iface}
								<tr class:dimmed={!iface.up}>
									<td class="mono">{iface.mac || 'N/A'}</td>
									<td>{iface.addresses?.[0]?.address || 'N/A'}{iface.addresses?.[0]?.family ? `(${iface.addresses[0].family})` : ''}</td>
									<td>{iface.speed || 'N/A'}</td>
									<td>{iface.mtu || 'N/A'}</td>
									<td><span class="status-badge" class:up={iface.up} class:down={!iface.up}>{iface.up ? 'UP' : 'DOWN'}</span></td>
								</tr>
							{/each}
						</tbody>
					</table>
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
		width: 1080px; max-height: 85vh;
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
		background: rgba(48, 213, 200, 0.55);
		background-clip: padding-box;
	}

	.loading-state { text-align: center; color: #64748b; font-size: 14px; padding: 32px; }
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
		color: #4ade80;
		font-variant-numeric: tabular-nums;
	}

	.stats-row {
		display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
	}
	.stat-card {
		background: #121720; border-radius: 10px; padding: 16px;
		display: flex; align-items: center; gap: 12px;
	}
	.stat-icon {
		width: 40px; height: 40px; border-radius: 50%;
		display: flex; align-items: center; justify-content: center; flex-shrink: 0;
	}
	.stat-icon.rx { background: rgba(48,213,200,0.15); color: #30d5c8; }
	.stat-icon.tx { background: rgba(99,102,241,0.15); color: #6366f1; }
	.stat-icon.pkt { background: rgba(139,92,246,0.15); color: #8b5cf6; }
	.stat-icon.err { background: rgba(239,68,68,0.15); color: #ef4444; }
	.stat-icon.conn { background: rgba(245,158,11,0.15); color: #f59e0b; }
	.stat-info { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
	.stat-label { font-size: 12px; color: #64748b; white-space: nowrap; }
	.stat-value { font-size: 15px; font-weight: 700; color: #cbd5e1; white-space: nowrap; }
	.stat-value small { font-size: 12px; font-weight: 400; color: #64748b; }

	.table-wrapper { overflow-x: auto; }
	table { width: 100%; border-collapse: collapse; }
	th {
		text-align: left; padding: 12px 18px; font-size: 13px;
		font-weight: 700; color: #64748b; border-bottom: 1px solid #1f2937;
	}
	td {
		padding: 12px 18px; font-size: 13px; color: #cbd5e1;
		border-bottom: 1px solid rgba(31,41,55,0.5);
	}
	td.mono { font-family: monospace; font-size: 12px; }
	tr.dimmed td { color: #475569; }
	.status-badge {
		padding: 3px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700;
	}
	.status-badge.up { color: #30d5c8; background: rgba(48,213,200,0.1); }
	.status-badge.down { color: #ef4444; background: rgba(239,68,68,0.1); }
</style>
