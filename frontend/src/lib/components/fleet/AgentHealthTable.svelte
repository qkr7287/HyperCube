<script lang="ts">
	import type { FleetAgentRow } from '$lib/stores/fleet-store';
	import { formatBytes, formatClock, formatRate, formatRelative, healthLabel, humanizeReason, shortReason } from '$lib/utils/fleet-format';
	import HealthScoreGauge from './HealthScoreGauge.svelte';
	import MetricHelp from './MetricHelp.svelte';
	import MetricMiniLine from './MetricMiniLine.svelte';
	import MetricScatter from './MetricScatter.svelte';

	let {
		agents = [],
		selectedId = null,
		onSelect,
		onOpen3d,
	}: {
		agents?: FleetAgentRow[];
		selectedId?: string | null;
		onSelect: (agentId: string) => void;
		onOpen3d?: (agentId: string) => void;
	} = $props();

	let query = $state('');
	let healthFilter = $state('all');
	let sortField = $state<string | null>(null);
	let sortDir = $state<'asc' | 'desc'>('desc');

	type SortValueFn = (row: FleetAgentRow) => number | string;
	const SORT_KEYS: Record<string, SortValueFn> = {
		host: (r) => r.agent.hostname.toLowerCase(),
		score: (r) => healthScore(r),
		mem: (r) => r.latest?.memory_usage ?? -1,
		disk: (r) => r.latest?.disk_usage ?? -1,
		gpu: (r) => ((r.latest?.gpu_count ?? 0) > 0 ? r.latest?.gpu_usage ?? -1 : -1),
		net: (r) => (r.latest?.network_rx_rate ?? 0) + (r.latest?.network_tx_rate ?? 0),
		proc: (r) => r.latest?.processes_total ?? -1,
		login: (r) => r.latest?.logins_total ?? -1,
		containers: (r) => Number(r.containers.total ?? 0),
		fresh: (r) => -ageSeconds(r.latest?.timestamp), // newer first for desc
	};

	function toggleSort(field: string) {
		if (sortField === field) {
			if (sortDir === 'desc') sortDir = 'asc';
			else {
				sortField = null;
				sortDir = 'desc';
			}
		} else {
			sortField = field;
			sortDir = 'desc';
		}
	}

	function sortArrow(field: string): string {
		if (sortField !== field) return '↕';
		return sortDir === 'desc' ? '▼' : '▲';
	}
	function sortIconClass(field: string): string {
		return sortField === field ? 'sort-icon active' : 'sort-icon';
	}

	let filtered = $derived.by(() => {
		const q = query.trim().toLowerCase();
		let list = agents.filter((row) => {
			const matchesQuery = !q || row.agent.hostname.toLowerCase().includes(q) || row.agent.ip_address.includes(q);
			const matchesHealth = healthFilter === 'all' || row.health === healthFilter;
			return matchesQuery && matchesHealth;
		});
		if (sortField && SORT_KEYS[sortField]) {
			const keyFn = SORT_KEYS[sortField];
			const sign = sortDir === 'asc' ? 1 : -1;
			list = [...list].sort((a, b) => {
				const va = keyFn(a);
				const vb = keyFn(b);
				if (va < vb) return -1 * sign;
				if (va > vb) return 1 * sign;
				return 0;
			});
		}
		return list;
	});

	const healthOptions = ['all', 'critical', 'warning', 'stale', 'offline', 'healthy'];
	const healthOptionLabels: Record<string, string> = {
		all: '전체 상태',
		critical: '위험',
		warning: '주의',
		stale: '지연',
		offline: '오프라인',
		healthy: '정상',
	};

	function handleMonitor(event: MouseEvent, agentId: string) {
		event.preventDefault();
		event.stopPropagation();
		event.stopImmediatePropagation?.();
		onOpen3d?.(agentId);
	}

	function handleRowClick(event: MouseEvent, agentId: string) {
		// tr onclick은 기본 select. 하지만 내부에 있는 .monitor-btn 이나 다른
		// button / link 클릭일 땐 select를 무시해서 버튼이 제 역할을 하도록 함.
		const target = event.target as HTMLElement | null;
		if (target?.closest('button, a, .monitor-btn')) return;
		onSelect(agentId);
	}

	function procText(row: FleetAgentRow): string {
		const total = row.latest?.processes_total ?? 0;
		const running = row.latest?.processes_running ?? 0;
		if (!total) return '-';
		return `${running} / ${total}`;
	}

	function memText(row: FleetAgentRow): string {
		const used = row.latest?.memory_used ?? 0;
		const total = row.latest?.memory_total ?? 0;
		if (!total) return '-';
		return `${formatBytes(used)} / ${formatBytes(total)}`;
	}

	function healthScore(row: FleetAgentRow): number {
		if (row.health === 'offline') return 0;
		if (!row.latest) return 30;
		const cpu = row.latest.cpu_usage ?? 0;
		const mem = row.latest.memory_usage ?? 0;
		const disk = row.latest.disk_usage ?? 0;
		const gpu = row.latest.gpu_count > 0 ? row.latest.gpu_usage ?? 0 : 0;
		const peak = Math.max(cpu, mem, disk, gpu);
		const reasons = row.health_reasons.length;
		let score = 100 - peak - reasons * 3;
		if (row.health === 'stale') score = Math.min(score, 55);
		return Math.max(0, Math.min(100, Math.round(score)));
	}

	function ageSeconds(timestamp?: string | null): number {
		if (!timestamp) return 9999;
		const at = new Date(timestamp).getTime();
		if (Number.isNaN(at)) return 9999;
		return Math.max(0, Math.floor((Date.now() - at) / 1000));
	}

	function freshnessClass(age: number): string {
		if (age >= 9999) return 'expired';
		if (age <= 15) return 'fresh';
		if (age <= 30) return 'warm';
		if (age <= 60) return 'stale';
		return 'expired';
	}
