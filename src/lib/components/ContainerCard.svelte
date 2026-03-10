<script lang="ts">
	import { createEventDispatcher } from 'svelte';

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

	function getStateColor(state: string): string {
		switch (state) {
			case 'running':
				return '#27ae60';
			case 'exited':
				return '#e74c3c';
			case 'paused':
				return '#f39c12';
			case 'created':
				return '#3498db';
			default:
				return '#95a5a6';
		}
	}

	function getStateText(state: string): string {
		switch (state) {
			case 'running':
				return '실행 중';
			case 'exited':
				return '중지됨';
			case 'paused':
				return '일시정지';
			case 'created':
				return '생성됨';
			default:
				return state;
		}
	}

	function formatDate(timestamp: number): string {
		return new Date(timestamp * 1000).toLocaleString('ko-KR');
	}

	function formatPorts(ports: any[]): string {
		if (!ports || ports.length === 0) return '포트 없음';
		
		return ports
			.map(port => {
				if (port.PublicPort) {
					return `${port.PrivatePort}/${port.Type} -> ${port.PublicPort}`;
				}
				return `${port.PrivatePort}/${port.Type}`;
			})
			.join(', ');
	}

	function getContainerName(): string {
		if (container.names && container.names.length > 0) {
			return container.names[0].replace('/', '');
		}
		return container.shortId;
	}
</script>

<div class="container-card" role="button" tabindex="0" on:click={() => dispatch('select')} on:keydown={(e) => e.key === 'Enter' && dispatch('select')}>
	<div class="card-header">
		<div class="container-name">
			<h3>{getContainerName()}</h3>
			<span class="container-id">#{container.shortId}</span>
		</div>
		<div class="state-indicator" style="background-color: {getStateColor(container.state)}">
			{getStateText(container.state)}
		</div>
	</div>

	<div class="card-body">
		<div class="info-row">
			<span class="label">이미지:</span>
			<span class="value">{container.image}</span>
		</div>
		
		<div class="info-row">
			<span class="label">상태:</span>
			<span class="value">{container.status}</span>
		</div>

		<div class="info-row">
			<span class="label">포트:</span>
			<span class="value">{formatPorts(container.ports)}</span>
		</div>

		<div class="info-row">
			<span class="label">생성일:</span>
			<span class="value">{formatDate(container.created)}</span>
		</div>

		{#if container.labels && Object.keys(container.labels).length > 0}
			<div class="info-row">
				<span class="label">라벨:</span>
				<div class="labels">
					{#each Object.entries(container.labels).slice(0, 3) as [key, value]}
						<span class="label-tag">{key}={value}</span>
					{/each}
					{#if Object.keys(container.labels).length > 3}
						<span class="label-tag">+{Object.keys(container.labels).length - 3}개 더</span>
					{/if}
				</div>
			</div>
		{/if}
	</div>

	<div class="card-footer">
		<button class="btn btn-outline" on:click|stopPropagation={() => dispatch('select')}>
			상세 보기
		</button>
	</div>
</div>

<style>
	.container-card {
		background: white;
		border-radius: 8px;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
		overflow: hidden;
		transition: all 0.2s ease;
		cursor: pointer;
		border: 1px solid #e0e0e0;
	}

	.container-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
	}

	.card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 15px 20px;
		background: #f8f9fa;
		border-bottom: 1px solid #e0e0e0;
	}

	.container-name h3 {
		margin: 0 0 5px 0;
		font-size: 1.2rem;
		color: #2c3e50;
		font-weight: 600;
	}

	.container-id {
		font-size: 0.85rem;
		color: #7f8c8d;
		font-family: monospace;
	}

	.state-indicator {
		padding: 4px 12px;
		border-radius: 20px;
		color: white;
		font-size: 0.8rem;
		font-weight: 500;
		text-transform: uppercase;
	}

	.card-body {
		padding: 20px;
	}

	.info-row {
		display: flex;
		margin-bottom: 12px;
		align-items: flex-start;
	}

	.info-row:last-child {
		margin-bottom: 0;
	}

	.label {
		font-weight: 600;
		color: #34495e;
		min-width: 80px;
		font-size: 0.9rem;
	}

	.value {
		flex: 1;
		color: #2c3e50;
		font-size: 0.9rem;
		word-break: break-word;
	}

	.labels {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		flex: 1;
	}

	.label-tag {
		background: #ecf0f1;
		color: #2c3e50;
		padding: 2px 6px;
		border-radius: 3px;
		font-size: 0.75rem;
		font-family: monospace;
	}

	.card-footer {
		padding: 15px 20px;
		background: #f8f9fa;
		border-top: 1px solid #e0e0e0;
		text-align: center;
	}

	.btn {
		padding: 8px 16px;
		border: 1px solid #3498db;
		background: transparent;
		color: #3498db;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.9rem;
		transition: all 0.2s;
	}

	.btn:hover {
		background: #3498db;
		color: white;
	}

	.btn-outline {
		border-color: #3498db;
		color: #3498db;
	}

	.btn-outline:hover {
		background: #3498db;
		color: white;
	}
</style>
