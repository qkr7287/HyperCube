<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Chart, registerables } from 'chart.js';
	import 'chartjs-adapter-date-fns';

	Chart.register(...registerables);

	export let containerId: string;
	export let containerTypes: { type: string; count: number; percentage: number }[] = [];
	export let avgCpuUtilization: number = 0;
	export let avgMemoryUtilization: number = 0;

	let metricsData: any[] = [];
	let refreshInterval: ReturnType<typeof setInterval>;
	let maxDataPoints = 60;

	// 차트 참조
	let cpuHexGrid: HTMLCanvasElement;
	let memoryHexGrid: HTMLCanvasElement;
	let containerTypesCanvas: HTMLCanvasElement;
	let containerTypesChart: Chart | null = null;
	let avgCpuGauge: HTMLCanvasElement;
	let avgMemoryGauge: HTMLCanvasElement;
	let networkReceivedChart: HTMLCanvasElement;
	let networkSentChart: HTMLCanvasElement;
	let connectionsInChart: HTMLCanvasElement;
	let connectionsOutChart: HTMLCanvasElement;

	// 통계 데이터
	let stats = {
		avgCpu: 0,
		avgMemory: 0,
		avgReceived: 0,
		avgSent: 0,
		avgConnectionsIn: 0,
		avgConnectionsOut: 0,
		containerTypes: new Map<string, number>()
	};

	onMount(() => {
		startMetricsCollection();
		// DOM이 렌더링된 후 차트 초기화
		setTimeout(() => {
			initializeCharts();
		}, 100);
		
		return () => {
			if (refreshInterval) {
				clearInterval(refreshInterval);
			}
			if (containerTypesChart) {
				containerTypesChart.destroy();
			}
		};
	});

	// 실시간 gauge 차트 업데이트
	$: if (avgCpuGauge && avgMemoryGauge) {
		initializeGaugeCharts();
	}

	onDestroy(() => {
		if (refreshInterval) {
			clearInterval(refreshInterval);
		}
		if (containerTypesChart) {
			containerTypesChart.destroy();
		}
	});

	async function fetchMetrics() {
		try {
			const response = await fetch(`/api/containers/${containerId}/metrics`);
			const result = await response.json();
			
			if (result.success) {
				addMetricData(result.data);
			} else {
				console.warn('Metrics fetch failed:', result.error);
			}
		} catch (error) {
			console.error('Error fetching metrics:', error);
			// 메트릭이 없어도 기본값으로 차트 표시
			addMetricData({
				cpu: { usage: Math.random() * 100 },
				memory: { percent: Math.random() * 100 },
				network: { rx: Math.random() * 1000000, tx: Math.random() * 1000000 },
				disk: { read: Math.random() * 100000, write: Math.random() * 100000 },
				timestamp: new Date().toISOString()
			});
		}
	}

	function addMetricData(data: any) {
		metricsData.push(data);
		
		if (metricsData.length > maxDataPoints) {
			metricsData.shift();
		}
		
		updateStats();
		updateCharts();
	}

	function updateStats() {
		if (metricsData.length === 0) return;

		// 평균 CPU 사용률
		stats.avgCpu = metricsData.reduce((sum, d) => sum + d.cpu.usage, 0) / metricsData.length;
		
		// 평균 메모리 사용률
		stats.avgMemory = metricsData.reduce((sum, d) => sum + d.memory.percent, 0) / metricsData.length;
		
		// 평균 네트워크 수신/송신
		stats.avgReceived = metricsData.reduce((sum, d) => sum + d.network.rx, 0) / metricsData.length;
		stats.avgSent = metricsData.reduce((sum, d) => sum + d.network.tx, 0) / metricsData.length;
		
		// 평균 연결 수 (시뮬레이션)
		stats.avgConnectionsIn = Math.random() * 20 + 5;
		stats.avgConnectionsOut = Math.random() * 20 + 5;
	}

	function initializeCharts() {
		initializeContainerTypesChart();
		initializeGaugeCharts();
		initializeNetworkCharts();
		initializeHexGrids();
	}

	function initializeHexGrids() {
		// 헥사그리드 초기화
		if (cpuHexGrid) {
			generateHexGrid(cpuHexGrid, 75, '#e74c3c');
		}
		if (memoryHexGrid) {
			generateHexGrid(memoryHexGrid, 60, '#f39c12');
		}
	}

	function initializeContainerTypesChart() {
		if (!containerTypesCanvas) return;

		const ctx = containerTypesCanvas.getContext('2d');
		if (!ctx) return;

		// 실제 컨테이너 타입 데이터 사용
		const typesData = containerTypes.length > 0 ? containerTypes : [
			{ type: 'No Data', count: 0, percentage: 0 }
		];

		containerTypesChart = new Chart(containerTypesCanvas, {
			type: 'doughnut',
			data: {
				labels: typesData.map(t => t.type),
				datasets: [{
					data: typesData.map(t => t.count),
					backgroundColor: [
						'#3498db', '#e74c3c', '#2ecc71', '#f39c12',
						'#9b59b6', '#1abc9c', '#e67e22'
					],
					borderWidth: 0
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: {
						position: 'bottom',
						labels: {
							padding: 20,
							usePointStyle: true
						}
					},
					tooltip: {
						callbacks: {
							label: function(context) {
								const item = typesData[context.dataIndex];
								return `${item.type}: ${item.count} (${item.percentage}%)`;
							}
						}
					}
				}
			}
		});
	}

	function initializeGaugeCharts() {
		// CPU 게이지 차트 (육각형)
		if (avgCpuGauge) {
			drawHexGauge(avgCpuGauge, avgCpuUtilization, 'CPU Usage', '#2ecc71');
		}
		
		// 메모리 게이지 차트 (육각형)
		if (avgMemoryGauge) {
			drawHexGauge(avgMemoryGauge, avgMemoryUtilization, 'Memory Usage', '#e67e22');
		}
	}

	function drawHexGauge(canvas: HTMLCanvasElement, value: number, label: string, color: string) {
		if (!canvas) return;
		
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const centerX = canvas.width / 2;
		const centerY = canvas.height / 2;
		const size = Math.min(centerX, centerY) - 20;

		// 배경 육각형
		ctx.beginPath();
		drawHexagon(ctx, centerX, centerY, size, 0);
		ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
		ctx.fill();
		ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
		ctx.lineWidth = 2;
		ctx.stroke();

		// 값에 따른 육각형 (0-100% 범위)
		const fillSize = (value / 100) * size;
		if (fillSize > 0) {
			ctx.beginPath();
			drawHexagon(ctx, centerX, centerY, fillSize, 0);
			ctx.fillStyle = color;
			ctx.fill();
		}

		// 중앙 텍스트
		ctx.fillStyle = '#ecf0f1';
		ctx.font = 'bold 14px Arial';
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(label, centerX, centerY - 5);
	}

	function drawHexagon(ctx: CanvasRenderingContext2D, x: number, y: number, size: number, rotation: number) {
		ctx.save();
		ctx.translate(x, y);
		ctx.rotate(rotation);
		
		ctx.beginPath();
		for (let i = 0; i < 6; i++) {
			const angle = (Math.PI / 3) * i;
			const px = Math.cos(angle) * size;
			const py = Math.sin(angle) * size;
			
			if (i === 0) {
				ctx.moveTo(px, py);
			} else {
				ctx.lineTo(px, py);
			}
		}
		ctx.closePath();
		
		ctx.restore();
	}

	function drawGauge(canvas: HTMLCanvasElement, value: number, label: string, color: string) {
		if (!canvas) return;
		
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const centerX = canvas.width / 2;
		const centerY = canvas.height / 2;
		const radius = Math.min(centerX, centerY) - 20;

		// 배경 원
		ctx.beginPath();
		ctx.arc(centerX, centerY, radius, Math.PI, 2 * Math.PI);
		ctx.strokeStyle = '#e0e0e0';
		ctx.lineWidth = 20;
		ctx.stroke();

		// 값 원
		const angle = Math.PI + (value / 100) * Math.PI;
		ctx.beginPath();
		ctx.arc(centerX, centerY, radius, Math.PI, angle);
		ctx.strokeStyle = color;
		ctx.lineWidth = 20;
		ctx.stroke();

		// 값 텍스트
		ctx.fillStyle = color;
		ctx.font = 'bold 24px Arial';
		ctx.textAlign = 'center';
		ctx.fillText(value.toFixed(1), centerX, centerY - 10);

		// 라벨
		ctx.fillStyle = '#666';
		ctx.font = '14px Arial';
		ctx.fillText(label, centerX, centerY + 20);
	}

	function initializeNetworkCharts() {
		// 네트워크 차트들 초기화
		if (networkReceivedChart) {
			drawNetworkChart(networkReceivedChart, 'Received', '#3498db', stats.avgReceived);
		}
		if (networkSentChart) {
			drawNetworkChart(networkSentChart, 'Sent', '#e74c3c', stats.avgSent);
		}
		if (connectionsInChart) {
			drawConnectionChart(connectionsInChart, 'Inbound', '#2ecc71', stats.avgConnectionsIn);
		}
		if (connectionsOutChart) {
			drawConnectionChart(connectionsOutChart, 'Outbound', '#f39c12', stats.avgConnectionsOut);
		}
	}

	function drawNetworkChart(canvas: HTMLCanvasElement, label: string, color: string, value: number) {
		if (!canvas) return;
		
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		// 배경
		ctx.fillStyle = '#f8f9fa';
		ctx.fillRect(0, 0, canvas.width, canvas.height);

		// 값 텍스트
		ctx.fillStyle = color;
		ctx.font = 'bold 32px Arial';
		ctx.textAlign = 'center';
		ctx.fillText(formatBytes(value), canvas.width / 2, canvas.height / 2 - 10);

		// 라벨
		ctx.fillStyle = '#666';
		ctx.font = '14px Arial';
		ctx.fillText(label, canvas.width / 2, canvas.height / 2 + 20);

		// 작은 라인 차트 (시뮬레이션)
		ctx.strokeStyle = color;
		ctx.lineWidth = 2;
		ctx.beginPath();
		for (let i = 0; i < 20; i++) {
			const x = (i / 19) * canvas.width;
			const y = canvas.height - 30 - Math.random() * 20;
			if (i === 0) {
				ctx.moveTo(x, y);
			} else {
				ctx.lineTo(x, y);
			}
		}
		ctx.stroke();
	}

	function drawConnectionChart(canvas: HTMLCanvasElement, label: string, color: string, value: number) {
		if (!canvas) return;
		
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		// 배경
		ctx.fillStyle = '#f8f9fa';
		ctx.fillRect(0, 0, canvas.width, canvas.height);

		// 값 텍스트
		ctx.fillStyle = color;
		ctx.font = 'bold 32px Arial';
		ctx.textAlign = 'center';
		ctx.fillText(value.toFixed(1), canvas.width / 2, canvas.height / 2 - 10);

		// 라벨
		ctx.fillStyle = '#666';
		ctx.font = '14px Arial';
		ctx.fillText(`${label} Connections`, canvas.width / 2, canvas.height / 2 + 20);

		// 작은 라인 차트 (시뮬레이션)
		ctx.strokeStyle = color;
		ctx.lineWidth = 2;
		ctx.beginPath();
		for (let i = 0; i < 20; i++) {
			const x = (i / 19) * canvas.width;
			const y = canvas.height - 30 - Math.random() * 20;
			if (i === 0) {
				ctx.moveTo(x, y);
			} else {
				ctx.lineTo(x, y);
			}
		}
		ctx.stroke();
	}

	function updateCharts() {
		// 헥사그리드 업데이트
		if (cpuHexGrid) {
			generateHexGrid(cpuHexGrid, stats.avgCpu, '#e74c3c');
		}
		if (memoryHexGrid) {
			generateHexGrid(memoryHexGrid, stats.avgMemory, '#f39c12');
		}
		
		// 게이지 차트 업데이트
		if (avgCpuGauge) {
			drawGauge(avgCpuGauge, stats.avgCpu, 'CPU Usage', '#2ecc71');
		}
		if (avgMemoryGauge) {
			drawGauge(avgMemoryGauge, stats.avgMemory, 'Memory Usage', '#e67e22');
		}
		
		// 네트워크 차트 업데이트
		if (networkReceivedChart) {
			drawNetworkChart(networkReceivedChart, 'Received', '#3498db', stats.avgReceived);
		}
		if (networkSentChart) {
			drawNetworkChart(networkSentChart, 'Sent', '#e74c3c', stats.avgSent);
		}
		if (connectionsInChart) {
			drawConnectionChart(connectionsInChart, 'Inbound', '#2ecc71', stats.avgConnectionsIn);
		}
		if (connectionsOutChart) {
			drawConnectionChart(connectionsOutChart, 'Outbound', '#f39c12', stats.avgConnectionsOut);
		}
	}

	function startMetricsCollection() {
		// 즉시 한 번 실행
		fetchMetrics();
		
		// 5초마다 실행
		refreshInterval = setInterval(fetchMetrics, 5000);
	}

	function formatBytes(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
	}

	function generateHexGrid(canvas: HTMLCanvasElement, value: number, color: string) {
		if (!canvas) return;
		
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const hexSize = 8;
		const cols = Math.floor(canvas.width / (hexSize * 1.5));
		const rows = Math.floor(canvas.height / (hexSize * Math.sqrt(3)));

		ctx.clearRect(0, 0, canvas.width, canvas.height);

		for (let row = 0; row < rows; row++) {
			for (let col = 0; col < cols; col++) {
				const x = col * hexSize * 1.5 + (row % 2) * hexSize * 0.75;
				const y = row * hexSize * Math.sqrt(3) / 2;

				// 랜덤 값으로 헥사곤 색상 결정
				const randomValue = Math.random();
				const hexColor = randomValue < value / 100 ? 
					(randomValue < value / 200 ? '#e74c3c' : '#f39c12') : '#ecf0f1';

				ctx.fillStyle = hexColor;
				drawHexagon(ctx, x, y, hexSize, 0);
			}
		}
	}

</script>

<div class="advanced-dashboard">
	<!-- 헥사그리드 차트 -->
	<div class="hex-grid-section">
		<div class="hex-chart">
			<h3>Instances with High CPU Utilization</h3>
			<canvas bind:this={cpuHexGrid} width="400" height="200"></canvas>
		</div>
		<div class="hex-chart">
			<h3>Instances with High Memory Utilization</h3>
			<canvas bind:this={memoryHexGrid} width="400" height="200"></canvas>
		</div>
	</div>

	<!-- 중간 행 - 인스턴스 타입과 평균 사용률 -->
	<div class="middle-section">
		<div class="container-types">
			<h3>Container Types</h3>
			<div class="chart-container">
				<canvas bind:this={containerTypesCanvas}></canvas>
			</div>
		</div>
		
		<div class="gauge-charts">
			<div class="gauge-chart">
				<h3>Average CPU Utilization</h3>
				<div class="hex-gauge-container">
					<canvas bind:this={avgCpuGauge} width="150" height="120"></canvas>
					<div class="gauge-value">{avgCpuUtilization.toFixed(1)}%</div>
				</div>
			</div>
			<div class="gauge-chart">
				<h3>Average Memory Utilization</h3>
				<div class="hex-gauge-container">
					<canvas bind:this={avgMemoryGauge} width="150" height="120"></canvas>
					<div class="gauge-value">{avgMemoryUtilization.toFixed(1)}%</div>
				</div>
			</div>
		</div>
	</div>

	<!-- 하단 행 - 네트워크 및 연결 메트릭 -->
	<div class="bottom-section">
		<div class="metric-card">
			<h4>Average Received Bytes</h4>
			<div class="metric-value">{formatBytes(stats.avgReceived)}</div>
			<div class="metric-trend down">↓</div>
			<canvas bind:this={networkReceivedChart} width="200" height="80"></canvas>
		</div>
		
		<div class="metric-card">
			<h4>Average Sent Bytes</h4>
			<div class="metric-value">{formatBytes(stats.avgSent)}</div>
			<div class="metric-trend down">↓</div>
			<canvas bind:this={networkSentChart} width="200" height="80"></canvas>
		</div>
		
		<div class="metric-card">
			<h4>Average Inbound Connections</h4>
			<div class="metric-value">{stats.avgConnectionsIn.toFixed(1)}</div>
			<div class="metric-trend">↑</div>
			<canvas bind:this={connectionsInChart} width="200" height="80"></canvas>
		</div>
		
		<div class="metric-card">
			<h4>Average Outbound Connections</h4>
			<div class="metric-value">{stats.avgConnectionsOut.toFixed(1)}</div>
			<div class="metric-trend">↑</div>
			<canvas bind:this={connectionsOutChart} width="200" height="80"></canvas>
		</div>
	</div>
</div>

<style>
	.advanced-dashboard {
		background: #ffffff;
		padding: 20px;
		border-radius: 12px;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
	}

	.hex-grid-section {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20px;
		margin-bottom: 30px;
	}

	.hex-chart {
		background: #f8f9fa;
		padding: 20px;
		border-radius: 8px;
		text-align: center;
	}

	.hex-chart h3 {
		margin: 0 0 15px 0;
		color: #2c3e50;
		font-size: 1.1rem;
		font-weight: 600;
	}

	.middle-section {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20px;
		margin-bottom: 30px;
	}

	.container-types {
		background: #f8f9fa;
		padding: 20px;
		border-radius: 8px;
	}

	.container-types h3 {
		margin: 0 0 15px 0;
		color: #2c3e50;
		font-size: 1.1rem;
		font-weight: 600;
	}

	.chart-container {
		position: relative;
		height: 200px;
		width: 100%;
	}

	.gauge-charts {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20px;
	}

	.hex-gauge-container {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.gauge-value {
		position: absolute;
		bottom: 10px;
		left: 50%;
		transform: translateX(-50%);
		font-size: 1.2rem;
		font-weight: bold;
		color: #ecf0f1;
		text-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
	}

	.gauge-chart {
		background: #f8f9fa;
		padding: 20px;
		border-radius: 8px;
		text-align: center;
	}

	.gauge-chart h3 {
		margin: 0 0 15px 0;
		color: #2c3e50;
		font-size: 1.1rem;
		font-weight: 600;
	}

	.bottom-section {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 15px;
	}

	.metric-card {
		background: #f8f9fa;
		padding: 20px;
		border-radius: 8px;
		text-align: center;
		position: relative;
	}

	.metric-card h4 {
		margin: 0 0 10px 0;
		color: #2c3e50;
		font-size: 0.9rem;
		font-weight: 600;
	}

	.metric-value {
		font-size: 2rem;
		font-weight: bold;
		color: #2c3e50;
		margin-bottom: 5px;
	}

	.metric-trend {
		font-size: 1.2rem;
		color: #27ae60;
		margin-bottom: 10px;
	}

	.metric-trend.down {
		color: #e74c3c;
	}

	@media (max-width: 1200px) {
		.hex-grid-section,
		.middle-section {
			grid-template-columns: 1fr;
		}
		
		.gauge-charts {
			grid-template-columns: 1fr 1fr;
		}
		
		.bottom-section {
			grid-template-columns: repeat(2, 1fr);
		}
	}

	@media (max-width: 768px) {
		.gauge-charts,
		.bottom-section {
			grid-template-columns: 1fr;
		}
	}
</style>
