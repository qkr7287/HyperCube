<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';

	export let detailType: 'network' | 'logins' | 'processes';

	const dispatch = createEventDispatcher();

	let activeTab = 'overview';
	let loading = false;
	let error = '';
	let detailData: any = null;

	// 상세 데이터
	let networkDetails: any = null;
	let loginDetails: any = null;
	let processDetails: any = null;

	onMount(() => {
		fetchDetailData();
	});

	function closeModal() {
		dispatch('close');
	}

	async function fetchDetailData() {
		loading = true;
		error = '';
		
		try {
			let response;
			
			switch (detailType) {
				case 'network':
					response = await fetch('/api/system/network');
					break;
				case 'logins':
					response = await fetch('/api/system/logins');
					break;
				case 'processes':
					response = await fetch('/api/system/processes');
					break;
				default:
					throw new Error('Unknown detail type');
			}

			const result = await response.json();
			
			if (result.success) {
				detailData = result.data;
				
				// 타입별로 데이터 처리
				switch (detailType) {
					case 'network':
						networkDetails = result.data;
						break;
					case 'logins':
						loginDetails = result.data;
						break;
					case 'processes':
						processDetails = result.data;
						break;
				}
			} else {
				error = result.error || '데이터를 가져오는데 실패했습니다.';
			}
		} catch (err) {
			error = '서버 상세 정보를 가져오는데 실패했습니다.';
			console.error('Error fetching detail data:', err);
		} finally {
			loading = false;
		}
	}

	function getTitle(): string {
		switch (detailType) {
			case 'network': return '네트워크 상세 정보';
			case 'logins': return '로그인 상세 정보';
			case 'processes': return '프로세스 상세 정보';
			default: return '서버 상세 정보';
		}
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
	}

	function formatUptime(seconds: number): string {
		const days = Math.floor(seconds / 86400);
		const hours = Math.floor((seconds % 86400) / 3600);
		const minutes = Math.floor((seconds % 3600) / 60);
		
		if (days > 0) {
			return `${days}일 ${hours}시간 ${minutes}분`;
		} else if (hours > 0) {
			return `${hours}시간 ${minutes}분`;
		} else {
			return `${minutes}분`;
		}
	}

	function getProcessStatusClass(status: string): string {
		switch (status?.toLowerCase()) {
			case 'running': return 'running';
			case 'sleeping': return 'sleeping';
			case 'stopped': return 'stopped';
			case 'zombie': return 'zombie';
			default: return 'unknown';
		}
	}

	function getProcessStatusText(status: string): string {
		switch (status?.toLowerCase()) {
			case 'running': return '실행 중';
			case 'sleeping': return '대기 중';
			case 'stopped': return '중지됨';
			case 'zombie': return '좀비';
			default: return '알 수 없음';
		}
	}
</script>

