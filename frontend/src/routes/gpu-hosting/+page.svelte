<script lang="ts">
  // GPU Hosting v8 — 빈 종이에서 통째로 재작성.
  // 좋은 점 spec 만 유지: 단일 서버 집중 + 자연어 + 마켓 chip + IncidentPane + chip click focus.
  // 새 시각 언어: 카드 → section divider, chip 최소화, typography hierarchy 강화, monospace 활용.
  // NON-runes (`+page.svelte`) — `let` + `$:`.
  import { onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';
  import { goto } from '$app/navigation';
  import AdminHeader from '$lib/components/AdminHeader.svelte';
  import HostHeader from '$lib/components/host-board/HostHeader.svelte';
  import SectionTitle from '$lib/components/host-board/SectionTitle.svelte';
  import GpuCompareCards from '$lib/components/host-board/GpuCompareCards.svelte';
  import GpuPanel from '$lib/components/host-board/GpuPanel.svelte';
  import UsageRank from '$lib/components/host-board/UsageRank.svelte';
  import MarketServices from '$lib/components/host-board/MarketServices.svelte';
  import {
    HOSTS,
    GPUS,
    MOUNTED_MODELS,
    jitterGpus,
    deriveUserUsage,
    type GpuMock,
  } from '$lib/mock/gpu-hosting';
  import { effectiveGpuSeverity } from '$lib/utils/gpu-severity';

  let liveGpus: GpuMock[] = GPUS;
  let intervalMs = 5000;
  let timerId: ReturnType<typeof setInterval> | undefined;
  let toastMessage: string | null = null;
  let toastTimer: ReturnType<typeof setTimeout> | undefined;

  let selectedServer: string = HOSTS[0].id;
  let manualGpuId: string | null = null;

  function selectGpu(id: string) { manualGpuId = id; }

  function startInterval(ms: number) {
    if (timerId) clearInterval(timerId);
    intervalMs = ms;
    timerId = setInterval(() => { liveGpus = jitterGpus(liveGpus); }, ms);
  }
  function showToast(msg: string) {
    toastMessage = msg;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toastMessage = null), 4500);
  }
  function handleContainerClick(id: string) {
    showToast(`${id} 컨테이너 상세 페이지 이동은 다음 단계에서 활성됩니다.`);
  }
  function handleMarketClick(name: string) {
    showToast(`${name} 의 마켓플레이스 페이지 이동은 다음 단계에서 활성됩니다.`);
  }

  $: host = HOSTS.find((h) => h.id === selectedServer)!;
  $: serverGpus = liveGpus.filter((g) => g.hostId === selectedServer);
  $: visibleMounted = MOUNTED_MODELS.filter((m) => serverGpus.some((g) => g.label === m.mountedOn[0]?.gpuLabel));

  $: selectedGpuId = manualGpuId ?? serverGpus[0]?.id ?? null;
  $: selectedGpu = serverGpus.find((g) => g.id === selectedGpuId) ?? serverGpus[0] ?? null;

  $: userUsage = deriveUserUsage(serverGpus);

  // 호스트 status 한 줄.
  $: hostStatus = (() => {
    if (!host.isOnline) {
      return { tone: 'error' as const, text: `에이전트 응답 없음 ${Math.floor(host.staleSec / 60)}분 ${host.staleSec % 60}초 · 하위 GPU 사용 불가` };
    }
    if (host.staleSec > 60) {
      return { tone: 'warn' as const, text: `응답 지연 ${host.staleSec}초` };
    }
    const sevs = serverGpus.map((g) => effectiveGpuSeverity(g, host));
    const err = sevs.filter((s) => s === 'error').length;
    if (err > 0) return { tone: 'error' as const, text: `GPU ${serverGpus.length}대 중 ${err}대 장애 · 점검 필요` };
    const warn = sevs.filter((s) => s === 'warn').length;
    if (warn > 0) return { tone: 'warn' as const, text: `GPU ${serverGpus.length}대 작동 · ${warn}대 주의` };
    return { tone: 'ok' as const, text: `GPU ${serverGpus.length}대 모두 정상 작동 중` };
  })();

  onMount(() => startInterval(5000));
  onDestroy(() => {
    if (timerId) clearInterval(timerId);
    if (toastTimer) clearTimeout(toastTimer);
  });
</script>

<svelte:head>
  <title>{host?.location ?? 'GPU'} · 호스팅 현황 - HyperCube</title>
</svelte:head>

<div class="shell">
<AdminHeader username="admin" />

