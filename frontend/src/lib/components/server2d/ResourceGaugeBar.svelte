<script lang="ts">
	import ResourceGaugeCard from './ResourceGaugeCard.svelte';
	import CpuDetailModal from '$lib/components/CpuDetailModal.svelte';
	import MemoryDetailModal from '$lib/components/MemoryDetailModal.svelte';
	import DiskDetailModal from '$lib/components/DiskDetailModal.svelte';
	import GpuDetailModal from '$lib/components/GpuDetailModal.svelte';
	import NetworkDetailModal from '$lib/components/NetworkDetailModal.svelte';
	import ProcessDetailModal from '$lib/components/ProcessDetailModal.svelte';

	type SystemTrend = {
		cpu: number[];
		memory: number[];
		disk: number[];
		gpu: number[];
		network: number[];
		processes?: number[];
		cpuAvg: number;
		cpuMax: number;
		memoryAvg: number;
		memoryMax: number;
		diskAvg: number;
		diskMax: number;
		gpuAvg: number;
		gpuMax: number;
		networkAvg: number;
		networkMax: number;
		processesAvg?: number;
		processesMax?: number;
		hasGpu: boolean;
	};

	let {
		systemInfo = null as any,
		systemTrend,
		agentId = '',
		accessToken = '',
		processCount = 0,
		runningProcesses = 0,
		loading = false,
	}: {
		systemInfo: any;
		systemTrend: SystemTrend;
		agentId?: string;
		accessToken?: string;
		processCount?: number;
		runningProcesses?: number;
		loading?: boolean;
	} = $props();

	let cpuOpen = $state(false);
	let memoryOpen = $state(false);
	let diskOpen = $state(false);
	let gpuOpen = $state(false);
	let networkOpen = $state(false);
	let processOpen = $state(false);

	const gpuAverage = $derived(
		Array.isArray(systemInfo?.gpu) && systemInfo.gpu.length
			? systemInfo.gpu.reduce((sum: number, item: any) => sum + Number(item?.usage ?? 0), 0) /
					systemInfo.gpu.length
			: 0,
	);

	function severityFor(value: number): 'ok' | 'warn' | 'hot' {
		if (value >= 90) return 'hot';
		if (value >= 70) return 'warn';
		return 'ok';
	}

	function formatBytes(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0 B';
		const units = ['B', 'KB', 'MB', 'GB', 'TB'];
		let next = value;
		let index = 0;
		while (next >= 1024 && index < units.length - 1) {
			next /= 1024;
			index += 1;
		}
		return `${next.toFixed(next >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
	}

	const networkPeak = $derived(
		Math.max(systemTrend.networkMax, systemTrend.networkAvg * 2, 1024),
	);
	const networkPercent = $derived(
		Math.min(100, ((systemTrend.networkAvg || 0) / networkPeak) * 100),
	);
	const processPercent = $derived(
		processCount ? Math.min(100, (runningProcesses / processCount) * 100) : 0,
	);
</script>

<section class="gauge-bar">
	<ResourceGaugeCard
		label="CPU"
		value={Number(systemInfo?.cpu?.usage ?? 0)}
		sparkValues={systemTrend.cpu}
		sparkColor="#30d5c8"
		hint={`평균 ${systemTrend.cpuAvg.toFixed(1)}% · 최대 ${systemTrend.cpuMax.toFixed(1)}%`}
		tooltip="지금 서버 CPU 사용률입니다. 바 아래 작은 선은 선택한 시간 범위의 추이, 평균·최대는 같은 구간 수치입니다. 카드를 누르면 코어별 상세 보기가 열립니다."
		severity={severityFor(Number(systemInfo?.cpu?.usage ?? 0))}
		onOpen={() => { cpuOpen = true; }}
		{loading}
	/>
	<ResourceGaugeCard
		label="메모리"
		value={Number(systemInfo?.memory?.usage ?? 0)}
		sparkValues={systemTrend.memory}
		sparkColor="#60a5fa"
		hint={`${systemInfo?.memory?.used ?? '0 B'} / ${systemInfo?.memory?.total ?? '0 B'}`}
		tooltip="지금 서버 메모리 사용률입니다. hint는 사용/전체 용량을 MB·GB 단위로 보여줍니다. 카드를 누르면 사용량 추이와 스왑 상세가 열립니다."
		severity={severityFor(Number(systemInfo?.memory?.usage ?? 0))}
		onOpen={() => { memoryOpen = true; }}
		{loading}
	/>
	<ResourceGaugeCard
		label="디스크"
		value={Number(systemInfo?.disk?.usage ?? 0)}
		sparkValues={systemTrend.disk}
		sparkColor="#a78bfa"
		hint={`${systemInfo?.disk?.used ?? '0 B'} / ${systemInfo?.disk?.total ?? '0 B'}`}
		tooltip="루트 디스크 사용률입니다. 바가 빨간색이면 용량이 위험합니다. 카드를 누르면 파티션별 사용량을 볼 수 있습니다."
		severity={severityFor(Number(systemInfo?.disk?.usage ?? 0))}
		onOpen={() => { diskOpen = true; }}
		{loading}
	/>
	<ResourceGaugeCard
		label="GPU"
		value={gpuAverage}
		valueText={systemInfo?.gpu?.length ? `${gpuAverage.toFixed(1)}%` : '없음'}
		sparkValues={systemTrend.hasGpu ? systemTrend.gpu : []}
		sparkColor="#c084fc"
		hint={systemInfo?.gpu?.length
			? `GPU ${systemInfo.gpu.length}개 · 최대 ${systemTrend.gpuMax.toFixed(1)}%`
			: 'GPU 데이터 없음'}
		tooltip="서버에 GPU가 여러 개일 때는 전체 평균입니다. 하드웨어가 보고한 사용률을 그대로 사용합니다. 카드를 누르면 GPU별 온도·VRAM 상세가 열립니다."
		severity={systemInfo?.gpu?.length ? severityFor(gpuAverage) : 'ok'}
		disabled={!systemInfo?.gpu?.length}
		onOpen={systemInfo?.gpu?.length ? () => { gpuOpen = true; } : null}
		{loading}
	/>
	<ResourceGaugeCard
		label="네트워크"
		value={networkPercent}
		valueText={`${formatBytes(systemTrend.networkAvg || 0)}/s`}
		sparkValues={systemTrend.network}
		sparkColor="#22d3ee"
		hint={`최대 ${formatBytes(systemTrend.networkMax || 0)}/s · 연결 ${systemInfo?.network?.connections ?? 0}개`}
		tooltip="서버 전체 네트워크 트래픽(송수신 합산 속도)입니다. 바는 현재 평균이 이 시간 범위 최대치 대비 얼마나 되는지 상대적으로 보여줍니다."
		severity="ok"
		onOpen={() => { networkOpen = true; }}
		{loading}
	/>
	<ResourceGaugeCard
		label="프로세스"
		value={processPercent}
		valueText={`${processCount}`}
		sparkValues={systemTrend.processes ?? []}
		sparkColor="#fbbf24"
		hint={`실행 ${runningProcesses} · 로그인 ${systemInfo?.logins?.active ?? 0}`}
		tooltip="서버에 올라온 전체 프로세스 수입니다. hint는 실행 상태 프로세스 수와 현재 로그인한 세션 수입니다. 카드를 누르면 상위 프로세스 목록이 열립니다."
		severity="ok"
		onOpen={() => { processOpen = true; }}
		{loading}
	/>
</section>

<CpuDetailModal
	open={cpuOpen}
	{systemInfo}
	{agentId}
	{accessToken}
	onClose={() => { cpuOpen = false; }}
/>
<MemoryDetailModal
	open={memoryOpen}
	{systemInfo}
	{agentId}
	{accessToken}
	onClose={() => { memoryOpen = false; }}
/>
<DiskDetailModal
	open={diskOpen}
	{systemInfo}
	{agentId}
	{accessToken}
	onClose={() => { diskOpen = false; }}
/>
<GpuDetailModal
	open={gpuOpen}
	{systemInfo}
	{agentId}
	{accessToken}
	onClose={() => { gpuOpen = false; }}
/>
<NetworkDetailModal
	open={networkOpen}
	{systemInfo}
	{agentId}
	{accessToken}
	onClose={() => { networkOpen = false; }}
/>
<ProcessDetailModal
	open={processOpen}
	{systemInfo}
	{agentId}
	{accessToken}
	onClose={() => { processOpen = false; }}
/>

<style>
	.gauge-bar {
		display: grid;
		grid-template-columns: repeat(6, minmax(0, 1fr));
		gap: 6px;
		min-width: 0;
	}

	@media (max-width: 1100px) {
		.gauge-bar {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}

	@media (max-width: 720px) {
		.gauge-bar {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
