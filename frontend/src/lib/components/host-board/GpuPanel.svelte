<script lang="ts">
  // GPU 한 대 panel — minimal admin console 풍.
  // 게이지 폐기. 작은 metric box + 큰 숫자 + VRAM 가로 막대 (cuda) + slice grid.
  import type { GpuMock, HostMock, MountedModel } from '$lib/mock/gpu-hosting';
  import { INCIDENT_LABEL_KO } from '$lib/mock/gpu-hosting';
  import { effectiveGpuSeverity } from '$lib/utils/gpu-severity';
  import { SEMANTIC_HEX, identityColor } from '$lib/utils/gpu-palette';
  import SparkLine from './SparkLine.svelte';
  import SliceCell from './SliceCell.svelte';
  import VramBar from './VramBar.svelte';
  import GpuTrendCharts from './GpuTrendCharts.svelte';
  import { INCIDENT_LABEL_KO as INC_KO } from '$lib/mock/gpu-hosting';

  // GPU 의 최대 분할 가능 칸 수 (MIG 7-slice 기준).
  const MAX_SLOTS = 7;

  function relTime(iso: string): string {
    const sec = Math.max(0, Math.floor((Date.parse('2026-05-26T12:03:00Z') - Date.parse(iso)) / 1000));
    if (sec < 60) return `${sec}초 전`;
    if (sec < 3600) return `${Math.floor(sec / 60)}분 전`;
    return `${Math.floor(sec / 3600)}시간 전`;
  }

  interface Props {
    gpu: GpuMock;
    host: HostMock;
    mountedModels: MountedModel[];
    focused?: boolean;
    onMarketClick: (name: string) => void;
    onContainerClick: (id: string) => void;
  }
  const { gpu, host, mountedModels, focused = false, onMarketClick, onContainerClick }: Props = $props();

  const sev = $derived(effectiveGpuSeverity(gpu, host));
  const vramPct = $derived(gpu.vramTotalGB > 0 ? (gpu.vramUsedGB / gpu.vramTotalGB) * 100 : 0);
  const allocSlices = $derived(gpu.slices.filter((s) => s.containerId !== null).length);

  const users = $derived.by(() => {
    const m = new Map<string, Set<string>>();
    for (const s of gpu.slices) {
      if (s.user) {
        if (!m.has(s.user.name)) m.set(s.user.name, new Set());
        if (s.model) m.get(s.user.name)!.add(s.model.name);
      }
    }
    return Array.from(m.entries());
  });

  const summary = $derived.by(() => {
    if (sev === 'offline') return '호스트 응답 없음 · 사용 불가';
    if (sev === 'error') return `${gpu.incident ? INCIDENT_LABEL_KO[gpu.incident] : '문제'} · 점검 필요`;
    if (users.length === 0) return '아무도 사용하지 않음 · 신청 받을 수 있음';
    return users.map(([u, models]) => `${u} 님이 ${Array.from(models).join(', ')}`).join(' · ');
  });

  function tempHint(t: number | null): string {
    if (t === null) return '';
    if (t > 80) return '뜨거움';
    if (t > 70) return '따뜻함';
    return '시원함';
  }
</script>

