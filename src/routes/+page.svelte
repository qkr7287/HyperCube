<script lang="ts">
	import { onMount } from 'svelte';
	import ContainerCard from '$lib/components/ContainerCard.svelte';
	import ContainerDetails from '$lib/components/ContainerDetails.svelte';
	import ProjectDetails from '$lib/components/ProjectDetails.svelte';
	import ServerDetails from '$lib/components/ServerDetails.svelte';

	interface Container {
		id: string;
		shortId: string;
		names: string[];
		image: string;
		imageId: string;
		command: string;
		created: number;
		state: string;
		status: string;
		ports: any[];
		labels: any;
		sizeRw: number;
		sizeRootFs: number;
		hostConfig: any;
		networkSettings: any;
		mounts: any[];
	}

	interface Project {
		name: string;
		containers: Container[];
		stats: {
			total: number;
			running: number;
			stopped: number;
			paused: number;
			created: number;
		};
		zone: string;
		color: string;
	}

	interface SystemInfo {
		hostname: string;
		os: string;
		cpu: {
			cores: number;
			model: string;
			usage: number;
		};
		memory: {
			total: string;
			used: string;
			free: string;
			usage: number;
		};
		disk: {
			total: string;
			used: string;
			free: string;
			usage: number;
		};
		network: {
			connections: number;
			interfaces: string[];
		};
		logins: {
			total: number;
			active: number;
		};
		processes: {
			total: number;
			running: number;
		};
		docker: {
			version: string;
			containers: number;
			images: number;
			driver: string;
		};
	}

	let containers: Container[] = [];
	let projects: Project[] = [];
	let systemInfo: SystemInfo | null = null;
	let loading = true;
	let error = '';
	let selectedContainer: Container | null = null;
	let showContainerDetails = false;
	let selectedProject: any = null;
	let showProjectDetails = false;
	let selectedServerDetail: 'network' | 'logins' | 'processes' | null = null;
	let showServerDetails = false;
	let refreshInterval: ReturnType<typeof setInterval>;
	let lastUpdate = new Date();
	let viewMode = 'isometric'; // 'isometric', 'grid', 'list'
	let serverAddress = '';

	// 전체 통계 데이터
	let stats = {
		total: 0,
		running: 0,
		stopped: 0,
		paused: 0,
		created: 0
	};

	// 프로젝트 색상 팔레트
	const projectColors = [
		'#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6',
		'#1abc9c', '#e67e22', '#34495e', '#f1c40f', '#e91e63'
	];

	// 존/지역 목록
	let zones: string[] = [];

	async function fetchContainers() {
		try {
			loading = true;
			const response = await fetch('/api/containers');
			const result = await response.json();
			
			if (result.success) {
				containers = result.data;
				groupContainersByProject();
				updateStats();
				error = '';
				lastUpdate = new Date();
			} else {
				error = result.error;
			}
		} catch (err) {
			error = '컨테이너 목록을 가져오는데 실패했습니다.';
			console.error('Error fetching containers:', err);
		} finally {
			loading = false;
		}
	}

	async function fetchSystemInfo() {
		try {
			const response = await fetch('/api/system');
			const result = await response.json();
			
			if (result.success) {
				systemInfo = result.data;
			}
		} catch (err) {
			console.error('Error fetching system info:', err);
		}
	}

	function groupContainersByProject() {
		const projectMap = new Map<string, Container[]>();
		
		// 기본 프로젝트 (라벨이 없는 컨테이너들)
		const defaultProject = 'default';
		projectMap.set(defaultProject, []);
		
		containers.forEach(container => {
			// 프로젝트 라벨 찾기
			let projectName = defaultProject;
			let zone = 'default-zone';
			
			if (container.labels) {
				const rawProjectName = container.labels['com.docker.compose.project'] || 
									  container.labels['project'] || 
									  container.labels['app'] || 
									  container.labels['service'] ||
									  defaultProject;
				
				// 공통 접두사로 그룹화 (예: agaptpisys-backend, agaptpisys-frontend -> agaptpisys)
				projectName = extractProjectPrefix(rawProjectName);
				
				zone = container.labels['zone'] || 
					  container.labels['region'] || 
					  container.labels['environment'] ||
					  'default-zone';
			}
			
			if (!projectMap.has(projectName)) {
				projectMap.set(projectName, []);
			}
			projectMap.get(projectName)!.push(container);
		});

		// 프로젝트별 통계 계산 및 색상 할당
		projects = Array.from(projectMap.entries()).map(([name, containers], index) => ({
			name,
			containers,
			zone: containers[0]?.labels?.zone || containers[0]?.labels?.region || 'default-zone',
			color: projectColors[index % projectColors.length],
			stats: {
				total: containers.length,
				running: containers.filter(c => c.state === 'running').length,
				stopped: containers.filter(c => c.state === 'exited').length,
				paused: containers.filter(c => c.state === 'paused').length,
				created: containers.filter(c => c.state === 'created').length
			}
		})).sort((a, b) => {
			if (a.name === 'default') return 1;
			if (b.name === 'default') return -1;
			return a.name.localeCompare(b.name);
		});

		// 존 목록 업데이트
		zones = [...new Set(projects.map(p => p.zone))];
		
		// 디버그 정보 출력
		console.log('프로젝트별 그룹화 결과:', projects.map(p => ({
			name: p.name,
			containers: p.containers.length,
			containerNames: p.containers.map(c => c.names?.[0]?.replace('/', '') || c.shortId),
			stats: p.stats
		})));
	}

	function extractProjectPrefix(projectName: string): string {
		// 하이픈이나 언더스코어로 구분된 경우 첫 번째 부분을 반환
		// 예: agaptpisys-backend -> agaptpisys, agaptpisys_frontend -> agaptpisys
		const parts = projectName.split(/[-_]/);
		if (parts.length > 1) {
			// 공통 접두사가 2글자 이상인 경우에만 적용
			if (parts[0].length >= 2) {
				return parts[0];
			}
		}
		return projectName;
	}

	function removeProjectPrefix(containerName: string, projectPrefix: string): string {
		// 컨테이너 이름에서 프로젝트 접두사 제거
		// 예: agaptpisys-backend -> backend, agaptpisys_frontend -> frontend
		if (containerName.startsWith(projectPrefix + '-') || containerName.startsWith(projectPrefix + '_')) {
			return containerName.substring(projectPrefix.length + 1);
		}
		return containerName;
	}

	function getDisplayName(container: Container): string {
		const containerName = container.names?.[0]?.replace('/', '') || container.shortId;
		
		// 컨테이너가 속한 프로젝트 찾기
		const project = projects.find(p => p.containers.some(c => c.id === container.id));
		if (project && project.name !== 'default') {
			return removeProjectPrefix(containerName, project.name);
		}
		
		return containerName;
	}

	function updateStats() {
		stats = {
			total: containers.length,
			running: containers.filter(c => c.state === 'running').length,
			stopped: containers.filter(c => c.state === 'exited').length,
			paused: containers.filter(c => c.state === 'paused').length,
			created: containers.filter(c => c.state === 'created').length
		};
	}

	function selectContainer(container: Container) {
		// 이전 팝업 완전히 닫기
		selectedContainer = null;
		showContainerDetails = false;
		
		// 다음 프레임에서 새 컨테이너 선택
		requestAnimationFrame(() => {
			selectedContainer = container;
			showContainerDetails = true;
		});
	}

	function closeDetails() {
		selectedContainer = null;
		showContainerDetails = false;
	}

	function selectProject(project: any) {
		selectedProject = project;
		showProjectDetails = true;
	}

	function closeProjectDetails() {
		showProjectDetails = false;
		selectedProject = null;
	}

	function selectServerDetail(type: 'network' | 'logins' | 'processes') {
		selectedServerDetail = type;
		showServerDetails = true;
	}

	function closeServerDetails() {
		showServerDetails = false;
		selectedServerDetail = null;
	}

	async function getServerAddress() {
		try {
			// 서버의 실제 IP 주소 가져오기
			const response = await fetch('/api/server/ip');
			const data = await response.json();
			serverAddress = data.ip || 'localhost';
		} catch (error) {
			console.error('서버 IP 가져오기 실패:', error);
			// 폴백: localhost 사용
			serverAddress = 'localhost';
		}
	}

	function getStateColor(state: string): string {
		switch (state) {
			case 'running': return '#28a745';
			case 'exited': return '#dc3545';
			case 'paused': return '#ffc107';
			case 'created': return '#17a2b8';
			default: return '#6c757d';
		}
	}

	function getProjectStats() {
		return {
			total: containers.length,
			running: containers.filter(c => c.state === 'running').length,
			stopped: containers.filter(c => c.state === 'exited').length,
			paused: containers.filter(c => c.state === 'paused').length,
			created: containers.filter(c => c.state === 'created').length
		};
	}

	function getStatusLevel(): 'critical' | 'warning' | 'info' {
		const stats = getProjectStats();
		if (stats.stopped > stats.running) return 'critical';
		if (stats.paused > 0 || stats.created > 0) return 'warning';
		return 'info';
	}

	onMount(() => {
		fetchContainers();
		fetchSystemInfo();
		getServerAddress();
		
		// 5초마다 자동 새로고침
		refreshInterval = setInterval(() => {
			fetchContainers();
			fetchSystemInfo();
		}, 5000);
		
		return () => {
			if (refreshInterval) {
				clearInterval(refreshInterval);
			}
		};
	});
