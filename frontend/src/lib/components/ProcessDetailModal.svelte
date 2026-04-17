<script lang="ts">
	import { sendCommand } from '$lib/stores/ws-store';
	import { adaptProcessDetail } from '$lib/utils/data-adapter';

	let {
		open = false,
		onClose = () => {},
	}: {
		open: boolean;
		onClose: () => void;
	} = $props();

	let loading = $state(true);
	let data: any = $state(null);

	let maxMem = $derived(
		(data?.processes ?? []).reduce(
			(m: number, p: any) => Math.max(m, p.memory ?? 0),
			0,
		)
	);

	function formatMem(mb: number): string {
		if (!mb || mb <= 0) return '0 MB';
		if (mb < 1024) return `${mb.toFixed(1)} MB`;
		return `${(mb / 1024).toFixed(2)} GB`;
	}

	function getStatusLabel(status: string): string {
		// Agent가 전체 단어로 state를 보냄 (running/sleeping/stopped/zombie ...)
		const map: Record<string, string> = {
			running: '실행중', R: '실행중',
			sleeping: '대기', S: '대기', D: '대기(I/O)', I: '유휴',
			stopped: '정지', T: '정지',
			zombie: '좀비', Z: '좀비',
		};
		return map[status] || status;
	}

	function getStatusClass(status: string): string {
		if (status === 'running' || status === 'R') return 'running';
		if (status === 'zombie' || status === 'Z') return 'zombie';
		if (status === 'stopped' || status === 'T') return 'stopped';
		return 'sleeping';
	}

	async function fetchData() {
		loading = true;
		try {
			const raw = await sendCommand('system_info', { subCommand: 'processes' });
			data = adaptProcessDetail(raw);
		} catch (e) {
			console.error('[ProcessDetailModal] sendCommand failed:', e);
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
			<span class="modal-title">프로세스 상세 정보</span>
			<button class="close-btn" onclick={onClose}>
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			{#if loading}
				<div class="loading-state">프로세스 정보를 불러오는 중...</div>
			{:else if data}
				{@const procs = data.processes ?? []}
				{@const topCpu = procs.length ? procs.reduce((a: any, b: any) => (b.cpu > a.cpu ? b : a)) : null}
				{@const topMem = procs.length ? procs.reduce((a: any, b: any) => (b.memoryMB > a.memoryMB ? b : a)) : null}
				<div class="stats-row">
					<div class="stat-pill">
						<span class="pill-label">총 프로세스</span>
						<span class="pill-value">{data.totalProcesses ?? 0}<small>개</small></span>
					</div>
					{#if topCpu}
						<div class="stat-pill" title={topCpu.command || topCpu.name}>
							<span class="pill-label">Top CPU</span>
							<span class="pill-value">
								<span class="pill-name">{topCpu.name}</span>
								<small class="pill-metric">{(topCpu.cpu ?? 0).toFixed(1)}%</small>
							</span>
						</div>
					{/if}
					{#if topMem}
						<div class="stat-pill" title={topMem.command || topMem.name}>
							<span class="pill-label">Top Memory</span>
							<span class="pill-value">
								<span class="pill-name">{topMem.name}</span>
								<small class="pill-metric">{formatMem(topMem.memoryMB ?? 0)}</small>
							</span>
						</div>
					{/if}
					{#if (data.zombieProcesses ?? 0) > 0}
						<div class="stat-pill warn" title="종료됐으나 부모가 회수(reap)하지 않은 좀비 프로세스">
							<span class="pill-label">좀비</span>
							<span class="pill-value">{data.zombieProcesses}<small>개</small></span>
						</div>
					{/if}
				</div>

				<div class="section-label">프로세스 목록 <small class="hint">CPU 사용률 상위 {data.processes?.length ?? 0}개</small></div>
				<div class="table-wrapper">
					<table>
						<thead>
							<tr>
								<th>PID</th>
								<th>프로세스명</th>
								<th>CPU</th>
								<th>메모리</th>
								<th>상태</th>
								<th>사용자</th>
							</tr>
						</thead>
						<tbody>
							{#each (data.processes || []) as proc}
								<tr>
									<td class="mono">{proc.pid}</td>
									<td class="proc-name" title={proc.command}>{proc.name}</td>
									<td>
										<div class="bar-cell">
											<div class="bar-track">
												<div class="bar-fill cpu" style="width: {Math.min(proc.cpu, 100)}%"></div>
											</div>
											<span class="bar-value">{proc.cpu.toFixed(1)}%</span>
										</div>
									</td>
									<td>
										<div class="bar-cell">
											<div class="bar-track">
												<div class="bar-fill mem" style="width: {maxMem > 0 ? Math.min((proc.memory / maxMem) * 100, 100) : 0}%"></div>
											</div>
											<span class="bar-value">{formatMem(proc.memory)}</span>
										</div>
									</td>
									<td>
										<span class="status-badge {getStatusClass(proc.status)}">
											{getStatusLabel(proc.status)}
										</span>
									</td>
									<td class="mono">{proc.user}</td>
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
	.modal-content { flex: 1; overflow-y: auto; padding: 28px; display: flex; flex-direction: column; gap: 28px; }
	.loading-state { text-align: center; color: #64748b; font-size: 14px; padding: 32px; }
	.section-label { font-size: 14px; font-weight: 700; color: #64748b; }

	.stats-row {
		display: flex; flex-wrap: wrap; gap: 8px;
	}
	.stat-pill {
		background: #121720; border-radius: 8px; padding: 8px 14px;
		display: inline-flex; align-items: center; gap: 10px;
		border: 1px solid transparent; min-width: 0;
	}
	.stat-pill.warn {
		border-color: rgba(239,68,68,0.4);
		background: rgba(239,68,68,0.05);
	}
	.pill-label {
		font-size: 11px; color: #64748b; font-weight: 600;
		text-transform: uppercase; letter-spacing: 0.04em;
		white-space: nowrap;
	}
	.pill-value {
		font-size: 14px; font-weight: 700; color: #cbd5e1;
		display: inline-flex; align-items: baseline; gap: 6px;
		min-width: 0;
	}
	.pill-value small { font-size: 11px; font-weight: 400; color: #64748b; }
	.pill-name {
		max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
	}
	.pill-metric { font-size: 11px; color: #30d5c8; font-weight: 600; }
	.hint { font-size: 10px; color: #475569; font-weight: 400; }

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
	.proc-name {
		max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
	}

	.bar-cell {
		display: flex; align-items: center; gap: 8px; min-width: 140px;
	}
	.bar-track {
		flex: 1; height: 7px; background: #1f2937; border-radius: 4px; overflow: hidden;
	}
	.bar-fill {
		height: 100%; border-radius: 4px; transition: width 0.3s ease;
	}
	.bar-fill.cpu { background: #30d5c8; }
	.bar-fill.mem { background: #6366f1; }
	.bar-value {
		font-size: 12px; color: #94a3b8; min-width: 44px; text-align: right;
		font-family: monospace;
	}

	.status-badge {
		padding: 3px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700;
	}
	.status-badge.running { color: #22c55e; background: rgba(34,197,94,0.1); }
	.status-badge.sleeping { color: #f59e0b; background: rgba(245,158,11,0.1); }
	.status-badge.zombie { color: #ef4444; background: rgba(239,68,68,0.1); }
	.status-badge.stopped { color: #64748b; background: rgba(100,116,139,0.1); }
</style>
