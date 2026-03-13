<script lang="ts">
	let {
		open = false,
		onClose = () => {},
	}: {
		open: boolean;
		onClose: () => void;
	} = $props();

	let loading = $state(true);
	let data: any = $state(null);

	function formatUptime(seconds: number): string {
		if (!seconds || seconds <= 0) return '0초';
		const days = Math.floor(seconds / 86400);
		const hours = Math.floor((seconds % 86400) / 3600);
		const mins = Math.floor((seconds % 3600) / 60);
		const parts: string[] = [];
		if (days > 0) parts.push(`${days}일`);
		if (hours > 0) parts.push(`${hours}시간`);
		if (mins > 0) parts.push(`${mins}분`);
		return parts.join(' ') || '0분';
	}

	async function fetchData() {
		loading = true;
		try {
			const res = await fetch('/api/system/logins');
			const result = await res.json();
			if (result.success) data = result.data;
		} catch (e) {
			console.error('Failed to fetch login data:', e);
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
			<span class="modal-title">로그인 상세 정보</span>
			<button class="close-btn" onclick={onClose}>
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			{#if loading}
				<div class="loading-state">로그인 정보를 불러오는 중...</div>
			{:else if data}
				<div class="section-label">로그인 통계</div>
				<div class="stats-row">
					<div class="stat-card">
						<div class="stat-icon users">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">총 사용자</span>
							<span class="stat-value">{data.totalUsers ?? 0} <small>명</small></span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon active">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="8.5" cy="7" r="4"/><polyline points="17 11 19 13 23 9"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">활성 사용자</span>
							<span class="stat-value">{data.activeUsers ?? 0} <small>명</small></span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon uptime">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">시스템 가동시간</span>
							<span class="stat-value">{formatUptime(data.uptime)}</span>
						</div>
					</div>
				</div>

				<div class="section-label">현재 로그인된 사용자 ({data.users?.length ?? 0}명)</div>
				{#if data.users && data.users.length > 0}
					<div class="table-wrapper">
						<table>
							<thead>
								<tr>
									<th>사용자</th>
									<th>터미널</th>
									<th>IP 주소</th>
									<th>시간</th>
									<th>상태</th>
								</tr>
							</thead>
							<tbody>
								{#each data.users as user}
									<tr>
										<td class="mono">{user.user || 'N/A'}</td>
										<td>{user.terminal || 'N/A'}</td>
										<td class="mono">{user.host || 'N/A'}</td>
										<td>{user.loginTime || 'N/A'}</td>
										<td>
											<span class="status-badge" class:active={user.active} class:inactive={!user.active}>
												{user.active ? '사용' : '비사용'}
											</span>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{:else}
					<div class="empty-state">
						<svg width="48" height="48" viewBox="0 0 24 24" fill="none">
							<path fill-rule="evenodd" clip-rule="evenodd" d="M9.72961 3.99268C10.8216 2.39501 13.1784 2.39502 14.2703 3.99268L14.7023 4.62463C17.4083 8.58385 19.7333 12.7905 21.646 17.1881L21.7362 17.3956C22.4103 18.9453 21.3919 20.705 19.7124 20.8927C14.5867 21.4656 9.41323 21.4656 4.2876 20.8927C2.60805 20.705 1.58969 18.9453 2.26374 17.3956L2.35396 17.1881C4.26669 12.7905 6.59165 8.58384 9.29769 4.62463L9.72961 3.99268ZM13 9.00005C13 9.55233 12.5523 10 12 10C11.4477 10 11 9.55233 11 9.00005C11 8.44776 11.4477 8.00005 12 8.00005C12.5523 8.00005 13 8.44776 13 9.00005ZM12 11.75C12.4142 11.75 12.75 12.0858 12.75 12.5V17.5C12.75 17.9143 12.4142 18.25 12 18.25C11.5858 18.25 11.25 17.9143 11.25 17.5V12.5C11.25 12.0858 11.5858 11.75 12 11.75Z" fill="#475569"/>
						</svg>
						<span class="empty-text">정보 없음</span>
					</div>
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
		width: 860px; max-height: 85vh;
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
		display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
	}
	.stat-card {
		background: #121720; border-radius: 10px; padding: 16px;
		display: flex; align-items: center; gap: 12px;
	}
	.stat-icon {
		width: 40px; height: 40px; border-radius: 50%;
		display: flex; align-items: center; justify-content: center; flex-shrink: 0;
	}
	.stat-icon.users { background: rgba(48,213,200,0.15); color: #30d5c8; }
	.stat-icon.active { background: rgba(34,197,94,0.15); color: #22c55e; }
	.stat-icon.uptime { background: rgba(99,102,241,0.15); color: #6366f1; }
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
	.status-badge {
		padding: 3px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700;
	}
	.status-badge.active { color: #30d5c8; background: rgba(48,213,200,0.1); }
	.status-badge.inactive { color: #ef4444; background: rgba(239,68,68,0.1); }

	.empty-state {
		display: flex; flex-direction: column; align-items: center;
		justify-content: center; gap: 16px; padding: 56px 0;
	}
	.empty-text { font-size: 14px; color: #475569; }
</style>