</script>

<svelte:head>
	<title>AGICS Container Monitor Tool</title>
</svelte:head>

<main class="dashboard">
	<!-- 상단 필터 및 컨트롤 -->
	<header class="dashboard-header">
		<div class="header-top">
			<div class="title-section">
				<h1>🐳 AGICS Container Monitor Tool</h1>
				<p class="subtitle">고급 인프라 모니터링 시스템 - Docker 컨테이너, 서버 리소스, 네트워크 상태를 실시간으로 추적하고 관리합니다</p>
				{#if serverAddress}
					<span class="server-address">
						🌐 {serverAddress}
					</span>
				{:else}
					<p class="server-address">🌐 Loading...</p>
				{/if}
			</div>
			<div class="header-controls">
				<div class="last-update">
					Last Update: {lastUpdate.toLocaleTimeString('ko-KR')}
				</div>
				<button class="refresh-btn" on:click={fetchContainers} disabled={loading} title="새로고침">
					{#if loading}
						<div class="spinner"></div>
					{:else}
						🔄
					{/if}
				</button>
			</div>
		</div>
		
		<div class="view-controls">
			<button class="view-btn {viewMode === 'isometric' ? 'active' : ''}" on:click={() => viewMode = 'isometric'}>
				🏗️ Group
			</button>
			<button class="view-btn {viewMode === 'grid' ? 'active' : ''}" on:click={() => viewMode = 'grid'}>
				🔲 Grid
			</button>
			<button class="view-btn {viewMode === 'list' ? 'active' : ''}" on:click={() => viewMode = 'list'}>
				📋 List
			</button>
		</div>
	</header>

	<!-- 시스템 정보 카드 -->
	{#if systemInfo}
		<section class="system-info-section">
			<div class="system-cards">
				<div class="system-card">
					<div class="card-icon">🖥️</div>
					<div class="card-content">
						<div class="card-label">Hostname</div>
						<div class="card-value">{systemInfo.hostname}</div>
					</div>
				</div>
				
				<div class="system-card">
					<div class="card-icon">💻</div>
					<div class="card-content">
						<div class="card-label">OS</div>
						<div class="card-value">{systemInfo.os}</div>
					</div>
				</div>
				
				<div class="system-card">
					<div class="card-icon">⚡</div>
					<div class="card-content">
						<div class="card-label">CPU Cores</div>
						<div class="card-value">{systemInfo.cpu.cores}</div>
					</div>
				</div>
				
				<div class="system-card">
					<div class="card-icon">🧠</div>
					<div class="card-content">
						<div class="card-label">Memory</div>
						<div class="card-value">{systemInfo.memory.total}</div>
					</div>
				</div>
				
				<div class="system-card">
					<div class="card-icon">💾</div>
					<div class="card-content">
						<div class="card-label">Disk Total</div>
						<div class="card-value">{systemInfo.disk.total}</div>
					</div>
				</div>
				
				<div 
					class="system-card clickable" 
					on:click={() => selectServerDetail('network')}
					on:keydown={(e) => e.key === 'Enter' && selectServerDetail('network')}
					role="button"
					tabindex="0"
					title="네트워크 상세보기"
				>
					<div class="card-icon">🌐</div>
					<div class="card-content">
						<div class="card-label">Network</div>
						<div class="card-value">{systemInfo.network.connections}</div>
						<div class="card-subtitle">연결 수</div>
					</div>
					<div class="card-arrow">→</div>
				</div>
				
				<div 
					class="system-card clickable" 
					on:click={() => selectServerDetail('logins')}
					on:keydown={(e) => e.key === 'Enter' && selectServerDetail('logins')}
					role="button"
					tabindex="0"
					title="로그인 상세보기"
				>
					<div class="card-icon">🔐</div>
					<div class="card-content">
						<div class="card-label">Logins</div>
						<div class="card-value">{systemInfo.logins?.active || 0}</div>
					</div>
					<div class="card-arrow">→</div>
				</div>
				
				<div 
					class="system-card clickable" 
					on:click={() => selectServerDetail('processes')}
					on:keydown={(e) => e.key === 'Enter' && selectServerDetail('processes')}
					role="button"
					tabindex="0"
					title="프로세스 상세보기"
				>
					<div class="card-icon">⚙️</div>
					<div class="card-content">
						<div class="card-label">Process Total</div>
						<div class="card-value">{systemInfo.processes?.total || 0}</div>
					</div>
					<div class="card-arrow">→</div>
				</div>
			</div>
		</section>
	{/if}

	<!-- 상태 알림 카드 -->
	<section class="status-alerts">
		<div class="alert-card critical">
			<div class="alert-icon">🚨</div>
			<div class="alert-content">
				<div class="alert-label">CRITICAL</div>
				<div class="alert-value">{getProjectStats().stopped}</div>
			</div>
		</div>
		
		<div class="alert-card warning">
			<div class="alert-icon">⚠️</div>
			<div class="alert-content">
				<div class="alert-label">WARNING</div>
				<div class="alert-value">{getProjectStats().paused + getProjectStats().created}</div>
			</div>
		</div>
		
		<div class="alert-card info">
			<div class="alert-icon">ℹ️</div>
			<div class="alert-content">
				<div class="alert-label">INFO</div>
				<div class="alert-value">{getProjectStats().running}</div>
			</div>
		</div>
	</section>

	<!-- 컨테이너 섹션 -->
	<section class="containers-section">
		<div class="section-header">
			<h2>컨테이너 상태</h2>
		</div>

		{#if error}
			<div class="error-banner">
				<p>❌ {error}</p>
			</div>
		{/if}

		{#if loading && containers.length === 0}
			<div class="loading-state">
				<div class="loading-spinner"></div>
				<p>Loading containers...</p>
			</div>
		{:else if containers.length === 0}
			<div class="empty-state">
				<div class="empty-icon">📦</div>
				<h3>No Containers</h3>
				<p>No containers found.</p>
			</div>
		{:else}
			{#if viewMode === 'isometric'}
				<!-- 3D 아이소메트릭 뷰 -->
				<div class="isometric-container">
					{#each projects as project (project.name)}
						<div class="project-zone" style="border-color: {project.color}">
							<div class="zone-header">
								<div class="zone-label" style="background-color: {project.color}">
									{project.name === 'default' ? 'Default' : project.name}
								</div>
								<button 
									class="project-details-btn"
									on:click={() => selectProject(project)}
									title="프로젝트 상세보기"
								>
									📊
								</button>
							</div>
							<div class="zone-stats">
								{project.stats.running} running, {project.stats.stopped} stopped
							</div>
							<div class="containers-3d">
								{#each project.containers as container (container.id)}
									<div 
										class="container-cube {container.state}" 
										style="background-color: {getStateColor(container.state)}"
										on:click={() => selectContainer(container)}
										on:keydown={(e) => e.key === 'Enter' && selectContainer(container)}
										role="button"
										tabindex="0"
										title="{getDisplayName(container)}"
									>
										<div class="cube-face front">
											<div class="cube-content">
												<div class="container-icon">
													{container.state === 'running' ? '🟢' : 
													 container.state === 'exited' ? '🔴' : 
													 container.state === 'paused' ? '🟡' : '🔵'}
												</div>
												<div class="container-name">
													{getDisplayName(container)}
												</div>
											</div>
										</div>
										<div class="cube-face back"></div>
										<div class="cube-face right"></div>
										<div class="cube-face left"></div>
										<div class="cube-face top"></div>
										<div class="cube-face bottom"></div>
									</div>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{:else if viewMode === 'grid'}
				<!-- 그리드 뷰 -->
				<div class="containers-grid">
					{#each containers as container (container.id)}
						<div 
							class="container-cell {container.state}" 
							style="background-color: {getStateColor(container.state)}"
							on:click={() => selectContainer(container)}
							on:keydown={(e) => e.key === 'Enter' && selectContainer(container)}
							role="button"
							tabindex="0"
							title="{getDisplayName(container)}"
						>
							<div class="cell-content">
								<div class="container-name">
									{getDisplayName(container)}
								</div>
								<div class="container-status">
									{container.state === 'running' ? '🟢' : 
									 container.state === 'exited' ? '🔴' : 
									 container.state === 'paused' ? '🟡' : '🔵'}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<!-- 리스트 뷰 (테이블 형태) -->
				<div class="table-view">
					<table class="containers-table">
						<thead>
							<tr>
								<th>상태</th>
								<th>컨테이너명</th>
								<th>이미지</th>
								<th>프로젝트</th>
								<th>포트</th>
								<th>생성일</th>
								<th>동작</th>
							</tr>
						</thead>
						<tbody>
							{#each projects as project}
								{#each project.containers as container}
									<tr class="container-row" on:click={() => selectContainer(container)}>
										<td>
											<span class="status-indicator {container.state}"></span>
											<span class="status-text">{container.state}</span>
										</td>
										<td class="container-name">{getDisplayName(container)}</td>
										<td class="container-image">{container.image}</td>
										<td class="project-name">{project.name}</td>
										<td class="container-ports">
											{#if container.ports && container.ports.length > 0}
												{#each container.ports as port}
													<span class="port-badge">{port.privatePort}:{port.publicPort}</span>
												{/each}
											{:else}
												<span class="no-ports">-</span>
											{/if}
										</td>
										<td class="created-date">{new Date(container.created * 1000).toLocaleDateString('ko-KR')}</td>
										<td>
											<button class="action-btn" on:click|stopPropagation={() => selectContainer(container)}>
												상세보기
											</button>
										</td>
									</tr>
								{/each}
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		{/if}
	</section>

	{#if showContainerDetails && selectedContainer}
		<ContainerDetails 
			container={selectedContainer} 
			on:close={closeDetails}
		/>
	{/if}
</main>

<style>
	.dashboard {
		min-height: 100vh;
		background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
		background-attachment: fixed;
		padding: 20px;
		color: #ffffff;
	}

	.dashboard-header {
		background: rgba(255, 255, 255, 0.1);
		backdrop-filter: blur(20px);
		border-radius: 20px;
		padding: 30px;
		margin-bottom: 30px;
		border: 1px solid rgba(255, 255, 255, 0.2);
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
	}

	.header-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
	}

	.title-section h1 {
		margin: 0 0 10px 0;
		font-size: 2.5rem;
		font-weight: 700;
		background: linear-gradient(45deg, #00d4ff, #0099cc);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.subtitle {
		margin: 0;
		color: #b0b0b0;
		font-size: 1.1rem;
	}

	.header-controls {
		display: flex;
		align-items: center;
		gap: 20px;
	}

	.last-update {
		color: #b0b0b0;
		font-size: 0.9rem;
	}

	.view-controls {
		display: flex;
		gap: 10px;
		justify-content: center;
		margin-top: 20px;
	}

	.view-btn {
		padding: 10px 16px;
		border: 2px solid rgba(255, 255, 255, 0.2);
		background: transparent;
		border-radius: 10px;
		cursor: pointer;
		font-size: 0.9rem;
		font-weight: 500;
		color: #b0b0b0;
		transition: all 0.3s ease;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.view-btn.active {
		background: linear-gradient(45deg, #00d4ff, #0099cc);
		border-color: #00d4ff;
		color: #ffffff;
		box-shadow: 0 4px 15px rgba(0, 212, 255, 0.3);
	}

	.view-btn:hover:not(.active) {
		border-color: #00d4ff;
		color: #00d4ff;
	}

	.btn {
		padding: 12px 24px;
		border: none;
		border-radius: 10px;
		cursor: pointer;
		font-size: 14px;
		font-weight: 600;
		transition: all 0.3s ease;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.btn-primary {
		background: linear-gradient(45deg, #00d4ff, #0099cc);
		color: white;
		box-shadow: 0 4px 15px rgba(0, 212, 255, 0.3);
	}

	.btn-primary:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 6px 20px rgba(0, 212, 255, 0.4);
	}

	.btn-primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
		transform: none;
	}

	.system-info-section {
		margin-bottom: 30px;
	}

	.system-cards {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 20px;
	}

	.system-card {
		background: rgba(255, 255, 255, 0.1);
		backdrop-filter: blur(20px);
		border-radius: 15px;
		padding: 25px;
		display: flex;
		align-items: center;
		gap: 20px;
		border: 1px solid rgba(255, 255, 255, 0.2);
		transition: all 0.3s ease;
	}

	.system-card:hover {
		transform: translateY(-5px);
		box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
	}

	.card-icon {
		font-size: 2.5rem;
		opacity: 0.8;
	}

	.card-content {
		flex: 1;
	}

	.card-label {
		font-size: 0.9rem;
		color: #b0b0b0;
		margin-bottom: 5px;
		font-weight: 500;
	}

	.card-value {
		font-size: 1.8rem;
		font-weight: 700;
		color: #ffffff;
		line-height: 1;
	}

	.status-alerts {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 20px;
		margin-bottom: 30px;
	}

	.alert-card {
		border-radius: 15px;
		padding: 25px;
		display: flex;
		align-items: center;
		gap: 20px;
		transition: all 0.3s ease;
	}

	.alert-card.critical {
		background: linear-gradient(135deg, #e74c3c, #c0392b);
		box-shadow: 0 8px 32px rgba(231, 76, 60, 0.3);
	}

	.alert-card.warning {
		background: linear-gradient(135deg, #f39c12, #e67e22);
		box-shadow: 0 8px 32px rgba(243, 156, 18, 0.3);
	}

	.alert-card.info {
		background: linear-gradient(135deg, #3498db, #2980b9);
		box-shadow: 0 8px 32px rgba(52, 152, 219, 0.3);
	}

	.alert-card:hover {
		transform: translateY(-5px);
	}

	.alert-icon {
		font-size: 2.5rem;
		opacity: 0.9;
	}

	.alert-content {
		flex: 1;
	}

	.alert-label {
		font-size: 0.9rem;
		color: rgba(255, 255, 255, 0.8);
		margin-bottom: 5px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 1px;
	}

	.alert-value {
		font-size: 2.5rem;
		font-weight: 700;
		color: #ffffff;
		line-height: 1;
	}

	.containers-section {
		background: rgba(255, 255, 255, 0.1);
		backdrop-filter: blur(20px);
		border-radius: 20px;
		padding: 30px;
		border: 1px solid rgba(255, 255, 255, 0.2);
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
	}

	.section-header {
		margin-bottom: 30px;
	}

	.section-header h2 {
		margin: 0;
		color: #ffffff;
		font-size: 1.8rem;
		font-weight: 600;
	}

	.isometric-container {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
		gap: 30px;
		margin-bottom: 30px;
	}

	.project-zone {
		background: rgba(255, 255, 255, 0.05);
		border: 2px dashed rgba(255, 255, 255, 0.3);
		border-radius: 15px;
		padding: 20px;
		position: relative;
		transition: all 0.3s ease;
	}

	.project-zone:hover {
		background: rgba(255, 255, 255, 0.1);
		transform: translateY(-5px);
	}

	.zone-label {
		position: absolute;
		top: -15px;
		left: 20px;
		padding: 8px 16px;
		border-radius: 20px;
		color: white;
		font-weight: 600;
		font-size: 0.9rem;
		text-transform: uppercase;
		letter-spacing: 1px;
	}

	.zone-stats {
		color: #b0b0b0;
		font-size: 0.8rem;
		margin-bottom: 20px;
		margin-top: 10px;
	}

	.containers-3d {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
		gap: 15px;
	}

	.container-cube {
		position: relative;
		width: 60px;
		height: 60px;
		cursor: pointer;
		transform-style: preserve-3d;
		transition: all 0.3s ease;
	}

	.container-cube:hover {
		transform: rotateX(-10deg) rotateY(10deg) scale(1.1);
	}

	.cube-face {
		position: absolute;
		width: 60px;
		height: 60px;
		border: 2px solid rgba(255, 255, 255, 0.3);
	}

	.cube-face.front {
		transform: rotateY(0deg) translateZ(30px);
		background: linear-gradient(135deg, currentColor, rgba(255, 255, 255, 0.1));
	}

	.cube-face.back {
		transform: rotateY(180deg) translateZ(30px);
		background: linear-gradient(135deg, currentColor, rgba(0, 0, 0, 0.3));
	}

	.cube-face.right {
		transform: rotateY(90deg) translateZ(30px);
		background: linear-gradient(135deg, currentColor, rgba(0, 0, 0, 0.2));
	}

	.cube-face.left {
		transform: rotateY(-90deg) translateZ(30px);
		background: linear-gradient(135deg, currentColor, rgba(0, 0, 0, 0.2));
	}

	.cube-face.top {
		transform: rotateX(90deg) translateZ(30px);
		background: linear-gradient(135deg, currentColor, rgba(255, 255, 255, 0.2));
	}

	.cube-face.bottom {
		transform: rotateX(-90deg) translateZ(30px);
		background: linear-gradient(135deg, currentColor, rgba(0, 0, 0, 0.4));
	}

	.cube-content {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		text-align: center;
		color: white;
		z-index: 10;
	}

	.container-icon {
		font-size: 1.2rem;
		margin-bottom: 2px;
	}

	.container-name {
		font-size: 0.6rem;
		font-weight: 600;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 50px;
	}

	.containers-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
		gap: 8px;
		margin-bottom: 30px;
	}

	.containers-list {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
		gap: 20px;
		margin-bottom: 30px;
	}

	.container-cell {
		aspect-ratio: 1;
		border-radius: 6px;
		cursor: pointer;
		position: relative;
		transition: all 0.2s ease;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
	}

	.container-cell:hover {
		transform: scale(1.1);
		z-index: 10;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
	}

	.container-cell.running {
		background: linear-gradient(135deg, #28a745, #20c997);
	}

	.container-cell.exited {
		background: linear-gradient(135deg, #dc3545, #e74c3c);
	}

	.container-cell.paused {
		background: linear-gradient(135deg, #ffc107, #fd7e14);
	}

	.container-cell.created {
		background: linear-gradient(135deg, #17a2b8, #6f42c1);
	}

	.cell-content {
		text-align: center;
		color: white;
		font-weight: 600;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
	}

	.container-name {
		font-size: 0.7rem;
		line-height: 1;
		margin-bottom: 2px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 50px;
	}

	.container-status {
		font-size: 0.8rem;
	}

	.error-banner {
		background: #e74c3c;
		color: white;
		padding: 15px 20px;
		border-radius: 8px;
		margin-bottom: 20px;
		text-align: center;
	}

	.loading-state {
		text-align: center;
		padding: 60px 20px;
	}

	.loading-spinner {
		width: 40px;
		height: 40px;
		border: 4px solid rgba(255, 255, 255, 0.3);
		border-top: 4px solid #00d4ff;
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin: 0 auto 20px;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	.empty-state {
		text-align: center;
		padding: 60px 20px;
		color: #b0b0b0;
	}

	.empty-icon {
		font-size: 4rem;
		margin-bottom: 20px;
		opacity: 0.5;
	}

	.empty-state h3 {
		margin: 0 0 10px 0;
		color: #ffffff;
		font-size: 1.5rem;
	}

	.empty-state p {
		margin: 0;
		font-size: 1rem;
	}

	@media (max-width: 768px) {
		.dashboard {
			padding: 10px;
		}

		.header-top {
			flex-direction: column;
			text-align: center;
			gap: 20px;
		}

		.title-section h1 {
			font-size: 2rem;
		}

		.view-controls {
			justify-content: center;
		}

		.system-cards {
			grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
			gap: 15px;
		}

		.status-alerts {
			grid-template-columns: 1fr;
		}

		.isometric-container {
			grid-template-columns: 1fr;
		}

		.containers-grid {
			grid-template-columns: repeat(auto-fill, minmax(50px, 1fr));
			gap: 6px;
		}

		.containers-list {
			grid-template-columns: 1fr;
		}
	}

	.zone-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10px;
	}

	.project-details-btn {
		background: rgba(255, 255, 255, 0.2);
		border: 1px solid rgba(255, 255, 255, 0.3);
		border-radius: 6px;
		padding: 6px 10px;
		cursor: pointer;
		font-size: 1rem;
		color: white;
		transition: all 0.2s ease;
		backdrop-filter: blur(10px);
	}

	.project-details-btn:hover {
		background: rgba(255, 255, 255, 0.3);
		transform: scale(1.05);
	}

	.system-card.clickable {
		cursor: pointer;
		transition: all 0.2s ease;
		position: relative;
		overflow: hidden;
	}

	.system-card.clickable:hover {
		transform: translateY(-2px);
		box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
	}

	.system-card.clickable:hover .card-icon {
		transform: scale(1.1);
	}

	.system-card.clickable:hover .card-arrow {
		opacity: 1;
		transform: translateX(0);
	}

	.card-arrow {
		position: absolute;
		right: 15px;
		top: 50%;
		transform: translateY(-50%) translateX(10px);
		font-size: 1.2rem;
		opacity: 0;
		transition: all 0.2s ease;
		font-weight: bold;
	}

	.card-subtitle {
		font-size: 0.8rem;
		color: #7f8c8d;
		margin-top: 2px;
		opacity: 0.8;
	}

	.server-address {
		margin: 8px 0 0 0;
		color: #3498db;
		font-size: 0.9rem;
		font-weight: 500;
		background: rgba(52, 152, 219, 0.1);
		padding: 4px 12px;
		border-radius: 12px;
		display: inline-block;
		border: 1px solid rgba(52, 152, 219, 0.2);
		text-decoration: none;
		transition: all 0.2s ease;
		cursor: pointer;
	}

	.server-address:hover {
		background: rgba(52, 152, 219, 0.2);
		border-color: rgba(52, 152, 219, 0.4);
		transform: translateY(-1px);
		box-shadow: 0 2px 8px rgba(52, 152, 219, 0.2);
	}

	.refresh-btn {
		background: #3498db;
		border: none;
		border-radius: 8px;
		padding: 8px 12px;
		color: white;
		font-size: 1.2rem;
		cursor: pointer;
		transition: all 0.2s ease;
		display: flex;
		align-items: center;
		justify-content: center;
		min-width: 40px;
		height: 40px;
	}

	.refresh-btn:hover:not(:disabled) {
		background: #2980b9;
		transform: translateY(-1px);
		box-shadow: 0 2px 8px rgba(52, 152, 219, 0.3);
	}

	.refresh-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.spinner {
		width: 16px;
		height: 16px;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top: 2px solid white;
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	/* 테이블 뷰 스타일 */
	.table-view {
		background: rgba(255, 255, 255, 0.05);
		border-radius: 12px;
		overflow: hidden;
		backdrop-filter: blur(10px);
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.containers-table {
		width: 100%;
		border-collapse: collapse;
		background: transparent;
	}

	.containers-table thead {
		background: rgba(52, 152, 219, 0.2);
	}

	.containers-table th {
		padding: 16px 12px;
		text-align: left;
		font-weight: 600;
		color: #ecf0f1;
		border-bottom: 2px solid rgba(52, 152, 219, 0.3);
		font-size: 0.9rem;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.containers-table td {
		padding: 12px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.05);
		color: #bdc3c7;
		vertical-align: middle;
	}

	.container-row {
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.container-row:hover {
		background: rgba(52, 152, 219, 0.1);
		transform: translateX(2px);
	}

	.status-indicator {
		display: inline-block;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		margin-right: 8px;
	}

	.status-indicator.running {
		background: #28a745;
		box-shadow: 0 0 6px rgba(40, 167, 69, 0.5);
	}

	.status-indicator.exited {
		background: #dc3545;
		box-shadow: 0 0 6px rgba(220, 53, 69, 0.5);
	}

	.status-indicator.paused {
		background: #ffc107;
		box-shadow: 0 0 6px rgba(255, 193, 7, 0.5);
	}

	.status-text {
		font-weight: 500;
		text-transform: capitalize;
	}

	.container-name {
		font-weight: 600;
		color: #ecf0f1;
	}

	.container-image {
		font-family: 'Courier New', monospace;
		font-size: 0.85rem;
		color: #95a5a6;
	}

	.project-name {
		background: rgba(52, 152, 219, 0.2);
		padding: 4px 8px;
		border-radius: 6px;
		font-size: 0.8rem;
		font-weight: 500;
		color: #3498db;
		display: inline-block;
	}

	.port-badge {
		background: rgba(46, 204, 113, 0.2);
		color: #2ecc71;
		padding: 2px 6px;
		border-radius: 4px;
		font-size: 0.75rem;
		font-family: 'Courier New', monospace;
		margin-right: 4px;
		display: inline-block;
	}

	.no-ports {
		color: #7f8c8d;
		font-style: italic;
	}

	.created-date {
		font-size: 0.85rem;
		color: #95a5a6;
	}

	.action-btn {
		background: #3498db;
		border: none;
		color: white;
		padding: 6px 12px;
		border-radius: 6px;
		font-size: 0.8rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.action-btn:hover {
		background: #2980b9;
		transform: translateY(-1px);
		box-shadow: 0 2px 8px rgba(52, 152, 219, 0.3);
	}
</style>


<!-- 프로젝트 상세보기 모달 -->
{#if showProjectDetails && selectedProject}
	<ProjectDetails 
		project={selectedProject} 
		on:close={closeProjectDetails}
	/>
{/if}

<!-- 서버 상세보기 모달 -->
{#if showServerDetails && selectedServerDetail}
	<ServerDetails 
		detailType={selectedServerDetail}
		on:close={closeServerDetails}
	/>
{/if}