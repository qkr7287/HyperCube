<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import AdvancedMetricsDashboard from './AdvancedMetricsDashboard.svelte';

	export let project: {
		name: string;
		containers: any[];
		zone: string;
		color: string;
		stats: {
			total: number;
			running: number;
			stopped: number;
			paused: number;
			created: number;
		};
	};

	const dispatch = createEventDispatcher();

	let activeTab = 'overview';
	let loading = false;
	let error = '';
	let initialLoad = true;

	// 프로젝트 통계
	let projectStats = {
		avgCpu: 0,
		avgMemory: 0,
		avgNetworkRx: 0,
		avgNetworkTx: 0,
		avgDiskRead: 0,
		avgDiskWrite: 0,
		totalContainers: project.containers.length,
		runningContainers: project.stats.running,
		stoppedContainers: project.stats.stopped
	};

	// 컨테이너별 메트릭 데이터
	let containerMetrics: Map<string, any> = new Map();
	let refreshInterval: ReturnType<typeof setInterval>;
	
	// 컨테이너 타입 분포
	let containerTypes: { type: string; count: number; percentage: number }[] = [];
	
	// 실시간 평균 사용률
	let avgCpuUtilization = 0;
	let avgMemoryUtilization = 0;

	onMount(() => {
		startMetricsCollection();
		
		return () => {
			if (refreshInterval) {
				clearInterval(refreshInterval);
			}
		};
	});

	function closeModal() {
		dispatch('close');
	}

	async function fetchProjectMetrics() {
		// 초기 로딩이 아닌 경우에만 로딩 상태 표시하지 않음
		if (initialLoad) {
			loading = true;
		}
		error = '';
		
		try {
			const metricsPromises = project.containers
				.filter(container => container.state === 'running')
				.map(async (container) => {
					try {
						const response = await fetch(`/api/containers/${container.id}/metrics`);
						const result = await response.json();
						
						if (result.success) {
							return { containerId: container.id, data: result.data };
						}
						return null;
					} catch (err) {
						console.warn(`Failed to fetch metrics for container ${container.id}:`, err);
						return null;
					}
				});

			const results = await Promise.all(metricsPromises);
			const validMetrics = results.filter(result => result !== null);
			
			// 컨테이너별 메트릭 저장
			validMetrics.forEach(({ containerId, data }) => {
				containerMetrics.set(containerId, data);
			});

			// 프로젝트 전체 통계 계산
			calculateProjectStats();
			
			// 컨테이너 타입 분포 계산
			calculateContainerTypes();
			
			// 실시간 평균 사용률 계산
			calculateRealTimeUtilization();
			
		} catch (err) {
			error = '프로젝트 메트릭을 가져오는데 실패했습니다.';
			console.error('Error fetching project metrics:', err);
		} finally {
			if (initialLoad) {
				loading = false;
				initialLoad = false; // 초기 로딩 완료
			}
		}
	}

	function calculateContainerTypes() {
		const typeCount = new Map<string, number>();
		
		// 모든 컨테이너의 이미지에서 타입 추출
		project.containers.forEach(container => {
			const image = container.image || '';
			let type = 'unknown';
			
			// 이미지명에서 타입 추출 (예: nginx, postgres, redis 등)
			if (image.includes('nginx')) type = 'nginx';
			else if (image.includes('postgres') || image.includes('postgresql')) type = 'postgres';
			else if (image.includes('redis')) type = 'redis';
			else if (image.includes('mysql')) type = 'mysql';
			else if (image.includes('mongodb') || image.includes('mongo')) type = 'mongodb';
			else if (image.includes('node') || image.includes('nodejs')) type = 'nodejs';
			else if (image.includes('python') || image.includes('django') || image.includes('flask')) type = 'python';
			else if (image.includes('java') || image.includes('spring')) type = 'java';
			else if (image.includes('php')) type = 'php';
			else if (image.includes('ruby')) type = 'ruby';
			else if (image.includes('go')) type = 'go';
			else if (image.includes('react') || image.includes('vue') || image.includes('angular')) type = 'frontend';
			else if (image.includes('api') || image.includes('backend')) type = 'backend';
			else if (image.includes('db') || image.includes('database')) type = 'database';
			else if (image.includes('web')) type = 'web';
			else if (image.includes('app') || image.includes('service')) type = 'app';
			else {
				// 이미지명에서 첫 번째 부분 추출 (예: ubuntu -> ubuntu)
				const parts = image.split('/');
				const lastPart = parts[parts.length - 1];
				const baseImage = lastPart.split(':')[0];
				type = baseImage || 'unknown';
			}
			
			typeCount.set(type, (typeCount.get(type) || 0) + 1);
		});
		
		// 배열로 변환하고 정렬
		containerTypes = Array.from(typeCount.entries())
			.map(([type, count]) => ({
				type,
				count,
				percentage: Math.round((count / project.containers.length) * 100 * 10) / 10
			}))
			.sort((a, b) => b.count - a.count);
	}

	function calculateRealTimeUtilization() {
		const runningContainers = project.containers.filter(c => c.state === 'running');
		
		if (runningContainers.length === 0) {
			avgCpuUtilization = 0;
			avgMemoryUtilization = 0;
			return;
		}

		let totalCpu = 0;
		let totalMemory = 0;
		let validMetrics = 0;

		runningContainers.forEach(container => {
			const metrics = containerMetrics.get(container.id);
			if (metrics) {
				totalCpu += metrics.cpu?.usage || 0;
				totalMemory += metrics.memory?.percent || 0;
				validMetrics++;
			}
		});

		if (validMetrics > 0) {
			avgCpuUtilization = totalCpu / validMetrics;
			avgMemoryUtilization = totalMemory / validMetrics;
		} else {
			avgCpuUtilization = 0;
			avgMemoryUtilization = 0;
		}
	}

	function calculateProjectStats() {
		const runningContainers = project.containers.filter(c => c.state === 'running');
		
		if (runningContainers.length === 0) {
			projectStats = {
				avgCpu: 0,
				avgMemory: 0,
				avgNetworkRx: 0,
				avgNetworkTx: 0,
				avgDiskRead: 0,
				avgDiskWrite: 0,
				totalContainers: project.containers.length,
				runningContainers: 0,
				stoppedContainers: project.stats.stopped
			};
			return;
		}

		let totalCpu = 0;
		let totalMemory = 0;
		let totalNetworkRx = 0;
		let totalNetworkTx = 0;
		let totalDiskRead = 0;
		let totalDiskWrite = 0;
		let validMetricsCount = 0;

		runningContainers.forEach(container => {
			const metrics = containerMetrics.get(container.id);
			if (metrics) {
				totalCpu += metrics.cpu?.usage || 0;
				totalMemory += metrics.memory?.percent || 0;
				totalNetworkRx += metrics.network?.rx || 0;
				totalNetworkTx += metrics.network?.tx || 0;
				totalDiskRead += metrics.disk?.read || 0;
				totalDiskWrite += metrics.disk?.write || 0;
				validMetricsCount++;
			}
		});

		if (validMetricsCount > 0) {
			projectStats = {
				avgCpu: totalCpu / validMetricsCount,
				avgMemory: totalMemory / validMetricsCount,
				avgNetworkRx: totalNetworkRx / validMetricsCount,
				avgNetworkTx: totalNetworkTx / validMetricsCount,
				avgDiskRead: totalDiskRead / validMetricsCount,
				avgDiskWrite: totalDiskWrite / validMetricsCount,
				totalContainers: project.containers.length,
				runningContainers: project.stats.running,
				stoppedContainers: project.stats.stopped
			};
		}
	}

	function startMetricsCollection() {
		// 즉시 한 번 실행
		fetchProjectMetrics();
		
		// 5초마다 실행
		refreshInterval = setInterval(fetchProjectMetrics, 5000);
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
	}

	function getContainerStatusClass(state: string): string {
		switch (state) {
			case 'running': return 'running';
			case 'exited': return 'stopped';
			case 'paused': return 'paused';
			case 'created': return 'created';
			default: return 'unknown';
		}
	}

	function getContainerStatusText(state: string): string {
		switch (state) {
			case 'running': return '실행 중';
			case 'exited': return '중지됨';
			case 'paused': return '일시정지';
			case 'created': return '생성됨';
			default: return '알 수 없음';
		}
	}