</script>

<section class="table-panel">
	<div class="table-head">
		<div class="head-left">
			<h2>서버 상세 정보</h2>
			<MetricHelp text={"각 서버의 실제 수치(GB, 개수, 속도)를 보여줍니다.\n\n• 카드: 퍼센트 중심 시각화\n• 테이블: 원 데이터 + 정렬/검색\n\n컬럼 헤더를 클릭하면 해당 값 기준으로 정렬됩니다."} />
			<span class="count-chip">전체 <b>{agents.length}</b>대 중 <b>{filtered.length}</b>대 표시</span>
		</div>
		<div class="tools">
			<input bind:value={query} type="search" placeholder="호스트명 또는 IP 검색" />
			<select bind:value={healthFilter} aria-label="상태 필터">
				{#each healthOptions as option}
					<option value={option}>{healthOptionLabels[option]}</option>
				{/each}
			</select>
		</div>
	</div>

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th class="c-state">상태</th>
					<th class="c-score sortable" onclick={() => toggleSort('score')}>
						부하 점수 <span class={sortIconClass('score')}>{sortArrow('score')}</span>
						<MetricHelp text={"100에 가까울수록 여유, 0에 가까울수록 과부하.\n\n계산식\n• 기본점 = 100 − max(CPU, 메모리, 디스크, GPU)\n• 경고 원인 1개당 −3점\n• 오프라인 = 0, 지연 = 최대 55\n\n헤더를 클릭하면 점수 기준 정렬."} />
					</th>
					<th class="c-host sortable" onclick={() => toggleSort('host')}>
						서버 <span class={sortIconClass('host')}>{sortArrow('host')}</span>
					</th>
					<th class="c-mem sortable" onclick={() => toggleSort('mem')}>
						메모리 사용량 <span class={sortIconClass('mem')}>{sortArrow('mem')}</span>
						<MetricHelp text={"사용 중 메모리 ÷ 전체 RAM × 100\n\n• buff/cache 포함\n• 표시: 사용 GB / 전체 GB + %\n• 정렬: 사용률(%) 기준"} />
					</th>
					<th class="c-disk sortable" onclick={() => toggleSort('disk')}>
						디스크 사용량 <span class={sortIconClass('disk')}>{sortArrow('disk')}</span>
						<MetricHelp text={"루트 파티션(/) 사용률(%)\n\n• 사용 용량 ÷ 전체 용량 × 100\n• 다른 마운트는 제외\n• 90%↑ 위험 (공간 부족)"} />
					</th>
					<th class="c-gpu sortable" onclick={() => toggleSort('gpu')}>
						GPU <span class={sortIconClass('gpu')}>{sortArrow('gpu')}</span>
						<MetricHelp text={"GPU 정보\n\n• 개수: 장착된 GPU 수\n• 온도: °C (장착된 장비 최대)\n• 사용률: 전체 GPU 평균 (%)\n\n정렬: 사용률(%) 기준"} />
					</th>
					<th class="c-net sortable" onclick={() => toggleSort('net')}>
						네트워크 <span class={sortIconClass('net')}>{sortArrow('net')}</span>
						<MetricHelp text="초당 수신(↓) / 송신(↑) 속도. 정렬은 합계 기준." />
					</th>
					<th class="c-proc sortable" onclick={() => toggleSort('proc')}>
						프로세스 수 <span class={sortIconClass('proc')}>{sortArrow('proc')}</span>
						<MetricHelp text="실행 중 / 전체 프로세스 수" />
					</th>
					<th class="c-login sortable" onclick={() => toggleSort('login')}>
						로그인 세션 <span class={sortIconClass('login')}>{sortArrow('login')}</span>
						<MetricHelp text="현재 활성 로그인 세션 수" />
					</th>
					<th class="c-containers sortable" onclick={() => toggleSort('containers')}>
						컨테이너 분포 <span class={sortIconClass('containers')}>{sortArrow('containers')}</span>
						<MetricHelp text="실행 · 정지 · 이상 상태별 분포. 정렬은 총 개수 기준." />
					</th>
					<th class="c-net-trend">네트워크 추이 <MetricHelp text={"최근 RX + TX 합계 속도의 추이.\n\n• 선이 높게 유지: 지속 트래픽\n• 뾰족한 스파이크: 일시 전송\n• 0 근처: 유휴 상태"} placement="bottom-end" /></th>
					<th class="c-fresh sortable" onclick={() => toggleSort('fresh')}>
						최신 메트릭 <span class={sortIconClass('fresh')}>{sortArrow('fresh')}</span>
						<MetricHelp text="마지막 메트릭이 수신된 시점(상대 시각)과 절대 시각입니다. 정렬은 최신순." placement="bottom-end" />
					</th>
					<th class="c-trend">부하 분포 <MetricHelp text={"X축 = CPU %\nY축 = 메모리 %\n점 하나 = 시계열 한 포인트\n\n해석\n• 우상단: 고부하\n• 좌하단: 여유\n• 대각선: 균형\n• 수평/수직 분산: 한쪽만 출렁임\n\n큰 점 = 현재값"} placement="bottom-end" /></th>
					<th class="c-action">상세 모니터링</th>
				</tr>
			</thead>
			<tbody>
				{#if filtered.length === 0}
					<tr>
						<td colspan="14" class="empty">조건에 맞는 서버가 없습니다.</td>
					</tr>
				{:else}
					{#each filtered as row (row.agent.id)}
						{@const total = Number(row.containers.total ?? 0)}
						{@const running = Number(row.containers.running ?? 0)}
						{@const other = Number(row.containers.non_running ?? 0)}
						{@const problem = Number(row.containers.problem ?? 0)}
						{@const runPct = total ? (running / total) * 100 : 0}
						{@const otherPct = total ? (other / total) * 100 : 0}
						{@const problemPct = total ? (problem / total) * 100 : 0}
						{@const freshAge = ageSeconds(row.latest?.timestamp)}
						{@const freshKey = freshnessClass(freshAge)}
						{@const freshPct = Math.min(100, (freshAge / 60) * 100)}
						<tr
							class="{row.health}"
							class:selected={selectedId === row.agent.id}
							onclick={(e) => handleRowClick(e, row.agent.id)}
						>
							<td class="c-state">
								<span class="health {row.health}">{healthLabel(row.health)}</span>
								{#if row.health_reasons.length}
									<div class="reason" title={humanizeReason(row.health_reasons[0])}>
										{shortReason(row.health_reasons[0])}
									</div>
								{/if}
							</td>
							<td class="c-score">
								<HealthScoreGauge value={healthScore(row)} size={38} stroke={4} />
							</td>
							<td class="c-host">
								<strong title={row.agent.hostname}>{row.agent.hostname}</strong>
								<span>{row.agent.ip_address}</span>
							</td>
							<td class="c-mem">
								<strong>{memText(row)}</strong>
								<span>{row.latest?.memory_total ? `${((row.latest?.memory_usage ?? 0)).toFixed(1)}% 사용 중` : '-'}</span>
							</td>
							<td class="c-disk">
								{#if (row.latest?.disk_usage ?? 0) > 0}
									<strong>{((row.latest?.disk_usage ?? 0)).toFixed(1)}%</strong>
									<span>공간 사용 중</span>
								{:else}
									<strong>-</strong>
									<span>정보 없음</span>
								{/if}
							</td>
							<td class="c-gpu">
								{#if (row.latest?.gpu_count ?? 0) > 0}
									<strong>{row.latest?.gpu_count}개</strong>
									<span>
										{#if row.latest?.gpu_temperature != null}
											{row.latest?.gpu_temperature}°C
										{:else}
											-
										{/if}
										· {((row.latest?.gpu_usage ?? 0)).toFixed(0)}%
									</span>
								{:else}
									<strong class="dim">-</strong>
									<span>GPU 없음</span>
								{/if}
							</td>
							<td class="c-net">
								<div class="net-line"><i class="rx"></i> ↓ {formatRate(row.latest?.network_rx_rate)}</div>
								<div class="net-line"><i class="tx"></i> ↑ {formatRate(row.latest?.network_tx_rate)}</div>
							</td>
							<td class="c-proc">
								<strong>{procText(row)}</strong>
								<span>실행 / 전체</span>
							</td>
							<td class="c-login">
								<strong>{row.latest?.logins_total ?? 0}</strong>
								<span>활성 세션</span>
							</td>
							<td class="c-containers">
								{#if total > 0}
									<div class="ct-bar" aria-label={`전체 ${total}개 컨테이너`}>
										<span class="seg running" style={`width: ${runPct}%`}></span>
										<span class="seg other" style={`width: ${otherPct}%`}></span>
										<span class="seg problem" style={`width: ${problemPct}%`}></span>
									</div>
									<div class="ct-legend">
										<span class="ct-c running"><b>{running}</b> 실행</span>
										<span class="ct-c other"><b>{other}</b> 정지</span>
										<span class="ct-c problem" class:active={problem > 0}><b>{problem}</b> 이상</span>
									</div>
								{:else}
									<strong class="dim">-</strong>
									<span class="subtle">컨테이너 없음</span>
								{/if}
							</td>
							<td class="c-net-trend">
								<MetricMiniLine
									values={(row.sparkline.rx ?? []).map((v, i) => v + (row.sparkline.tx?.[i] ?? 0))}
									color="#fbbf24"
									label={`${row.agent.hostname} 네트워크 추이`}
								/>
							</td>
							<td class="c-fresh">
								<div class="fresh-head">
									<span class="fresh-dot {freshKey}"></span>
									<strong>{formatRelative(row.latest?.timestamp)}</strong>
								</div>
								<div class="fresh-bar">
									<span class={freshKey} style={`width: ${freshPct}%`}></span>
								</div>
								<span class="fresh-clock">{row.latest?.timestamp ? formatClock(row.latest.timestamp) : '-'}</span>
							</td>
							<td class="c-trend">
								<MetricScatter
									cpu={row.sparkline.cpu}
									memory={row.sparkline.memory}
									color={row.health === 'critical' ? '#f87171' : row.health === 'warning' ? '#fbbf24' : '#30d5c8'}
									label={`${row.agent.hostname} CPU-메모리 분포`}
								/>
							</td>
							<td class="c-action">
								{#if onOpen3d}
									{@const isSim = row.agent.id.startsWith('sim-')}
									<button
										type="button"
										class="monitor-btn"
										class:disabled={isSim}
										disabled={isSim}
										onclick={(e) => handleMonitor(e, row.agent.id)}
										title={isSim ? '시뮬레이션 서버는 3D 뷰로 연결할 실제 토폴로지가 없습니다' : '3D 토폴로지 뷰에서 상세 모니터링'}
									>
										<span aria-hidden="true">◆</span>
										<span>상세</span>
									</button>
								{/if}
							</td>
						</tr>
					{/each}
				{/if}
			</tbody>
		</table>
	</div>
</section>

<style>
	.table-panel {
		/* monitor-btn 이 FleetAgentCard와 동일 토큰을 쓰도록 로컬 선언 — 카드와 테이블
		   버튼이 같은 치수/발색을 유지하는 것이 목표. */
		--font-xs: clamp(10px, 0.62vw, 13px);
		min-width: 0;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 10px 10px 4px;
		min-height: 0;
		height: 100%;
		display: flex;
		flex-direction: column;
	}
	.table-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 14px;
		margin-bottom: 6px;
		flex-shrink: 0;
	}
	.head-left {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}
	h2 {
		margin: 0;
		display: inline-flex;
		align-items: center;
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 800;
		white-space: nowrap;
	}
	.count-chip {
		display: inline-flex;
		align-items: center;
		padding: 2px 8px;
		border: 1px solid var(--border);
		border-radius: var(--radius-full);
		background: rgba(13, 17, 23, 0.45);
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
		white-space: nowrap;
	}
	.count-chip b {
		color: var(--text-primary);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		margin: 0 1px;
	}
	.tools {
		display: flex;
		gap: 6px;
	}
	input,
	select {
		height: 28px;
		border-radius: var(--radius-sm);
		border: 1px solid var(--border);
		background: var(--bg-base);
		color: var(--text-primary);
		padding: 0 8px;
		font-size: 11px;
	}
	input {
		width: 200px;
	}
	.table-wrap {
		flex: 1;
		overflow-x: hidden;
		overflow-y: auto;
		min-height: 0;
	}
	table {
		width: 100%;
		table-layout: fixed;
		border-collapse: collapse;
	}
	th,
	td {
		padding: 6px 8px;
		border-bottom: 1px solid var(--border);
		text-align: left;
		vertical-align: middle;
		white-space: nowrap;
	}
	th {
		overflow: visible;
		user-select: none;
	}
	th.sortable {
		cursor: pointer;
		transition: color 0.12s ease;
	}
	th.sortable:hover {
		color: var(--text-primary);
	}
	.sort-icon {
		display: inline-block;
		color: rgba(100, 116, 139, 0.55);
		font-size: 9px;
		margin-left: 2px;
		transition: color 0.12s ease;
	}
	th.sortable:hover .sort-icon {
		color: var(--text-secondary);
	}
	.sort-icon.active {
		color: var(--accent);
	}
	td {
		overflow: hidden;
		text-overflow: ellipsis;
	}
	/* Column widths — 14 cols, total ≈ 100%, no horizontal scroll */
	.c-state { width: 6%; min-width: 76px; }
	.c-score {
		width: 5%;
		min-width: 58px;
		text-align: center;
	}
	.c-score :global(svg) {
		margin: 0 auto;
	}
	th.c-score {
		padding-left: 0;
		padding-right: 0;
	}
	th.c-score :global(.info-tip) {
		margin-left: 3px;
	}
	.c-host { width: 10%; min-width: 140px; }
	.c-mem { width: 9%; min-width: 116px; }
	.c-disk { width: 5%; min-width: 66px; }
	.c-gpu { width: 6%; min-width: 72px; }
	.c-net { width: 7%; min-width: 96px; }
	.c-net-trend { width: 8%; min-width: 100px; }
	.c-proc { width: 5%; min-width: 64px; }
	.c-login { width: 4%; min-width: 50px; }
	.c-containers { width: 12%; min-width: 150px; }
	.c-fresh { width: 8%; min-width: 92px; }
	.c-trend { width: 9%; min-width: 108px; }
	.c-action { width: 5%; min-width: 56px; }
	th {
		position: sticky;
		top: 0;
		z-index: 1;
		background: var(--bg-card);
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 800;
		letter-spacing: 0.2px;
	}
	tbody tr {
		cursor: pointer;
		box-shadow: inset 3px 0 0 var(--state-color, rgba(100, 116, 139, 0.35));
	}
	/* 좌측 바 색 = health chip 색상과 정확히 일치 — 한 눈에 상태 인식하기 쉽게. */
	tbody tr.healthy  { --state-color: #34d399; }
	tbody tr.warning  { --state-color: #fbbf24; } /* amber 400 */
	tbody tr.critical { --state-color: #f87171; } /* red 400 */
	tbody tr.stale    { --state-color: #a78bfa; } /* violet 400 */
	tbody tr.offline  { --state-color: #94a3b8; } /* slate 400 */
	tbody tr:hover {
		background: var(--bg-tab);
	}
	tbody tr.selected {
		/* 좌측 3px 막대는 상태색 유지 — selected라고 해도 상태 정보가 더 중요.
		   선택 표시는 배경 tint만으로 충분. */
		background: rgba(48, 213, 200, 0.08);
		outline: 1px solid rgba(48, 213, 200, 0.3);
		outline-offset: -1px;
	}
	.health {
		display: inline-flex;
		padding: 3px 8px;
		border-radius: var(--radius-full);
		font-size: 11px;
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	/* chip 색상은 좌측 바 색상과 1:1 매칭. stale은 보라(violet), offline만 slate 회색. */
	.health.healthy  { color: #34d399; background: rgba(52, 211, 153, 0.14); }
	.health.warning  { color: #fbbf24; background: rgba(251, 191, 36, 0.14); }
	.health.critical { color: #f87171; background: rgba(248, 113, 113, 0.14); }
	.health.stale    { color: #a78bfa; background: rgba(167, 139, 250, 0.14); }
	.health.offline  { color: #94a3b8; background: rgba(148, 163, 184, 0.14); }

	td strong {
		display: block;
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	td strong.dim {
		color: var(--text-muted);
	}
	/* monitor-btn 내부 span은 버튼 스타일(teal), .health 는 상태별 색상을 유지해야
	   해서 이 회색 muted 규칙에서 제외. 안 그러면 "상세"가 회색으로, "주의/위험/
	   오프라인" chip 텍스트도 회색으로 죽어 보임. */
	td span:not(.monitor-btn span):not(.monitor-btn *):not(.health),
	td .subtle {
		display: block;
		margin-top: 2px;
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 600;
	}
	.reason {
		margin-top: 2px;
		color: var(--text-secondary);
		font-size: 11px;
		font-weight: 600;
		white-space: nowrap;
		line-height: 1.25;
	}
	.c-host strong {
		max-width: 180px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.net-line {
		display: flex;
		align-items: center;
		gap: 4px;
		color: var(--text-primary);
		font-size: 11px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		line-height: 1.4;
	}
	.net-line i {
		width: 5px;
		height: 5px;
		border-radius: 50%;
		display: inline-block;
	}
	.net-line i.rx { background: #22d3ee; }
	.net-line i.tx { background: #fbbf24; }

	.ct-bar {
		display: flex;
		height: 8px;
		border-radius: var(--radius-full);
		overflow: hidden;
		background: rgba(100, 116, 139, 0.2);
	}
	.ct-bar .seg {
		display: block;
		height: 100%;
	}
	.ct-bar .seg.running {
		background: linear-gradient(90deg, #22c55e, #30d5c8);
	}
	.ct-bar .seg.other {
		background: #64748b;
	}
	.ct-bar .seg.problem {
		background: #ef4444;
	}
	.ct-legend {
		display: flex;
		gap: 6px;
		margin-top: 3px;
		font-size: 10px;
		font-weight: 700;
	}
	.ct-c {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		color: var(--text-muted);
	}
	.ct-c b {
		font-variant-numeric: tabular-nums;
	}
	.ct-c.running b { color: #34d399; }
	.ct-c.other b { color: var(--text-primary); }
	.ct-c.problem.active b { color: #f87171; }

	.c-trend :global(svg) {
		width: 100% !important;
		max-width: 130px !important;
	}

	.c-action {
		text-align: center;
	}

	.fresh-head {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.fresh-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
		background: #34d399;
		box-shadow: 0 0 6px rgba(52, 211, 153, 0.6);
		animation: pulse 1.8s ease-in-out infinite;
	}
	.fresh-dot.warm {
		background: #60a5fa;
		box-shadow: 0 0 6px rgba(96, 165, 250, 0.6);
	}
	.fresh-dot.stale {
		background: #fbbf24;
		box-shadow: 0 0 6px rgba(251, 191, 36, 0.6);
		animation-duration: 2.4s;
	}
	.fresh-dot.expired {
		background: #ef4444;
		box-shadow: 0 0 6px rgba(239, 68, 68, 0.6);
		animation: none;
	}
	@keyframes pulse {
		0%, 100% { opacity: 1; transform: scale(1); }
		50% { opacity: 0.5; transform: scale(0.75); }
	}
	.fresh-bar {
		margin-top: 4px;
		height: 4px;
		border-radius: var(--radius-full);
		background: rgba(100, 116, 139, 0.2);
		overflow: hidden;
	}
	.fresh-bar span {
		display: block;
		height: 100%;
		transition: width 0.4s ease;
		background: #34d399;
	}
	.fresh-bar span.warm { background: #60a5fa; }
	.fresh-bar span.stale { background: #fbbf24; }
	.fresh-bar span.expired { background: #ef4444; }
	.fresh-clock {
		display: block;
		margin-top: 2px;
		color: var(--text-muted);
		font-size: 10px;
		font-variant-numeric: tabular-nums;
	}
	.monitor-btn {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		/* 카드 쪽 monitor-btn과 완전히 동일한 치수·발색 — 통일성 보장. */
		height: clamp(22px, 1.8vw, 32px);
		padding: 0 clamp(7px, 0.55vw, 14px);
		border: 1px solid rgba(48, 213, 200, 0.6);
		border-radius: var(--radius-sm);
		/* 선택된 tr의 청록 틴트 위에서도 일관된 발색을 위해 솔리드 바탕 + 청록 오버레이를 합성. */
		background: linear-gradient(rgba(48, 213, 200, 0.18), rgba(48, 213, 200, 0.18)), var(--bg-card);
		color: var(--accent);
		font-family: inherit;
		font-size: var(--font-xs);
		font-weight: 800;
		letter-spacing: 0.2px;
		white-space: nowrap;
		cursor: pointer;
		transition: background 0.12s ease, border-color 0.12s ease;
	}
	.monitor-btn:hover:not(.disabled) {
		background: linear-gradient(rgba(48, 213, 200, 0.3), rgba(48, 213, 200, 0.3)), var(--bg-card);
		border-color: rgba(48, 213, 200, 0.8);
	}
	.monitor-btn.disabled,
	.monitor-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
		background: rgba(100, 116, 139, 0.1);
		color: var(--text-muted);
		border-color: rgba(100, 116, 139, 0.3);
	}

	.empty {
		height: 160px;
		text-align: center;
		color: var(--text-muted);
	}
	@media (max-width: 900px) {
		.table-head {
			display: block;
		}
		.tools {
			margin-top: 10px;
			flex-wrap: wrap;
		}
		input {
			width: min(100%, 260px);
		}
	}
</style>
