<!--
  InspectPanel — agent.inspect 응답을 4개 영역으로 정리:
  - Health & Lifecycle: state.status / health / restartCount / startedAt / exitCode / oomKilled
  - Network: networkSettings.networks (이름/IP), ports (host → container)
  - Mounts: mounts[] (type / source / destination / mode)
  - Image / Config: image, config.cmd, entrypoint, workingDir
  + Raw JSON (collapsible)
-->
<script lang="ts">
	import { formatDateTime } from '$lib/utils/container-dashboard';
	import StateBox from './StateBox.svelte';

	type InspectData = {
		id?: string;
		name?: string;
		created?: string;
		state?: {
			status?: string;
			running?: boolean;
			paused?: boolean;
			restarting?: boolean;
			oomKilled?: boolean;
			dead?: boolean;
			pid?: number;
			exitCode?: number;
			startedAt?: string;
			finishedAt?: string;
			health?: { status?: string; failingStreak?: number; log?: any[] } | null;
		};
		image?: string;
		config?: {
			hostname?: string;
			env?: string[];
			cmd?: string[] | null;
			labels?: Record<string, string>;
			workingDir?: string;
			entrypoint?: string[] | null;
		};
		networkSettings?: {
			ports?: Record<string, Array<{ HostIp?: string; HostPort?: string }> | null> | null;
			networks?: Record<string, { IPAddress?: string; Gateway?: string; MacAddress?: string; [k: string]: any }> | null;
		};
		mounts?: Array<{ type?: string; source?: string; destination?: string; mode?: string; rw?: boolean }>;
		restartCount?: number;
	};

	let {
		data,
		loading = false,
		errorMsg = '',
	}: {
		data: InspectData | null;
		loading?: boolean;
		errorMsg?: string;
	} = $props();

	let rawOpen = $state(false);
	let copied = $state(false);

	let healthBadge = $derived(computeHealthBadge(data));
	let portRows = $derived(computePortRows(data));
	let networkRows = $derived(computeNetworkRows(data));
	let mounts = $derived(data?.mounts ?? []);
	let envCount = $derived(data?.config?.env?.length ?? 0);

	function computeHealthBadge(d: InspectData | null) {
		if (!d?.state) return { tone: 'muted', text: '정보 없음' };
		const s = d.state;
		if (s.oomKilled) return { tone: 'danger', text: 'OOM Killed' };
		if (s.dead) return { tone: 'danger', text: 'Dead' };
		if (s.restarting) return { tone: 'warn', text: '재시작 중' };
		if (s.health?.status) {
			if (s.health.status === 'healthy') return { tone: 'success', text: 'Healthy' };
			if (s.health.status === 'unhealthy') return { tone: 'danger', text: 'Unhealthy' };
			if (s.health.status === 'starting') return { tone: 'warn', text: 'Health 시작 중' };
		}
		if (s.running) return { tone: 'success', text: '실행 중' };
		if (s.paused) return { tone: 'warn', text: '일시정지' };
		return { tone: 'muted', text: s.status || '알 수 없음' };
	}

	function computePortRows(d: InspectData | null): Array<{ container: string; bindings: string }> {
		const ports = d?.networkSettings?.ports;
		if (!ports) return [];
		const rows: Array<{ container: string; bindings: string }> = [];
		for (const [containerPort, list] of Object.entries(ports)) {
			if (!list || list.length === 0) {
				rows.push({ container: containerPort, bindings: '(미공개)' });
				continue;
			}
			const bindings = list
				.map((b) => `${b.HostIp || '0.0.0.0'}:${b.HostPort ?? '-'}`)
				.join(', ');
			rows.push({ container: containerPort, bindings });
		}
		return rows;
	}

	function computeNetworkRows(d: InspectData | null): Array<{ name: string; ip: string; gateway: string; mac: string }> {
		const nets = d?.networkSettings?.networks;
		if (!nets) return [];
		return Object.entries(nets).map(([name, info]) => ({
			name,
			ip: info?.IPAddress || '-',
			gateway: info?.Gateway || '-',
			mac: info?.MacAddress || '-',
		}));
	}

	async function copyRaw() {
		if (!data) return;
		try {
			await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			/* clipboard 권한 없음 — 무시 */
		}
	}
</script>

