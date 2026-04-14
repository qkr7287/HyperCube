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
				<div class="section-label">프로세스 통계</div>
				<div class="stats-row">
					<div class="stat-card">
						<div class="stat-icon total">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6M9 13h6M9 17h4"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">총 프로세스</span>
							<span class="stat-value">{data.totalProcesses ?? 0} <small>개</small></span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon run">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">실행중</span>
							<span class="stat-value">{data.runningProcesses ?? 0} <small>개</small></span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon sleep">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">대기중</span>
							<span class="stat-value">{data.sleepingProcesses ?? 0} <small>개</small></span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon zombie">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">정지중</span>
							<span class="stat-value">{data.zombieProcesses ?? 0} <small>개</small></span>
						</div>
					</div>
				</div>

				<div class="section-label">실행중인 프로세스 (상위 {data.processes?.length ?? 0}개)</div>
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
	.stat-icon.total { background: rgba(48,213,200,0.15); color: #30d5c8; }
	.stat-icon.run { background: rgba(34,197,94,0.15); color: #22c55e; }
	.stat-icon.sleep { background: rgba(245,158,11,0.15); color: #f59e0b; }
	.stat-icon.zombie { background: rgba(239,68,68,0.15); color: #ef4444; }
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
