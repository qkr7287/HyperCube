<script lang="ts">
	import { createEventDispatcher, onMount, onDestroy } from 'svelte';
	import ContainerMetricsChart from './ContainerMetricsChart.svelte';

	export let container: {
		id: string;
		shortId: string;
		names: string[];
		image: string;
		state: string;
		status: string;
		ports: any[];
		created: number;
		labels: any;
	};

	const dispatch = createEventDispatcher();

	let details: any = null;
	let logs: string[] = [];
	let loading = false; // 초기값을 false로 설정
	let error = '';
	let activeTab = 'info';
	let initialLoad = true; // 초기 로딩 플래그

	async function fetchDetails() {
		try {
			const response = await fetch(`/api/containers/${container.id}`);
			const result = await response.json();
			
			if (result.success) {
				details = result.data;
				error = '';
			} else {
				error = result.error;
			}
		} catch (err) {
			error = '컨테이너 상세 정보를 가져오는데 실패했습니다.';
			console.error('Error fetching container details:', err);
		}
	}

	async function fetchLogs() {
		try {
			const response = await fetch(`/api/containers/${container.id}/logs?tail=100`);
			const result = await response.json();
			
			if (result.success) {
				logs = result.data.logs;
			} else {
				console.warn('로그 가져오기 실패:', result.error);
				logs = ['로그를 불러올 수 없습니다: ' + result.error];
			}
		} catch (err) {
			console.error('Error fetching logs:', err);
			logs = ['로그를 불러오는 중 오류가 발생했습니다.'];
		}
	}

	async function refreshLogs() {
		// 로그 새로고침 시에는 로딩 상태 표시하지 않음
		await fetchLogs();
	}

	async function controlContainer(action: string) {
		try {
			const response = await fetch(`/api/containers/${container.id}/control`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ action })
			});
			
			const result = await response.json();
			
			if (result.success) {
				// 컨테이너 상태가 변경되었으므로 부모 컴포넌트에 알림
				dispatch('refresh');
				// 상세 정보도 다시 가져오기
				await fetchDetails();
			} else {
				error = result.error;
			}
		} catch (err) {
			error = `컨테이너 제어에 실패했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}`;
		}
	}

	function closeModal() {
		dispatch('close');
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 Bytes';
		const k = 1024;
		const sizes = ['Bytes', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
	}

	function formatDate(timestamp: number): string {
		return new Date(timestamp * 1000).toLocaleString('ko-KR');
	}

	onMount(() => {
		// 컴포넌트 마운트 시 데이터 로드
		console.log('ContainerDetails onMount:', container.id);
		loadData();
	});

	onDestroy(() => {
		// 컴포넌트 언마운트 시 상태 초기화
		console.log('ContainerDetails onDestroy:', container.id);
		loading = false;
		// details = null; // 언마운트 시에는 초기화하지 않음
		logs = [];
		error = '';
	});

	async function loadData() {
		console.log('로딩 시작:', container.id);
		
		// 초기 로딩이 아닌 경우에만 로딩 상태 표시하지 않음
		if (initialLoad) {
			loading = true;
		}
		// details = null; // 기존 데이터 유지
		logs = [];
		error = '';
		// activeTab = 'info'; // 탭 상태 유지
		
		try {
			// 정보와 로그를 모두 가져온 후 표시
			const [detailsResult, logsResult] = await Promise.allSettled([
				fetchDetails(), 
				fetchLogs()
			]);
			
			// 정보 로딩 결과 확인
			if (detailsResult.status === 'rejected') {
				console.error('정보 로딩 실패:', detailsResult.reason);
				error = '컨테이너 정보를 가져오는데 실패했습니다.';
			}
			
			// 로그 로딩 결과 확인
			if (logsResult.status === 'rejected') {
				console.warn('로그 로딩 실패:', logsResult.reason);
				logs = ['로그를 불러올 수 없습니다.'];
			}
			
			console.log('정보와 로그 로딩 완료:', container.id);
		} catch (err) {
			console.error('로딩 오류:', err);
			error = '데이터를 불러오는 중 오류가 발생했습니다.';
		} finally {
			loading = false;
			initialLoad = false; // 초기 로딩 완료
			console.log('로딩 상태 해제:', container.id);
		}
	}
</script>

<div class="modal-overlay" role="dialog" aria-modal="true" tabindex="-1" on:click={closeModal} on:keydown={(e) => e.key === 'Escape' && closeModal()}>
	<div class="modal" role="document" on:click|stopPropagation on:keydown|stopPropagation>
		<div class="modal-header">
			<h2>컨테이너 상세 정보</h2>
			<button class="close-btn" on:click={closeModal}>×</button>
		</div>

		<div class="modal-body">
			<div class="tabs">
				<button 
					class="tab {activeTab === 'info' ? 'active' : ''}" 
					on:click={() => activeTab = 'info'}
				>
					정보
				</button>
				<button 
					class="tab {activeTab === 'metrics' ? 'active' : ''}" 
					on:click={() => activeTab = 'metrics'}
				>
					메트릭
				</button>
				<button 
					class="tab {activeTab === 'logs' ? 'active' : ''}" 
					on:click={() => activeTab = 'logs'}
				>
					로그
				</button>
			</div>

			{#if activeTab === 'info'}
				<div class="info-content">
					{#if loading}
						<div class="loading">
							<div class="loading-spinner"></div>
							<div>컨테이너 정보를 불러오는 중...</div>
						</div>
					{:else if error}
						<div class="error">{error}</div>
					{:else}
						<div class="info-grid">
							<div class="info-section">
								<h3>기본 정보</h3>
								<div class="info-row">
									<span class="label">이름:</span>
									<span class="value">{container.names?.[0]?.replace('/', '') || container.shortId}</span>
								</div>
								<div class="info-row">
									<span class="label">ID:</span>
									<span class="value">{container.id}</span>
								</div>
								<div class="info-row">
									<span class="label">이미지:</span>
									<span class="value">{container.image}</span>
								</div>
								<div class="info-row">
									<span class="label">상태:</span>
									<span class="value">{container.status}</span>
								</div>
								<div class="info-row">
									<span class="label">생성일:</span>
									<span class="value">{formatDate(container.created)}</span>
								</div>
							</div>

							{#if details && details.inspect && details.inspect.Config}
								<div class="info-section">
									<h3>설정</h3>
									<div class="info-row">
										<span class="label">명령어:</span>
										<span class="value">{details.inspect.Config.Cmd?.join(' ') || 'N/A'}</span>
									</div>
									<div class="info-row">
										<span class="label">작업 디렉토리:</span>
										<span class="value">{details.inspect.Config.WorkingDir || 'N/A'}</span>
									</div>
									<div class="info-row">
										<span class="label">환경 변수:</span>
										<div class="env-vars">
											{#each details.inspect.Config.Env?.slice(0, 5) || [] as env}
												<span class="env-var">{env}</span>
											{/each}
											{#if details.inspect.Config.Env?.length > 5}
												<span class="env-var">... {details.inspect.Config.Env.length - 5}개 더</span>
											{/if}
										</div>
									</div>
								</div>
							{/if}

							{#if details && details.stats}
								<div class="info-section">
									<h3>리소스 사용량</h3>
									<div class="info-row">
										<span class="label">CPU 사용률:</span>
										<span class="value">
											{details.stats.cpu_stats ? 
												((details.stats.cpu_stats.cpu_usage.total_usage / details.stats.cpu_stats.system_cpu_usage) * 100).toFixed(2) + '%' : 
												'N/A'
											}
										</span>
									</div>
									<div class="info-row">
										<span class="label">메모리 사용량:</span>
										<span class="value">
											{details.stats.memory_stats ? 
												formatBytes(details.stats.memory_stats.usage) : 
												'N/A'
											}
										</span>
									</div>
									<div class="info-row">
										<span class="label">네트워크:</span>
										<span class="value">
											{details.stats.networks ? 
												Object.keys(details.stats.networks).join(', ') : 
												'N/A'
											}
										</span>
									</div>
								</div>
							{/if}
						</div>

						<div class="actions">
							<button 
								class="btn btn-success" 
								on:click={() => controlContainer('start')}
								disabled={container.state === 'running'}
							>
								시작
							</button>
							<button 
								class="btn btn-warning" 
								on:click={() => controlContainer('stop')}
								disabled={container.state !== 'running'}
							>
								중지
							</button>
							<button 
								class="btn btn-info" 
								on:click={() => controlContainer('restart')}
								disabled={container.state !== 'running'}
							>
								재시작
							</button>
							<button 
								class="btn btn-danger" 
								on:click={() => controlContainer('remove')}
							>
								삭제
							</button>
						</div>
					{/if}
				</div>
			{:else if activeTab === 'metrics'}
				<div class="metrics-content">
					{#if container.state === 'running'}
						<div class="metrics-grid">
							<ContainerMetricsChart containerId={container.id} type="cpu" />
							<ContainerMetricsChart containerId={container.id} type="memory" />
							<ContainerMetricsChart containerId={container.id} type="network" />
							<ContainerMetricsChart containerId={container.id} type="disk" />
						</div>
					{:else}
						<div class="metrics-unavailable">
							<div class="unavailable-icon">📊</div>
							<h3>메트릭을 사용할 수 없습니다</h3>
							<p>컨테이너가 실행 중일 때만 실시간 메트릭을 확인할 수 있습니다.</p>
							<div class="container-status-info">
								현재 상태: <span class="status-badge {container.state}">{container.status}</span>
							</div>
						</div>
					{/if}
				</div>
			{:else if activeTab === 'logs'}
				<div class="logs-content">
					<div class="logs-header">
						<button class="btn btn-primary" on:click={refreshLogs}>
							로그 새로고침
						</button>
					</div>
					<div class="logs-container">
						{#each logs as log}
							<div class="log-line">{log}</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 20px;
	}

	.modal {
		background: white;
		border-radius: 8px;
		width: 90%;
		max-width: 800px;
		max-height: 90vh;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 20px;
		border-bottom: 1px solid #e0e0e0;
		background: #f8f9fa;
	}

	.modal-header h2 {
		margin: 0;
		color: #2c3e50;
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 24px;
		cursor: pointer;
		color: #7f8c8d;
		padding: 0;
		width: 30px;
		height: 30px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.close-btn:hover {
		color: #e74c3c;
	}

	.modal-body {
		flex: 1;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.tabs {
		display: flex;
		border-bottom: 1px solid #e0e0e0;
	}

	.tab {
		padding: 15px 20px;
		background: none;
		border: none;
		cursor: pointer;
		font-size: 16px;
		color: #7f8c8d;
		border-bottom: 2px solid transparent;
		transition: all 0.2s;
	}

	.tab.active {
		color: #3498db;
		border-bottom-color: #3498db;
	}

	.tab:hover {
		color: #2c3e50;
	}

	.info-content, .logs-content, .metrics-content {
		flex: 1;
		overflow-y: auto;
		padding: 20px;
	}

	.info-grid {
		display: grid;
		gap: 20px;
	}

	.info-section {
		background: #f8f9fa;
		padding: 15px;
		border-radius: 5px;
	}

	.info-section h3 {
		margin: 0 0 15px 0;
		color: #2c3e50;
		font-size: 1.1rem;
	}

	.info-row {
		display: flex;
		margin-bottom: 10px;
		align-items: flex-start;
	}

	.info-row:last-child {
		margin-bottom: 0;
	}

	.label {
		font-weight: 600;
		color: #34495e;
		min-width: 120px;
		font-size: 0.9rem;
	}

	.value {
		flex: 1;
		color: #2c3e50;
		font-size: 0.9rem;
		word-break: break-word;
	}

	.env-vars {
		display: flex;
		flex-direction: column;
		gap: 4px;
		flex: 1;
	}

	.env-var {
		background: #ecf0f1;
		padding: 4px 8px;
		border-radius: 3px;
		font-size: 0.8rem;
		font-family: monospace;
	}

	.actions {
		display: flex;
		gap: 10px;
		margin-top: 20px;
		padding-top: 20px;
		border-top: 1px solid #e0e0e0;
		flex-wrap: wrap;
	}

	.btn {
		padding: 8px 16px;
		border: none;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.9rem;
		font-weight: 500;
		transition: all 0.2s;
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-primary {
		background: #3498db;
		color: white;
	}

	.btn-success {
		background: #27ae60;
		color: white;
	}

	.btn-warning {
		background: #f39c12;
		color: white;
	}

	.btn-info {
		background: #17a2b8;
		color: white;
	}

	.btn-danger {
		background: #e74c3c;
		color: white;
	}

	.btn:hover:not(:disabled) {
		opacity: 0.9;
		transform: translateY(-1px);
	}

	.logs-header {
		margin-bottom: 15px;
	}

	.logs-container {
		background: #2c3e50;
		color: #ecf0f1;
		padding: 15px;
		border-radius: 5px;
		font-family: monospace;
		font-size: 0.85rem;
		max-height: 400px;
		overflow-y: auto;
	}

	.log-line {
		margin-bottom: 2px;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
		gap: 20px;
	}

	.metrics-unavailable {
		text-align: center;
		padding: 60px 20px;
		color: #7f8c8d;
	}

	.unavailable-icon {
		font-size: 4rem;
		margin-bottom: 20px;
		opacity: 0.5;
	}

	.metrics-unavailable h3 {
		margin: 0 0 10px 0;
		color: #2c3e50;
		font-size: 1.5rem;
	}

	.metrics-unavailable p {
		margin: 0 0 20px 0;
		font-size: 1rem;
	}

	.container-status-info {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		font-size: 0.9rem;
	}

	.status-badge {
		padding: 4px 12px;
		border-radius: 20px;
		font-size: 0.8rem;
		font-weight: 500;
		text-transform: uppercase;
	}

	.status-badge.running {
		background: #d4edda;
		color: #155724;
	}

	.status-badge.exited {
		background: #f8d7da;
		color: #721c24;
	}

	.status-badge.paused {
		background: #fff3cd;
		color: #856404;
	}

	.status-badge.created {
		background: #d1ecf1;
		color: #0c5460;
	}


	.loading, .error {
		text-align: center;
		padding: 40px;
		color: #7f8c8d;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 15px;
	}
	

	.loading-spinner {
		width: 40px;
		height: 40px;
		border: 4px solid #f3f3f3;
		border-top: 4px solid #3498db;
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	.error {
		color: #e74c3c;
	}


	@media (max-width: 768px) {
		.modal {
			width: 95%;
			margin: 10px;
		}

		.actions {
			flex-direction: column;
		}

		.btn {
			width: 100%;
		}
	}
</style>