<section class="panel">
	<div class="panel-header slim">
		<div>
			<h2>현재 컨테이너 상태 (Inspect)</h2>
		</div>
	</div>

	{#if errorMsg}
		<StateBox kind="error" message={errorMsg} />
	{:else if loading}
		<StateBox kind="loading" message="Inspect 불러오는 중..." />
	{:else if !data}
		<StateBox kind="empty" message="아직 데이터가 없습니다." icon="🛈" />
	{:else}
		<div class="grid">
			<!-- Health & Lifecycle -->
			<div class="card">
				<span class="card-title">상태 / 라이프사이클</span>
				<div class="status-line">
					<span class="badge {healthBadge.tone}">{healthBadge.text}</span>
					{#if data.state?.health?.failingStreak}
						<span class="badge warn">실패 streak {data.state.health.failingStreak}</span>
					{/if}
				</div>
				<dl>
					<div><dt>시작 시각</dt><dd>{formatDateTime(data.state?.startedAt)}</dd></div>
					{#if data.state?.finishedAt && data.state.finishedAt !== '0001-01-01T00:00:00Z'}
						<div><dt>종료 시각</dt><dd>{formatDateTime(data.state.finishedAt)}</dd></div>
					{/if}
					<div><dt>재시작 횟수</dt><dd>{data.restartCount ?? 0}</dd></div>
					{#if typeof data.state?.exitCode === 'number'}
						<div><dt>종료 코드</dt><dd class:bad={data.state.exitCode !== 0}>{data.state.exitCode}</dd></div>
					{/if}
					{#if data.state?.pid}
						<div><dt>PID</dt><dd class="mono">{data.state.pid}</dd></div>
					{/if}
				</dl>
			</div>

			<!-- Network -->
			<div class="card">
				<span class="card-title">네트워크</span>
				{#if networkRows.length > 0}
					<dl>
						{#each networkRows as net}
							<div><dt>{net.name}</dt><dd class="mono">{net.ip}{#if net.gateway !== '-'} · gw {net.gateway}{/if}</dd></div>
						{/each}
					</dl>
				{:else}
					<p class="empty">연결된 네트워크가 없습니다.</p>
				{/if}
				{#if portRows.length > 0}
					<div class="subsection">
						<span class="sub-title">포트 매핑 (현재)</span>
						<dl>
							{#each portRows as port}
								<div><dt class="mono">{port.container}</dt><dd class="mono">{port.bindings}</dd></div>
							{/each}
						</dl>
					</div>
				{/if}
			</div>

			<!-- Mounts -->
			<div class="card">
				<span class="card-title">Mount / Volume</span>
				{#if mounts.length > 0}
					<ul class="mount-list">
						{#each mounts as m}
							<li>
								<span class="mount-type">{m.type || '-'}</span>
								<span class="mono">{m.source || '?'}</span>
								<span class="arrow">→</span>
								<span class="mono">{m.destination || '?'}</span>
								<span class="mount-mode">{m.mode || (m.rw === false ? 'ro' : 'rw')}</span>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="empty">mount 가 없습니다.</p>
				{/if}
			</div>

			<!-- Image / Config -->
			<div class="card">
				<span class="card-title">이미지 / 설정</span>
				<dl>
					<div><dt>이미지</dt><dd class="mono">{data.image || '-'}</dd></div>
					{#if data.config?.workingDir}
						<div><dt>워킹 디렉터리</dt><dd class="mono">{data.config.workingDir}</dd></div>
					{/if}
					{#if data.config?.entrypoint && data.config.entrypoint.length > 0}
						<div><dt>Entrypoint</dt><dd class="mono">{data.config.entrypoint.join(' ')}</dd></div>
					{/if}
					{#if data.config?.cmd && data.config.cmd.length > 0}
						<div><dt>Command</dt><dd class="mono">{data.config.cmd.join(' ')}</dd></div>
					{/if}
					<div><dt>환경 변수</dt><dd>{envCount}개</dd></div>
				</dl>
			</div>
		</div>

		<div class="raw">
			<button class="raw-toggle" onclick={() => (rawOpen = !rawOpen)}>
				{rawOpen ? '▾' : '▸'} Raw inspect JSON
			</button>
			{#if rawOpen}
				<div class="raw-actions">
					<button class="raw-copy" onclick={copyRaw}>{copied ? '복사됨' : '복사'}</button>
				</div>
				<pre class="raw-json">{JSON.stringify(data, null, 2)}</pre>
			{/if}
		</div>
	{/if}
</section>

<style>
	.panel {
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		border-radius: var(--radius-panel);
		padding: clamp(6px, 0.6vw, 14px);
		margin-top: 18px;
		transition: border-color var(--ease-fast);
		display: flex;
		flex-direction: column;
		min-height: 0;
	}
	.panel:hover {
		border-color: rgba(48, 213, 200, 0.22);
	}
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: clamp(8px, 0.8vw, 16px);
		margin-bottom: clamp(4px, 0.4vw, 10px);
	}
	h2 {
		font-size: 20px;
		margin-bottom: 4px;
	}
	.panel-header p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.state-row {
		padding: 16px;
		border-radius: 12px;
		background: rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
		font-size: 13px;
		color: var(--text-secondary);
	}
	.state-row.error {
		color: #fecaca;
		border-color: rgba(239, 68, 68, 0.3);
		background: rgba(127, 29, 29, 0.18);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: clamp(6px, 0.5vw, 10px);
		/* parent panel 이 area-inspect 셀 안에서 flex column 으로 동작. grid 가
		   panel 의 남은 공간 자동 fill + 내부 overflow. */
		flex: 1 1 0;
		min-height: 0;
		overflow-y: auto;
	}

	.card {
		padding: clamp(8px, 0.7vw, 14px) clamp(10px, 0.8vw, 16px);
		border-radius: var(--radius-panel);
		background: rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
	}

	.card-title {
		display: block;
		font-size: 11px;
		color: var(--text-muted);
		margin-bottom: 10px;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	.status-line {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
		margin-bottom: 10px;
	}

	.badge {
		display: inline-flex;
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 700;
	}
	.badge.success {
		background: rgba(16, 185, 129, 0.18);
		color: #34d399;
		border: 1px solid rgba(16, 185, 129, 0.35);
	}
	.badge.warn {
		background: rgba(234, 179, 8, 0.18);
		color: #fde047;
		border: 1px solid rgba(234, 179, 8, 0.35);
	}
	.badge.danger {
		background: rgba(239, 68, 68, 0.18);
		color: #fca5a5;
		border: 1px solid rgba(239, 68, 68, 0.4);
	}
	.badge.muted {
		background: rgba(100, 116, 139, 0.16);
		color: var(--text-secondary);
		border: 1px solid rgba(100, 116, 139, 0.32);
	}

	dl {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	dl > div {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		font-size: 12px;
		padding-bottom: 6px;
		border-bottom: 1px solid rgba(31, 41, 55, 0.6);
	}
	dl > div:last-child {
		border-bottom: none;
	}
	dt {
		color: var(--text-secondary);
		flex-shrink: 0;
	}
	dd {
		color: var(--text-primary);
		text-align: right;
		word-break: break-all;
	}
	dd.bad {
		color: #fca5a5;
		font-weight: 700;
	}
	.mono {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		/* path / UUID / env value 처럼 공백 없는 긴 token 도 카드 안에서 줄바꿈. */
		word-break: break-all;
		overflow-wrap: anywhere;
		min-width: 0;
	}

	.subsection {
		margin-top: 12px;
		padding-top: 10px;
		border-top: 1px dashed rgba(100, 116, 139, 0.2);
	}
	.sub-title {
		display: block;
		font-size: 11px;
		color: var(--text-muted);
		margin-bottom: 6px;
	}

	.mount-list {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.mount-list li {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
		align-items: center;
		font-size: 12px;
		padding-bottom: 6px;
		border-bottom: 1px solid rgba(31, 41, 55, 0.6);
		min-width: 0;
		max-width: 100%;
		word-break: break-all;
		overflow-wrap: anywhere;
	}

	.mount-list .mono {
		flex: 1 1 auto;
		min-width: 0;
		max-width: 100%;
	}
	.mount-list li:last-child {
		border-bottom: none;
	}
	.mount-type {
		font-size: 10px;
		font-weight: 700;
		text-transform: uppercase;
		padding: 2px 6px;
		border-radius: 6px;
		background: rgba(48, 213, 200, 0.12);
		color: var(--accent);
	}
	.arrow {
		color: var(--text-muted);
	}
	.mount-mode {
		margin-left: auto;
		font-size: 10px;
		color: var(--text-muted);
		text-transform: uppercase;
	}

	.empty {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.raw {
		margin-top: 14px;
	}

	.raw-toggle {
		background: transparent;
		border: none;
		color: var(--text-secondary);
		cursor: pointer;
		font-family: inherit;
		font-size: 12px;
		font-weight: 700;
		padding: 4px 0;
	}
	.raw-toggle:hover {
		color: var(--accent);
	}

	.raw-actions {
		margin: 6px 0;
	}
	.raw-copy {
		padding: 5px 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-secondary);
		font-family: inherit;
		font-size: 11px;
		font-weight: 700;
		cursor: pointer;
	}
	.raw-copy:hover {
		color: var(--accent);
		border-color: rgba(48, 213, 200, 0.4);
	}

	.raw-json {
		max-height: clamp(120px, 16vh, 300px);
		overflow: auto;
		padding: 12px;
		border-radius: 10px;
		background: rgba(2, 6, 12, 0.7);
		border: 1px solid rgba(31, 41, 55, 0.7);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 11px;
		line-height: 1.45;
		color: #cbd5e1;
		white-space: pre;
	}

	@media (max-width: 980px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