<div class="modal-overlay" role="dialog" aria-modal="true" tabindex="-1" on:click={closeModal} on:keydown={(e) => e.key === 'Escape' && closeModal()}>
	<div class="modal" role="document" on:click|stopPropagation on:keydown|stopPropagation>
		<div class="modal-header">
			<h2>{getTitle()}</h2>
			<button class="close-btn" on:click={closeModal}>×</button>
		</div>

		<div class="modal-body">
			{#if loading}
				<div class="loading">로딩 중...</div>
			{:else if error}
				<div class="error">{error}</div>
			{:else}
				{#if detailType === 'network'}
					<div class="network-details">
						<div class="section-header">
							<h3>네트워크 인터페이스 ({networkDetails?.interfaces?.length || 0}개)</h3>
						</div>
						
						{#if networkDetails?.interfaces}
							<div class="interfaces-grid">
								{#each networkDetails.interfaces as iface}
									<div class="interface-card">
										<div class="interface-header">
											<h4>{iface.name}</h4>
											<span class="interface-status {iface.up ? 'up' : 'down'}">
												{iface.up ? 'UP' : 'DOWN'}
											</span>
										</div>
										
										<div class="interface-info">
											<div class="info-row">
												<span class="label">MAC 주소:</span>
												<span class="value">{iface.mac || 'N/A'}</span>
											</div>
											
											{#if iface.addresses}
												<div class="info-row">
													<span class="label">IP 주소:</span>
													<div class="addresses">
														{#each iface.addresses as addr}
															<span class="address">{addr.address} ({addr.family})</span>
														{/each}
													</div>
												</div>
											{/if}
											
											<div class="info-row">
												<span class="label">속도:</span>
												<span class="value">{iface.speed || 'N/A'}</span>
											</div>
											
											<div class="info-row">
												<span class="label">MTU:</span>
												<span class="value">{iface.mtu || 'N/A'}</span>
											</div>
										</div>
									</div>
								{/each}
							</div>
						{/if}

						<div class="section-header">
							<h3>네트워크 통계 (연결 수: {networkDetails?.connections || 0}개)</h3>
						</div>
						
						{#if networkDetails?.stats}
							<div class="stats-grid">
								<div class="stat-card">
									<div class="stat-icon">📥</div>
									<div class="stat-content">
										<div class="stat-value">{formatBytes(networkDetails.stats.rx_bytes || 0)}</div>
										<div class="stat-label">수신 바이트</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">📤</div>
									<div class="stat-content">
										<div class="stat-value">{formatBytes(networkDetails.stats.tx_bytes || 0)}</div>
										<div class="stat-label">송신 바이트</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">📦</div>
									<div class="stat-content">
										<div class="stat-value">{networkDetails.stats.rx_packets || 0}</div>
										<div class="stat-label">수신 패킷</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">📦</div>
									<div class="stat-content">
										<div class="stat-value">{networkDetails.stats.tx_packets || 0}</div>
										<div class="stat-label">송신 패킷</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">❌</div>
									<div class="stat-content">
										<div class="stat-value">{networkDetails.stats.rx_errors || 0}</div>
										<div class="stat-label">수신 오류</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">❌</div>
									<div class="stat-content">
										<div class="stat-value">{networkDetails.stats.tx_errors || 0}</div>
										<div class="stat-label">송신 오류</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">🔗</div>
									<div class="stat-content">
										<div class="stat-value">{networkDetails.connections || 0}</div>
										<div class="stat-label">활성 연결</div>
									</div>
								</div>
							</div>
						{/if}
					</div>

				{:else if detailType === 'logins'}
					<div class="logins-details">
						<div class="section-header">
							<h3>현재 로그인된 사용자</h3>
						</div>
						
						{#if loginDetails?.users}
							<div class="users-grid">
								{#each loginDetails.users as user}
									<div class="user-card">
										<div class="user-header">
											<div class="user-info">
												<div class="user-name">{user.user}</div>
												<div class="user-terminal">{user.terminal}</div>
											</div>
											<div class="user-status">
												<span class="status-dot {user.active ? 'active' : 'inactive'}"></span>
												{user.active ? '활성' : '비활성'}
											</div>
										</div>
										
										<div class="user-details">
											<div class="detail-row">
												<span class="label">호스트:</span>
												<span class="value">{user.host || 'N/A'}</span>
											</div>
											
											<div class="detail-row">
												<span class="label">로그인 시간:</span>
												<span class="value">{user.loginTime || 'N/A'}</span>
											</div>
											
											<div class="detail-row">
												<span class="label">마지막 활동:</span>
												<span class="value">{user.lastActivity || 'N/A'}</span>
											</div>
											
											{#if user.process}
												<div class="detail-row">
													<span class="label">프로세스:</span>
													<span class="value">{user.process}</span>
												</div>
											{/if}
										</div>
									</div>
								{/each}
							</div>
						{:else}
							<div class="no-data">
								<div class="no-data-icon">👤</div>
								<p>현재 로그인된 사용자가 없습니다.</p>
							</div>
						{/if}

						<div class="section-header">
							<h3>로그인 통계</h3>
						</div>
						
						<div class="stats-grid">
							<div class="stat-card">
								<div class="stat-icon">👥</div>
								<div class="stat-content">
									<div class="stat-value">{loginDetails?.totalUsers || 0}</div>
									<div class="stat-label">총 사용자</div>
								</div>
							</div>
							
							<div class="stat-card">
								<div class="stat-icon">🟢</div>
								<div class="stat-content">
									<div class="stat-value">{loginDetails?.activeUsers || 0}</div>
									<div class="stat-label">활성 사용자</div>
								</div>
							</div>
							
							<div class="stat-card">
								<div class="stat-icon">🕐</div>
								<div class="stat-content">
									<div class="stat-value">{loginDetails?.uptime ? formatUptime(loginDetails.uptime) : 'N/A'}</div>
									<div class="stat-label">시스템 가동시간</div>
								</div>
							</div>
						</div>
					</div>

				{:else if detailType === 'processes'}
					<div class="processes-details">
						<div class="section-header">
							<h3>실행 중인 프로세스</h3>
						</div>
						
						{#if processDetails?.processes}
							<div class="processes-table">
								<div class="table-header">
									<div class="col-pid">PID</div>
									<div class="col-name">프로세스명</div>
									<div class="col-cpu">CPU%</div>
									<div class="col-memory">메모리%</div>
									<div class="col-status">상태</div>
									<div class="col-user">사용자</div>
								</div>
								
								{#each processDetails.processes.slice(0, 50) as process}
									<div class="table-row">
										<div class="col-pid">{process.pid}</div>
										<div class="col-name" title={process.command}>
											{process.name || process.command?.split(' ')[0] || 'N/A'}
										</div>
										<div class="col-cpu">
											<div class="progress-bar">
												<div class="progress-fill" style="width: {Math.min(process.cpu || 0, 100)}%"></div>
												<span class="progress-text">{process.cpu?.toFixed(1) || '0.0'}%</span>
											</div>
										</div>
										<div class="col-memory">
											<div class="progress-bar">
												<div class="progress-fill memory" style="width: {Math.min(process.memory || 0, 100)}%"></div>
												<span class="progress-text">{process.memory?.toFixed(1) || '0.0'}%</span>
											</div>
										</div>
										<div class="col-status">
											<span class="status-badge {getProcessStatusClass(process.status)}">
												{getProcessStatusText(process.status)}
											</span>
										</div>
										<div class="col-user">{process.user || 'N/A'}</div>
									</div>
								{/each}
							</div>
						{:else}
							<div class="no-data">
								<div class="no-data-icon">⚙️</div>
								<p>프로세스 정보를 가져올 수 없습니다.</p>
							</div>
						{/if}

						<div class="section-header">
							<h3>프로세스 통계</h3>
						</div>
						
						<div class="stats-grid">
							<div class="stat-card">
								<div class="stat-icon">⚙️</div>
								<div class="stat-content">
									<div class="stat-value">{processDetails?.totalProcesses || 0}</div>
									<div class="stat-label">총 프로세스</div>
								</div>
							</div>
							
							<div class="stat-card">
								<div class="stat-icon">🟢</div>
								<div class="stat-content">
									<div class="stat-value">{processDetails?.runningProcesses || 0}</div>
									<div class="stat-label">실행 중</div>
								</div>
							</div>
							
							<div class="stat-card">
								<div class="stat-icon">😴</div>
								<div class="stat-content">
									<div class="stat-value">{processDetails?.sleepingProcesses || 0}</div>
									<div class="stat-label">대기 중</div>
								</div>
							</div>
							
							<div class="stat-card">
								<div class="stat-icon">🧟</div>
								<div class="stat-content">
									<div class="stat-value">{processDetails?.zombieProcesses || 0}</div>
									<div class="stat-label">좀비 프로세스</div>
								</div>
							</div>
						</div>
					</div>
				{/if}
			{/if}
		</div>
	</div>
</div>

<style>
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		background: rgba(0, 0, 0, 0.7);
		display: flex;
		justify-content: center;
		align-items: center;
		z-index: 1000;
	}

	.modal {
		background: white;
		border-radius: 12px;
		width: 90%;
		max-width: 1200px;
		max-height: 90vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 20px 30px;
		border-bottom: 1px solid #e0e0e0;
		background: #f8f9fa;
		border-radius: 12px 12px 0 0;
	}

	.modal-header h2 {
		margin: 0;
		color: #2c3e50;
		font-size: 1.5rem;
		font-weight: 600;
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 2rem;
		cursor: pointer;
		color: #7f8c8d;
		padding: 0;
		width: 40px;
		height: 40px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		transition: all 0.2s ease;
	}

	.close-btn:hover {
		background: #e74c3c;
		color: white;
	}

	.modal-body {
		flex: 1;
		overflow-y: auto;
		padding: 30px;
	}

	.section-header {
		margin: 30px 0 20px 0;
		padding-bottom: 10px;
		border-bottom: 2px solid #e0e0e0;
	}

	.section-header h3 {
		margin: 0;
		color: #2c3e50;
		font-size: 1.3rem;
		font-weight: 600;
	}

	.interfaces-grid, .users-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
		gap: 20px;
		margin-bottom: 30px;
	}

	.interface-card, .user-card {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 12px;
		padding: 20px;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
		transition: transform 0.2s ease, box-shadow 0.2s ease;
	}

	.interface-card:hover, .user-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
	}

	.interface-header, .user-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 15px;
	}

	.interface-header h4, .user-name {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 600;
		color: #2c3e50;
	}

	.interface-status {
		padding: 4px 12px;
		border-radius: 20px;
		font-size: 0.8rem;
		font-weight: 600;
		text-transform: uppercase;
	}

	.interface-status.up {
		background: #d4edda;
		color: #155724;
	}

	.interface-status.down {
		background: #f8d7da;
		color: #721c24;
	}

	.user-terminal {
		font-size: 0.9rem;
		color: #7f8c8d;
		margin-top: 2px;
	}

	.user-status {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 0.9rem;
		color: #7f8c8d;
	}

	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}

	.status-dot.active {
		background: #28a745;
	}

	.status-dot.inactive {
		background: #6c757d;
	}

	.interface-info, .user-details {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.info-row, .detail-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
	}

	.label {
		color: #7f8c8d;
		font-weight: 500;
		min-width: 100px;
	}

	.value {
		color: #2c3e50;
		font-weight: 500;
		word-break: break-all;
		text-align: right;
	}

	.addresses {
		display: flex;
		flex-direction: column;
		gap: 4px;
		text-align: right;
	}

	.address {
		background: #f8f9fa;
		padding: 2px 8px;
		border-radius: 4px;
		font-size: 0.8rem;
		color: #495057;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 20px;
		margin-bottom: 30px;
	}

	.stat-card {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 12px;
		padding: 25px;
		display: flex;
		align-items: center;
		gap: 20px;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
		transition: transform 0.2s ease, box-shadow 0.2s ease;
	}

	.stat-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
	}

	.stat-icon {
		font-size: 2.5rem;
		opacity: 0.8;
	}

	.stat-content {
		flex: 1;
	}

	.stat-value {
		font-size: 1.8rem;
		font-weight: 700;
		color: #2c3e50;
		margin-bottom: 5px;
	}

	.stat-label {
		color: #7f8c8d;
		font-size: 0.9rem;
		font-weight: 500;
	}

	.processes-table {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 12px;
		overflow: hidden;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
		margin-bottom: 30px;
	}

	.table-header {
		display: grid;
		grid-template-columns: 80px 1fr 120px 120px 100px 120px;
		gap: 15px;
		padding: 15px 20px;
		background: #f8f9fa;
		font-weight: 600;
		color: #2c3e50;
		border-bottom: 1px solid #e0e0e0;
	}

	.table-row {
		display: grid;
		grid-template-columns: 80px 1fr 120px 120px 100px 120px;
		gap: 15px;
		padding: 12px 20px;
		border-bottom: 1px solid #f0f0f0;
		align-items: center;
		transition: background-color 0.2s ease;
	}

	.table-row:hover {
		background: #f8f9fa;
	}

	.table-row:last-child {
		border-bottom: none;
	}

	.col-pid {
		font-family: monospace;
		font-size: 0.9rem;
		color: #6c757d;
	}

	.col-name {
		font-weight: 500;
		color: #2c3e50;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.col-cpu, .col-memory {
		position: relative;
	}

	.progress-bar {
		position: relative;
		background: #e9ecef;
		border-radius: 10px;
		height: 20px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #28a745, #20c997);
		border-radius: 10px;
		transition: width 0.3s ease;
	}

	.progress-fill.memory {
		background: linear-gradient(90deg, #007bff, #6f42c1);
	}

	.progress-text {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		font-size: 0.8rem;
		font-weight: 600;
		color: #2c3e50;
	}

	.status-badge {
		padding: 4px 8px;
		border-radius: 12px;
		font-size: 0.8rem;
		font-weight: 600;
		text-align: center;
	}

	.status-badge.running {
		background: #d4edda;
		color: #155724;
	}

	.status-badge.sleeping {
		background: #d1ecf1;
		color: #0c5460;
	}

	.status-badge.stopped {
		background: #f8d7da;
		color: #721c24;
	}

	.status-badge.zombie {
		background: #fff3cd;
		color: #856404;
	}

	.status-badge.unknown {
		background: #e2e3e5;
		color: #383d41;
	}

	.col-user {
		font-size: 0.9rem;
		color: #6c757d;
	}

	.no-data {
		text-align: center;
		padding: 60px 20px;
		color: #7f8c8d;
	}

	.no-data-icon {
		font-size: 4rem;
		margin-bottom: 20px;
		opacity: 0.5;
	}

	.no-data p {
		margin: 0;
		font-size: 1.1rem;
	}

	.loading, .error {
		text-align: center;
		padding: 40px;
		color: #7f8c8d;
	}

	.error {
		color: #e74c3c;
	}

	@media (max-width: 768px) {
		.modal {
			width: 95%;
			max-height: 95vh;
		}
		
		.modal-header {
			padding: 15px 20px;
		}
		
		.modal-header h2 {
			font-size: 1.2rem;
		}
		
		.modal-body {
			padding: 20px;
		}
		
		.interfaces-grid, .users-grid {
			grid-template-columns: 1fr;
		}
		
		.stats-grid {
			grid-template-columns: 1fr;
		}
		
		.table-header, .table-row {
			grid-template-columns: 60px 1fr 80px 80px 80px 100px;
			gap: 10px;
			padding: 10px 15px;
		}
		
		.progress-text {
			font-size: 0.7rem;
		}
	}
</style>