<main class="page">
  <!-- Top utility bar — back, server selector, live rate -->
  <nav class="util">
    <button class="back" type="button" onclick={() => goto(`${base}/server-2d`)}>← Docker 화면</button>
    <div class="server-pick">
      <label for="server-select">호스트</label>
      <select id="server-select" value={selectedServer} onchange={(e) => (selectedServer = (e.currentTarget as HTMLSelectElement).value)}>
        {#each HOSTS as h (h.id)}
          <option value={h.id}>{h.location} · {h.hostname} · GPU {liveGpus.filter(g => g.hostId === h.id).length}대 {h.isOnline ? '' : '(오프라인)'}</option>
        {/each}
      </select>
    </div>
    <div class="rate" role="radiogroup" aria-label="갱신 주기">
      <span class="live"><span class="live-dot"></span>실시간</span>
      {#each [{ ms: 1000, lbl: '1초' }, { ms: 5000, lbl: '5초' }, { ms: 60000, lbl: '1분' }] as r}
        <button type="button" class:active={intervalMs === r.ms} onclick={() => startInterval(r.ms)} aria-pressed={intervalMs === r.ms}>{r.lbl}</button>
      {/each}
    </div>
  </nav>

  <!-- Host header — 자연어 status + inline insight -->
  <HostHeader {host} statusTone={hostStatus.tone} statusText={hostStatus.text} />

  <!-- Main split: 좌 800px (비교 + 사이드 4 panel) / 우 나머지 (선택 GPU 1대 상세) -->
  <section class="main">
    <div class="left">
      <!-- ① 비교 카드 -->
      <div class="section">
        <SectionTitle no={1} title="전체 GPU 한눈에 비교" en="All GPUs at a glance" hint="카드 클릭 = 우측 상세 보기" />
        <GpuCompareCards gpus={serverGpus} {host} {selectedGpuId} onSelect={selectGpu} />
      </div>

      <!-- ③④ 2 column grid (장애 상세 / 활동 로그 폐기 — 우측 GpuPanel 안에 흡수됨) -->
      <div class="grid-2">
        <div class="section">
          <SectionTitle no={3} title="누가 얼마나 쓰나" en="User Allocation" hint={`${userUsage.length}명`} />
          <UsageRank items={userUsage} />
        </div>
        <div class="section">
          <SectionTitle no={4} title="운영 중인 서비스" en="Running Services" hint={`${visibleMounted.filter((m) => m.marketSharedAt).length}개 마켓 공유`} />
          <MarketServices items={visibleMounted} onMarketClick={handleMarketClick} />
        </div>
      </div>
    </div>

    <div class="right">
      <div class="section">
        <SectionTitle no={5} title="선택한 GPU 상세" en="Selected GPU Detail" hint={selectedGpu?.label ?? ''} />
        {#if selectedGpu}
          <GpuPanel
            gpu={selectedGpu}
            {host}
            mountedModels={MOUNTED_MODELS}
            onMarketClick={handleMarketClick}
            onContainerClick={handleContainerClick}
          />
        {:else}
          <p class="empty">GPU 가 없습니다.</p>
        {/if}
      </div>
    </div>
  </section>
</main>
</div>

{#if toastMessage}
  <div class="toast" role="status" aria-live="polite">
    <span>{toastMessage}</span>
    <button class="t-close" type="button" onclick={() => (toastMessage = null)} aria-label="Close">×</button>
  </div>
{/if}

<style>
  .shell { height: 100vh; display: flex; flex-direction: column; background: var(--bg-base); }
  .page {
    flex: 1; min-height: 0;
    overflow: hidden;
    padding: 12px 22px 28px;
    display: flex; flex-direction: column;
    color: var(--text-primary);
  }
  .page > :global(*) { flex-shrink: 0; min-width: 0; }

  .util {
    display: flex;
    align-items: center;
    gap: 14px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }
  .back {
    background: transparent; border: none;
    color: var(--text-secondary);
    font: inherit; font-size: 12px;
    padding: 4px 0;
    cursor: pointer;
  }
  .back:hover { color: var(--accent); }

  .server-pick {
    flex: 1;
    display: inline-flex; align-items: center; gap: 8px;
  }
  .server-pick label {
    color: var(--text-muted); font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em;
  }
  .server-pick select {
    background: transparent; color: var(--text-primary); border: none;
    font: inherit; font-size: 13px; font-weight: 600; cursor: pointer;
    border-bottom: 1px dashed var(--border);
    padding: 2px 4px;
  }
  .server-pick select:hover { border-bottom-color: var(--accent); }

  .rate {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 11px;
  }
  .live {
    display: inline-flex; align-items: center; gap: 4px;
    color: var(--accent); font-weight: 700;
    padding: 0 8px;
  }
  .live-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--accent); animation: pulse 1.6s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .rate button {
    background: transparent; border: none;
    color: var(--text-muted); font: inherit; font-size: 11px;
    padding: 4px 8px;
    cursor: pointer;
    border-radius: 4px;
  }
  .rate button:hover { color: var(--text-primary); }
  .rate button.active { color: var(--accent); font-weight: 700; }

  .main {
    display: grid;
    grid-template-columns: 800px minmax(0, 1fr);
    gap: 18px;
    align-items: stretch;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
  .left { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
  .left > .section:first-child { flex: 0 0 auto; }
  .left > .grid-2 { flex: 1; min-height: 0; }
  .grid-2 > .section { display: flex; flex-direction: column; min-height: 0; }
  .grid-2 > .section > :global(*:last-child) { flex: 1; min-height: 0; }
  .right {
    display: flex; flex-direction: column; gap: 16px;
    min-width: 0;
  }
  .right > .section { flex: 1; }
  .right > .section > :global(*:last-child) { flex: 1; }
  .section { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .empty { color: var(--text-muted); padding: 40px; text-align: center; }

  .toast {
    position: fixed; bottom: 20px; right: 20px;
    background: var(--bg-card); border: 1px solid var(--warn); color: var(--text-primary);
    padding: 10px 14px; border-radius: 8px;
    display: inline-flex; align-items: center; gap: 10px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5); max-width: 460px; font-size: 13px; z-index: 200;
  }
  .t-close { background: transparent; border: none; color: var(--text-muted); font-size: 16px; cursor: pointer; padding: 0 4px; }
  .t-close:hover { color: var(--text-primary); }

  @media (max-width: 1500px) {
    .main { grid-template-columns: 1fr; }
    .right { position: static; }
    .grid-2 { grid-template-columns: 1fr 1fr; }
  }
</style>