</script>

<div class="modal-overlay" role="dialog" aria-modal="true" tabindex="-1" on:click={closeModal} on:keydown={(e) => e.key === 'Escape' && closeModal()}>
	<div class="modal" role="document" on:click|stopPropagation on:keydown|stopPropagation>
		<div class="modal-header">
			<h2>프로젝트 상세 정보: {project.name}</h2>
			<button class="close-btn" on:click={closeModal}>×</button>
		</div>

		<div class="modal-body">
			<div class="tabs">
				<button 
					class="tab {activeTab === 'overview' ? 'active' : ''}" 
					on:click={() => activeTab = 'overview'}
				>
					개요
				</button>
				<button 
					class="tab {activeTab === 'containers' ? 'active' : ''}" 
					on:click={() => activeTab = 'containers'}
				>
					컨테이너 ({project.containers.length})
				</button>
				<button 
					class="tab {activeTab === 'dashboard' ? 'active' : ''}" 
					on:click={() => activeTab = 'dashboard'}
				>
					대시보드
				</button>
			</div>

			{#if activeTab === 'overview'}
				<div class="overview-content">
					{#if loading}
						<div class="loading">
							<div class="loading-spinner"></div>
							<div>프로젝트 정보를 불려오는 중입니다...</div>
						</div>
					{:else if error}
						<div class="error">{error}</div>
					{:else}
						<div class="project-info">
							<div class="project-header">
								<div class="project-title">
									<div class="project-color" style="background-color: {project.color}"></div>
									<h3>{project.name}</h3>
								</div>
								<div class="project-zone">
									<span class="zone-label">Zone:</span>
									<span class="zone-value">{project.zone}</span>
								</div>
							</div>

							<div class="stats-grid">
								<div class="stat-card">
									<div class="stat-icon">📊</div>
									<div class="stat-content">
										<div class="stat-value">{projectStats.totalContainers}</div>
										<div class="stat-label">전체 컨테이너</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">🟢</div>
									<div class="stat-content">
										<div class="stat-value">{projectStats.runningContainers}</div>
										<div class="stat-label">실행 중</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">🔴</div>
									<div class="stat-content">
										<div class="stat-value">{projectStats.stoppedContainers}</div>
										<div class="stat-label">중지됨</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">⚡</div>
									<div class="stat-content">
										<div class="stat-value">{projectStats.avgCpu.toFixed(1)}%</div>
										<div class="stat-label">평균 CPU</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">💾</div>
									<div class="stat-content">
										<div class="stat-value">{projectStats.avgMemory.toFixed(1)}%</div>
										<div class="stat-label">평균 메모리</div>
									</div>
								</div>
								
								<div class="stat-card">
									<div class="stat-icon">🌐</div>
									<div class="stat-content">
										<div class="stat-value">{formatBytes(projectStats.avgNetworkRx)}</div>
										<div class="stat-label">평균 수신</div>
									</div>
								</div>
							</div>
						</div>
					{/if}
				</div>
			{:else if activeTab === 'containers'}
				<div class="containers-content">
					<div class="containers-grid">
						{#each project.containers as container}
							<div class="container-item">
								<div class="container-header">
									<div class="container-name">{container.names?.[0]?.replace('/', '') || container.shortId}</div>
									<div class="container-status">
										<span class="status-badge {getContainerStatusClass(container.state)}">
											{getContainerStatusText(container.state)}
										</span>
									</div>
								</div>
								
								<div class="container-info">
									<div class="info-item">
										<span class="info-label">ID:</span>
										<span class="info-value">{container.shortId}</span>
									</div>
									<div class="info-item">
										<span class="info-label">이미지:</span>
										<span class="info-value">{container.image}</span>
									</div>
									<div class="info-item">
										<span class="info-label">포트:</span>
										<span class="info-value">
											{#if container.ports && container.ports.length > 0}
												{container.ports.map((port: any) => `${port.PublicPort || 'N/A'}:${port.PrivatePort || 'N/A'}`).join(', ')}
											{:else}
												없음
											{/if}
										</span>
									</div>
								</div>

								{#if container.state === 'running' && containerMetrics.has(container.id)}
									<div class="container-metrics">
										<div class="metric-item">
											<span class="metric-label">CPU:</span>
											<span class="metric-value">{containerMetrics.get(container.id)?.cpu?.usage?.toFixed(1) || '0.0'}%</span>
										</div>
										<div class="metric-item">
											<span class="metric-label">메모리:</span>
											<span class="metric-value">{containerMetrics.get(container.id)?.memory?.percent?.toFixed(1) || '0.0'}%</span>
										</div>
									</div>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			{:else if activeTab === 'dashboard'}
				<div class="dashboard-content">
					{#if projectStats.runningContainers > 0}
						<AdvancedMetricsDashboard 
							containerId={project.containers.find(c => c.state === 'running')?.id || project.containers[0]?.id}
							containerTypes={containerTypes}
							avgCpuUtilization={avgCpuUtilization}
							avgMemoryUtilization={avgMemoryUtilization}
						/>
					{:else}
						<div class="dashboard-unavailable">
							<div class="unavailable-icon">📊</div>
							<h3>대시보드를 사용할 수 없습니다</h3>
							<p>실행 중인 컨테이너가 있을 때만 고급 대시보드를 확인할 수 있습니다.</p>
							<div class="container-status-info">
								실행 중인 컨테이너: <span class="status-badge">{projectStats.runningContainers}개</span>
							</div>
						</div>
					{/if}
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
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.tabs {
		display: flex;
		border-bottom: 1px solid #e0e0e0;
		background: #f8f9fa;
	}

	.tab {
		background: none;
		border: none;
		padding: 15px 25px;
		cursor: pointer;
		font-size: 1rem;
		color: #7f8c8d;
		border-bottom: 3px solid transparent;
		transition: all 0.2s ease;
	}

	.tab.active {
		color: #2c3e50;
		border-bottom-color: #3498db;
		background: white;
	}

	.tab:hover {
		color: #2c3e50;
	}

	.overview-content, .containers-content, .dashboard-content {
		flex: 1;
		overflow-y: auto;
		padding: 30px;
	}

	.project-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 30px;
		padding-bottom: 20px;
		border-bottom: 2px solid #e0e0e0;
	}

	.project-title {
		display: flex;
		align-items: center;
		gap: 15px;
	}

	.project-color {
		width: 20px;
		height: 20px;
		border-radius: 50%;
	}

	.project-title h3 {
		margin: 0;
		font-size: 2rem;
		color: #2c3e50;
		font-weight: 700;
	}

	.project-zone {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.zone-label {
		color: #7f8c8d;
		font-weight: 500;
	}

	.zone-value {
		background: #3498db;
		color: white;
		padding: 5px 15px;
		border-radius: 20px;
		font-weight: 600;
		font-size: 0.9rem;
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
		font-size: 2rem;
		font-weight: 700;
		color: #2c3e50;
		margin-bottom: 5px;
	}

	.stat-label {
		color: #7f8c8d;
		font-size: 0.9rem;
		font-weight: 500;
	}

	.containers-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
		gap: 20px;
	}

	.container-item {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 12px;
		padding: 20px;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
		transition: transform 0.2s ease, box-shadow 0.2s ease;
	}

	.container-item:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
	}

	.container-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 15px;
	}

	.container-name {
		font-size: 1.1rem;
		font-weight: 600;
		color: #2c3e50;
	}

	.container-status {
		display: flex;
		align-items: center;
	}

	.status-badge {
		padding: 4px 12px;
		border-radius: 20px;
		font-size: 0.8rem;
		font-weight: 600;
		text-transform: uppercase;
	}

	.status-badge.running {
		background: #d4edda;
		color: #155724;
	}

	.status-badge.stopped {
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

	.container-info {
		margin-bottom: 15px;
	}

	.info-item {
		display: flex;
		justify-content: space-between;
		margin-bottom: 8px;
	}

	.info-label {
		color: #7f8c8d;
		font-weight: 500;
	}

	.info-value {
		color: #2c3e50;
		font-weight: 500;
		word-break: break-all;
	}

	.container-metrics {
		background: #f8f9fa;
		border-radius: 8px;
		padding: 15px;
		display: flex;
		gap: 20px;
	}

	.metric-item {
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.metric-label {
		font-size: 0.8rem;
		color: #7f8c8d;
		margin-bottom: 5px;
	}

	.metric-value {
		font-size: 1.2rem;
		font-weight: 700;
		color: #2c3e50;
	}

	.dashboard-unavailable {
		text-align: center;
		padding: 60px 20px;
		color: #7f8c8d;
	}

	.dashboard-unavailable .unavailable-icon {
		font-size: 4rem;
		margin-bottom: 20px;
		opacity: 0.5;
	}

	/* 대시보드 그리드 */
	.dashboard-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 2rem;
		margin-top: 1rem;
	}

	.container-types-section,
	.project-stats-section {
		background: rgba(255, 255, 255, 0.05);
		border-radius: 12px;
		padding: 1.5rem;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.container-types-section h3,
	.project-stats-section h3 {
		margin: 0 0 1rem 0;
		color: #ecf0f1;
		font-size: 1.1rem;
		font-weight: 600;
	}

	.container-types-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.container-type-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem;
		background: rgba(255, 255, 255, 0.03);
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.05);
	}

	.type-info {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.type-name {
		font-weight: 600;
		color: #ecf0f1;
		text-transform: capitalize;
	}

	.type-count {
		background: rgba(52, 152, 219, 0.2);
		color: #3498db;
		padding: 0.25rem 0.5rem;
		border-radius: 4px;
		font-size: 0.8rem;
		font-weight: 500;
	}

	.type-percentage {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 120px;
	}

	.percentage-bar {
		flex: 1;
		height: 6px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 3px;
		overflow: hidden;
	}

	.percentage-fill {
		height: 100%;
		background: linear-gradient(90deg, #3498db, #2ecc71);
		border-radius: 3px;
		transition: width 0.3s ease;
	}

	.percentage-text {
		font-size: 0.8rem;
		color: #bdc3c7;
		font-weight: 500;
		min-width: 35px;
		text-align: right;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
	}

	.stat-item {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 1rem;
		background: rgba(255, 255, 255, 0.03);
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.05);
	}

	.stat-label {
		font-size: 0.8rem;
		color: #95a5a6;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 700;
		color: #ecf0f1;
	}

	.stat-value.running {
		color: #2ecc71;
	}

	.stat-value.stopped {
		color: #e74c3c;
	}

	.dashboard-unavailable h3 {
		margin: 0 0 10px 0;
		color: #2c3e50;
		font-size: 1.5rem;
	}

	.dashboard-unavailable p {
		margin: 0 0 20px 0;
		font-size: 1rem;
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
		
		.overview-content, .containers-content, .dashboard-content {
			padding: 20px;
		}
		
		.stats-grid {
			grid-template-columns: 1fr;
		}
		
		.containers-grid {
			grid-template-columns: 1fr;
		}
		
		.project-header {
			flex-direction: column;
			align-items: flex-start;
			gap: 15px;
		}
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
</style>