<section class="gpu" data-sev={sev} class:focused data-gpu-id={gpu.id}>
  <header class="head">
    <div class="line">
      <span class="dot" style="background: {SEMANTIC_HEX[sev]};" aria-hidden="true"></span>
      <h2>{gpu.label}</h2>
      <span class="meta">{gpu.model} · {gpu.mode === 'mig' ? `MIG ${gpu.slices.length}슬라이스` : '전체'}</span>
      {#if gpu.incident}<span class="incident">{INCIDENT_LABEL_KO[gpu.incident]}</span>{/if}
    </div>
    <p class="summary">{summary}</p>
  </header>

  <!-- Metric strip — Grafana stat panel 풍, 적당 크기 -->
  <div class="metrics">
    <div class="m m-hero">
      <div class="m-top"><span class="m-label">지금 작업률</span><span class="m-sub">GPU Util</span></div>
      <div class="m-mid">
        <span class="m-val" style="color: {SEMANTIC_HEX[sev]};">
          {gpu.computePct ?? '—'}{gpu.computePct !== null ? '%' : ''}
        </span>
        <SparkLine values={gpu.sparkline60s} width={110} height={22} stroke={identityColor(gpu.id)} label="GPU {gpu.label} 60s" />
      </div>
      <span class="m-foot">p95 {gpu.computePctP95_1h ?? '—'}%</span>
    </div>
    <div class="m">
      <div class="m-top"><span class="m-label">메모리</span><span class="m-sub">VRAM</span></div>
      <span class="m-val">{Math.round(vramPct)}<small>%</small></span>
      <span class="m-foot">{gpu.vramUsedGB} / {gpu.vramTotalGB} GB</span>
    </div>
    <div class="m">
      <div class="m-top"><span class="m-label">온도</span><span class="m-sub">Temp</span></div>
      <span class="m-val">{gpu.tempC ?? '—'}<small>{gpu.tempC !== null ? '°C' : ''}</small></span>
      <span class="m-foot">{tempHint(gpu.tempC)}</span>
    </div>
    <div class="m">
      <div class="m-top"><span class="m-label">전력</span><span class="m-sub">Power</span></div>
      <span class="m-val">{gpu.powerW ?? '—'}<small>{gpu.powerW !== null ? 'W' : ''}</small></span>
      <span class="m-foot">한도 {gpu.powerCapW} W</span>
    </div>
  </div>

  <!-- VRAM 가로 막대 (cuda_monitoring 풍) -->
  <div class="vram-row">
    <div class="vr-key">VRAM 사용량</div>
    <VramBar usedGB={gpu.vramUsedGB} totalGB={gpu.vramTotalGB} height={16} />
  </div>

  <!-- 슬라이스 -->
  <div class="slices">
    <div class="s-head">
      <span class="s-title">슬라이스 분할</span>
      <span class="s-stat">
        {gpu.mode === 'mig' ? `MIG · ${gpu.slices.length} 분할` : '전체 (Whole)'}
        · 사용 <b>{allocSlices}</b> / {gpu.slices.length}
      </span>
    </div>
    <div class="s-grid" style="--max: {MAX_SLOTS}">
      {#each gpu.slices as s (s.id)}
        <div class="s-wrap" style="grid-column: span {s.profileWeight};">
          <SliceCell slice={s} {mountedModels} {onContainerClick} {onMarketClick} />
        </div>
      {/each}
    </div>
  </div>

  <!-- 60초 시계열 차트 (VRAM / Temp / Power) -->
  <GpuTrendCharts {gpu} />

  <!-- 이 GPU 의 최근 활동 — 테이블 + 액션 -->
  <div class="recent">
    <div class="r-head">
      <span class="r-title">이 GPU 의 최근 활동</span>
      <span class="r-en">Recent Events</span>
      <span class="r-hint">{gpu.recentEvents.length}건</span>
    </div>
    {#if gpu.recentEvents.length === 0}
      <p class="r-empty">최근 기록된 이벤트가 없습니다.</p>
    {:else}
      <table class="r-tbl">
        <thead>
          <tr>
            <th class="thx"></th>
            <th class="thx">시간</th>
            <th>이벤트</th>
            <th>메시지</th>
            <th class="thx">조치</th>
          </tr>
        </thead>
        <tbody>
          {#each gpu.recentEvents as e (e.ts + e.kind)}
            <tr>
              <td><span class="dot" style="background: {SEMANTIC_HEX[e.severity]};" aria-hidden="true"></span></td>
              <td class="t-time">{relTime(e.ts)}</td>
              <td class="t-kind">{INC_KO[e.kind] ?? e.kind}</td>
              <td class="t-msg">{e.message}</td>
              <td class="t-act">
                {#if e.containerId}
                  <button class="act-btn" type="button" onclick={() => onContainerClick(e.containerId!)}>컨테이너 보기 →</button>
                {:else if e.severity === 'error'}
                  <button class="act-btn primary" type="button" onclick={() => onContainerClick(`investigate-${gpu.id}`)}>원인 분석 →</button>
                {:else}
                  <span class="act-dim">—</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</section>

<style>
  .gpu {
    padding: 14px 0 18px;
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 12px;
    position: relative;
    height: 100%;
  }
  .gpu.focused::before {
    content: '';
    position: absolute;
    left: -10px; top: 14px; bottom: 18px;
    width: 2px;
    background: var(--error);
  }
  .gpu:first-child { border-top: none; padding-top: 2px; }

  .head { display: flex; flex-direction: column; gap: 3px; }
  .line { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  .dot { width: 9px; height: 9px; border-radius: 50%; align-self: center; }
  h2 {
    margin: 0;
    font-size: 24px;
    font-weight: 800;
    color: var(--text-primary);
    letter-spacing: -0.02em;
  }
  .meta { color: var(--text-muted); font-size: 13px; }
  .incident {
    color: var(--error);
    background: rgba(217, 112, 112, 0.14);
    padding: 1px 7px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
  }
  .summary {
    margin: 0;
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.55;
  }
  .gpu[data-sev='error'] .summary { color: var(--error); }

  .metrics {
    display: grid;
    grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
    gap: 1px;
    background: var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  .m {
    background: #181d26;
    padding: 12px 14px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }
  .m-top { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; }
  .m-label { color: var(--text-primary); font-size: 14px; font-weight: 700; }
  .m-sub { color: var(--text-muted); font-size: 12px; font-weight: 500; }
  .m-val {
    font-size: 36px;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1.05;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
  }
  .m-val small {
    font-size: 15px;
    color: var(--text-muted);
    font-weight: 600;
    margin-left: 2px;
  }
  .m-foot { color: var(--text-muted); font-size: 13px; }
  .m-mid { display: flex; align-items: center; gap: 10px; }

  .vram-row {
    display: grid;
    grid-template-columns: 110px 1fr;
    gap: 14px;
    align-items: center;
    padding: 10px 14px;
    background: #181d26;
    border-radius: 6px;
  }
  .vr-key { color: var(--text-primary); font-size: 14px; font-weight: 700; }

  .slices { display: flex; flex-direction: column; gap: 10px; }
  .s-head { display: flex; align-items: baseline; gap: 10px; }
  .s-title { color: var(--text-primary); font-size: 14px; font-weight: 700; }
  .s-stat { color: var(--text-muted); font-size: 13px; }
  .s-stat b { color: var(--accent); font-weight: 800; font-variant-numeric: tabular-nums; }
  .s-grid {
    display: grid;
    grid-template-columns: repeat(var(--max), minmax(0, 1fr));
    background: var(--border);
    border-radius: 6px;
    overflow: hidden;
    gap: 1px;
    min-height: 130px;
  }
  .s-wrap { background: #181d26; min-width: 0; min-height: 128px; display: flex; }
  .s-wrap > :global(*) { flex: 1; min-height: 100%; }

  .recent {
    padding: 14px 16px 0;
    background: #181d26;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    scrollbar-gutter: stable;
    mask-image: linear-gradient(to bottom, #000 calc(100% - 20px), transparent);
    -webkit-mask-image: linear-gradient(to bottom, #000 calc(100% - 20px), transparent);
  }
  .r-tbl { padding-bottom: 22px; }
  .r-tbl tbody { display: table-row-group; }
  .r-empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    font-size: 13px;
    min-height: 240px;
  }
  .r-head { display: flex; align-items: baseline; gap: 8px; }
  .r-title { color: var(--text-primary); font-size: 14px; font-weight: 700; }
  .r-en { color: var(--text-muted); font-size: 12px; font-weight: 500; }
  .r-hint { margin-left: auto; color: var(--text-muted); font-size: 12px; }
  .r-empty { margin: 0; color: var(--text-muted); font-size: 13px; }
  .r-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
  .r-tbl thead th {
    text-align: left;
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 700;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
  }
  .r-tbl th.thx { width: 1%; white-space: nowrap; }
  .r-tbl tbody td {
    padding: 10px 10px;
    border-bottom: 1px dashed var(--border);
    vertical-align: middle;
  }
  .r-tbl tbody tr:last-child td { border-bottom: none; }
  .r-tbl tbody tr:hover td { background: rgba(77, 191, 179, 0.04); }
  .r-tbl .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
  .r-tbl .t-time { color: var(--text-muted); font-variant-numeric: tabular-nums; white-space: nowrap; font-size: 12px; }
  .r-tbl .t-kind { color: var(--text-primary); font-weight: 700; white-space: nowrap; font-size: 13px; }
  .r-tbl .t-msg { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; max-width: 440px; font-size: 13px; line-height: 1.5; }
  .r-tbl .t-act { white-space: nowrap; text-align: right; }
  .act-btn {
    appearance: none;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-secondary);
    font: inherit;
    font-size: 12px;
    font-weight: 600;
    padding: 5px 12px;
    border-radius: 9999px;
    cursor: pointer;
    transition: color 0.12s, border-color 0.12s, background 0.12s;
  }
  .act-btn:hover { color: var(--accent); border-color: var(--accent); }
  .act-btn.primary {
    color: var(--error);
    border-color: rgba(217, 112, 112, 0.4);
    background: rgba(217, 112, 112, 0.08);
  }
  .act-btn.primary:hover { color: #fff; background: var(--error); border-color: var(--error); }
  .act-dim { color: var(--text-muted); font-size: 11px; }

  @media (max-width: 1340px) {
    .metrics { grid-template-columns: 1fr 1fr; }
  }
</style>
