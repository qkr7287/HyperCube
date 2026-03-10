<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Chart, registerables } from 'chart.js';
	import 'chartjs-adapter-date-fns';

	Chart.register(...registerables);

	export let containerId: string;
	export let type: 'cpu' | 'memory' | 'network' | 'disk' = 'cpu';

	let chartCanvas: HTMLCanvasElement;
	let chart: Chart | null = null;
	let metricsData: any[] = [];
	let maxDataPoints = 60; // 5분간의 데이터 (5초 간격)
	let refreshInterval: ReturnType<typeof setInterval>;

	interface MetricData {
		timestamp: string;
		cpu: { usage: number; cores: number };
		memory: { usage: number; limit: number; percent: number };
		network: { rx: number; tx: number };
		disk: { read: number; write: number };
	}

	onMount(() => {
		initializeChart();
		startMetricsCollection();
		
		return () => {
			if (refreshInterval) {
				clearInterval(refreshInterval);
			}
			if (chart) {
				chart.destroy();
			}
		};
	});

	onDestroy(() => {
		if (refreshInterval) {
			clearInterval(refreshInterval);
		}
		if (chart) {
			chart.destroy();
		}
	});

	async function fetchMetrics() {
		try {
			const response = await fetch(`/api/containers/${containerId}/metrics`);
			const result = await response.json();
			
			if (result.success) {
				addMetricData(result.data);
			}
		} catch (error) {
			console.error('Error fetching metrics:', error);
		}
	}

	function addMetricData(data: MetricData) {
		metricsData.push(data);
		
		// 최대 데이터 포인트 수 제한
		if (metricsData.length > maxDataPoints) {
			metricsData.shift();
		}
		
		updateChart();
	}

	function initializeChart() {
		if (!chartCanvas) return;

		const ctx = chartCanvas.getContext('2d');
		if (!ctx) return;

		const config = getChartConfig();
		chart = new Chart(ctx, config);
	}

	function getChartConfig() {
		const baseConfig: any = {
			type: 'line' as const,
			data: {
				labels: [],
				datasets: []
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: {
					intersect: false,
					mode: 'index' as const
				},
				scales: {
					x: {
						type: 'time' as const,
						time: {
							displayFormats: {
								second: 'HH:mm:ss'
							}
						},
						title: {
							display: true,
							text: '시간'
						}
					},
					y: {
						beginAtZero: true,
						title: {
							display: true,
							text: getYAxisLabel()
						}
					}
				},
				plugins: {
					legend: {
						display: true,
						position: 'top' as const
					},
					tooltip: {
						mode: 'index' as const,
						intersect: false
					}
				}
			}
		};

		switch (type) {
			case 'cpu':
				baseConfig.data.datasets = [{
					label: 'CPU 사용률 (%)',
					data: [],
					borderColor: '#3498db',
					backgroundColor: 'rgba(52, 152, 219, 0.1)',
					tension: 0.4,
					fill: true
				}];
				break;
			case 'memory':
				baseConfig.data.datasets = [{
					label: '메모리 사용률 (%)',
					data: [],
					borderColor: '#e74c3c',
					backgroundColor: 'rgba(231, 76, 60, 0.1)',
					tension: 0.4,
					fill: true
				}];
				break;
			case 'network':
				baseConfig.data.datasets = [
					{
						label: '수신 (bytes)',
						data: [],
						borderColor: '#2ecc71',
						backgroundColor: 'rgba(46, 204, 113, 0.1)',
						tension: 0.4,
						fill: false
					},
					{
						label: '송신 (bytes)',
						data: [],
						borderColor: '#f39c12',
						backgroundColor: 'rgba(243, 156, 18, 0.1)',
						tension: 0.4,
						fill: false
					}
				];
				break;
			case 'disk':
				baseConfig.data.datasets = [
					{
						label: '읽기 (bytes)',
						data: [],
						borderColor: '#9b59b6',
						backgroundColor: 'rgba(155, 89, 182, 0.1)',
						tension: 0.4,
						fill: false
					},
					{
						label: '쓰기 (bytes)',
						data: [],
						borderColor: '#1abc9c',
						backgroundColor: 'rgba(26, 188, 156, 0.1)',
						tension: 0.4,
						fill: false
					}
				];
				break;
		}

		return baseConfig;
	}

	function updateChart() {
		if (!chart || !chartCanvas) return;

		// DOM 요소가 여전히 존재하는지 확인
		if (!chartCanvas.ownerDocument) {
			console.warn('Chart canvas is not attached to DOM');
			return;
		}

		const labels = metricsData.map(d => new Date(d.timestamp));
		chart.data.labels = labels;

		switch (type) {
			case 'cpu':
				chart.data.datasets[0].data = metricsData.map(d => d.cpu.usage);
				break;
			case 'memory':
				chart.data.datasets[0].data = metricsData.map(d => d.memory.percent);
				break;
			case 'network':
				chart.data.datasets[0].data = metricsData.map(d => d.network.rx);
				chart.data.datasets[1].data = metricsData.map(d => d.network.tx);
				break;
			case 'disk':
				chart.data.datasets[0].data = metricsData.map(d => d.disk.read);
				chart.data.datasets[1].data = metricsData.map(d => d.disk.write);
				break;
		}

		try {
			chart.update('none');
		} catch (error) {
			console.error('Chart update error:', error);
		}
	}

	function getYAxisLabel(): string {
		switch (type) {
			case 'cpu': return 'CPU 사용률 (%)';
			case 'memory': return '메모리 사용률 (%)';
			case 'network': return '바이트';
			case 'disk': return '바이트';
			default: return '값';
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

	function getChartTitle(): string {
		switch (type) {
			case 'cpu': return 'CPU 사용률';
			case 'memory': return '메모리 사용률';
			case 'network': return '네트워크 I/O';
			case 'disk': return '디스크 I/O';
			default: return '메트릭';
		}
	}

	function getCurrentMetrics(): string {
		if (metricsData.length === 0) return '';
		
		const latest = metricsData[metricsData.length - 1];
		
		switch (type) {
			case 'cpu':
				return `
					<div class="metric-item">
						<div class="metric-label">CPU 사용률</div>
						<div class="metric-value">${latest.cpu.usage.toFixed(1)}%</div>
					</div>
					<div class="metric-item">
						<div class="metric-label">CPU 코어</div>
						<div class="metric-value">${latest.cpu.cores}</div>
					</div>
				`;
			case 'memory':
				return `
					<div class="metric-item">
						<div class="metric-label">메모리 사용률</div>
						<div class="metric-value">${latest.memory.percent.toFixed(1)}%</div>
					</div>
					<div class="metric-item">
						<div class="metric-label">사용량</div>
						<div class="metric-value">${formatBytes(latest.memory.usage)}</div>
					</div>
					<div class="metric-item">
						<div class="metric-label">제한</div>
						<div class="metric-value">${formatBytes(latest.memory.limit)}</div>
					</div>
				`;
			case 'network':
				return `
					<div class="metric-item">
						<div class="metric-label">수신</div>
						<div class="metric-value">${formatBytes(latest.network.rx)}</div>
					</div>
					<div class="metric-item">
						<div class="metric-label">송신</div>
						<div class="metric-value">${formatBytes(latest.network.tx)}</div>
					</div>
				`;
			case 'disk':
				return `
					<div class="metric-item">
						<div class="metric-label">읽기</div>
						<div class="metric-value">${formatBytes(latest.disk.read)}</div>
					</div>
					<div class="metric-item">
						<div class="metric-label">쓰기</div>
						<div class="metric-value">${formatBytes(latest.disk.write)}</div>
					</div>
				`;
			default:
				return '';
		}
	}
</script>

<div class="metrics-chart">
	<div class="chart-header">
		<h3>{getChartTitle()}</h3>
		<div class="chart-controls">
			<button class="btn btn-sm" on:click={() => metricsData = []}>
				초기화
			</button>
		</div>
	</div>
	<div class="chart-container">
		<canvas bind:this={chartCanvas}></canvas>
	</div>
	<div class="chart-info">
		{#if metricsData.length > 0}
			<div class="current-metrics">
				{@html getCurrentMetrics()}
			</div>
		{/if}
	</div>
</div>

<style>
	.metrics-chart {
		background: rgba(255, 255, 255, 0.05);
		border-radius: 12px;
		padding: 20px;
		margin-bottom: 20px;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.chart-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 15px;
	}

	.chart-header h3 {
		margin: 0;
		color: #ffffff;
		font-size: 1.1rem;
		font-weight: 600;
	}

	.chart-container {
		position: relative;
		height: 300px;
		width: 100%;
	}

	.chart-info {
		margin-top: 15px;
		padding-top: 15px;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}

	.current-metrics {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 15px;
	}

	.metric-item {
		text-align: center;
	}

	.metric-label {
		font-size: 0.8rem;
		color: #b0b0b0;
		margin-bottom: 5px;
	}

	.metric-value {
		font-size: 1.2rem;
		font-weight: 600;
		color: #ffffff;
	}

	.btn {
		padding: 6px 12px;
		border: 1px solid rgba(255, 255, 255, 0.2);
		background: transparent;
		color: #b0b0b0;
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.8rem;
		transition: all 0.2s ease;
	}

	.btn:hover {
		background: rgba(255, 255, 255, 0.1);
		color: #ffffff;
	}

	.btn-sm {
		padding: 4px 8px;
		font-size: 0.75rem;
	}
</style>
