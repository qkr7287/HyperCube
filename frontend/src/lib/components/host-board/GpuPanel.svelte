<script lang="ts">
  // GPU 한 대 panel — minimal admin console 풍.
  // 게이지 폐기. 작은 metric box + 큰 숫자 + VRAM 가로 막대 (cuda) + slice grid.
  import type { GpuMock, HostMock, MountedModel } from '$lib/mock/gpu-hosting';
  import { INCIDENT_LABEL_KO } from '$lib/mock/gpu-hosting';
  import { effectiveGpuSeverity } from '$lib/utils/gpu-severity';
  import { SEMANTIC_HEX } from '$lib/utils/gpu-palette';
  import SliceCell from './SliceCell.svelte';
  import VramBar from './VramBar.svelte';
  import {
    FLOWER, axialPx, hexPoints, frameOutlinePoints,
    expandSlicesToFlower, sliceUsagePct, heatmapColor,
  } from '$lib/utils/hex-flower';
  import { INCIDENT_LABEL_KO as INC_KO } from '$lib/mock/gpu-hosting';

  // mini hex flower geometry — 좌측 ResourceMap 과 동일 시각 언어.
  const MINI_SIZE = 9;
  const MINI_HEX_POINTS = hexPoints(MINI_SIZE);
  const MINI_FRAME_POINTS = frameOutlinePoints(MINI_SIZE);

  // GPU 의 최대 분할 가능 칸 수 (MIG 7-slice 기준).
  const MAX_SLOTS = 7;

  function relTime(iso: string): string {
    const sec = Math.max(0, Math.floor((Date.parse('2026-05-26T12:03:00Z') - Date.parse(iso)) / 1000));
    if (sec < 60) return `${sec}초 전`;
    if (sec < 3600) return `${Math.floor(sec / 60)}분 전`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}시간 전`;
    return `${Math.floor(sec / 86400)}일 전`;
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
    if (t === null) return '—';
    if (t > 85) return '🔥 뜨거움';
    if (t > 75) return '따뜻함';
    if (t > 60) return '적정';
    return '시원함';
  }
  function utilHint(p: number | null): string {
    if (p === null) return '—';
    if (p >= 90) return '포화';
    if (p >= 70) return '빠듯함';
    if (p >= 30) return '적정';
    return '여유';
  }
  function memHint(p: number): string {
    if (p >= 90) return '가득';
    if (p >= 70) return '빠듯함';
    if (p >= 30) return '적정';
    return '여유';
  }
  function powerHint(w: number | null, cap: number): string {
    if (w === null) return '—';
    const p = (w / cap) * 100;
    if (p >= 90) return '한도 근접';
    if (p >= 70) return '적정';
    return '여유';
  }
  // 한도 대비 % → bar 색 (낮음 teal → 중간 amber → 높음 red)
  function barColor(pct: number, thresh: { warn: number; crit: number }): string {
    if (pct >= thresh.crit) return '#d97070';
    if (pct >= thresh.warn) return '#e0b96b';
    return '#4dbfb3';
  }
</script>

<section class="gpu" data-sev={sev} class:focused data-gpu-id={gpu.id}>
  <header class="head">
    <!-- selected GPU 의 mini hex flower (좌측 자원맵과 동일 시각 — 매핑 명시) -->
    <svg class="mini-flower" viewBox="-32 -32 64 64" aria-hidden="true">
      <defs>
        <pattern id="mini-hatched" patternUnits="userSpaceOnUse" width="3" height="3" patternTransform="rotate(45)">
          <rect width="3" height="3" fill="rgba(255,255,255,0.03)"/>
          <line x1="0" y1="0" x2="0" y2="3" stroke="rgba(255,255,255,0.22)" stroke-width="0.7"/>
        </pattern>
      </defs>
      <polygon class="mini-frame" points={MINI_FRAME_POINTS} data-sev={sev} />
      {#each expandSlicesToFlower(gpu) as c, i (i)}
        {@const allocated = !!(c.slice && c.slice.containerId)}
        {@const isUnalloc = !c.slice}
        {@const pct = c.slice ? sliceUsagePct(c.slice) : 0}
        {@const off = axialPx(FLOWER[i], MINI_SIZE)}
        {@const fillColor = isUnalloc ? 'url(#mini-hatched)' : heatmapColor(pct, allocated, sev)}
        <polygon
          class="mini-hex"
          class:unalloc={isUnalloc}
          transform="translate({off.x}, {off.y})"
          points={MINI_HEX_POINTS}
          fill={fillColor}
        />
      {/each}
    </svg>
    <div class="head-text">
      <div class="line">
        <span class="dot" style="background: {SEMANTIC_HEX[sev]};" aria-hidden="true"></span>
        <h2>{gpu.label}</h2>
        <span class="meta">{gpu.model} · {gpu.mode === 'mig' ? `MIG ${gpu.slices.length}슬라이스` : '전체'}</span>
        {#if gpu.incident}<span class="incident">{INCIDENT_LABEL_KO[gpu.incident]}</span>{/if}
      </div>
      <p class="summary">{summary}</p>
    </div>
  </header>

  <!-- Metric strip — Grafana stat panel 풍, 적당 크기 -->
  <div class="metrics">
    <div class="m">
      <div class="m-top"><span class="m-label">지금 작업률</span><span class="m-sub">GPU Util</span></div>
      <div class="m-row">
        <span class="m-val" style="color: {SEMANTIC_HEX[sev]};">
          {gpu.computePct ?? '—'}{gpu.computePct !== null ? '%' : ''}
        </span>
        <!-- lucide: cpu -->
        <svg class="m-mark" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="4" y="4" width="16" height="16" rx="2" />
          <rect x="9" y="9" width="6" height="6" />
          <path d="M9 2v2 M15 2v2 M9 20v2 M15 20v2 M2 9h2 M2 15h2 M20 9h2 M20 15h2" />
        </svg>
      </div>
      <div class="m-bar"><span class="m-fill" style="width: {gpu.computePct ?? 0}%; background: {barColor(gpu.computePct ?? 0, { warn: 70, crit: 90 })};"></span></div>
      <span class="m-foot"><b>{utilHint(gpu.computePct)}</b> · p95 {gpu.computePctP95_1h ?? '—'}%</span>
    </div>
    <div class="m">
      <div class="m-top"><span class="m-label">메모리</span><span class="m-sub">VRAM</span></div>
      <div class="m-row">
        <span class="m-val">{Math.round(vramPct)}<small>%</small></span>
        <!-- lucide: memory-stick -->
        <svg class="m-mark" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M2 7a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v1.1a2 2 0 0 0 0 3.8V17a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-5.1a2 2 0 0 0 0-3.8Z" />
          <path d="M2 15h20 M6 19v-3 M10 19v-3 M14 19v-3 M18 19v-3 M8 11V9 M12 11V9 M16 11V9" />
        </svg>
      </div>
      <div class="m-bar"><span class="m-fill" style="width: {vramPct}%; background: {barColor(vramPct, { warn: 70, crit: 90 })};"></span></div>
      <span class="m-foot"><b>{memHint(vramPct)}</b> · {gpu.vramUsedGB} / {gpu.vramTotalGB} GB</span>
    </div>
    <div class="m">
      <div class="m-top"><span class="m-label">온도</span><span class="m-sub">Temp</span></div>
      <div class="m-row">
        <span class="m-val">{gpu.tempC ?? '—'}<small>{gpu.tempC !== null ? '°C' : ''}</small></span>
        <!-- lucide: thermometer -->
        <svg class="m-mark" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z" />
        </svg>
      </div>
      <div class="m-bar"><span class="m-fill" style="width: {Math.min(100, ((gpu.tempC ?? 0) / 95) * 100)}%; background: {barColor(((gpu.tempC ?? 0) / 95) * 100, { warn: 75, crit: 90 })};"></span></div>
      <span class="m-foot"><b>{tempHint(gpu.tempC)}</b> · 한도 95°C</span>
    </div>
    <div class="m">
      <div class="m-top"><span class="m-label">전력</span><span class="m-sub">Power</span></div>
      <div class="m-row">
        <span class="m-val">{gpu.powerW ?? '—'}<small>{gpu.powerW !== null ? 'W' : ''}</small></span>
        <!-- lucide: zap -->
        <svg class="m-mark" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" />
        </svg>
      </div>
      <div class="m-bar"><span class="m-fill" style="width: {Math.min(100, ((gpu.powerW ?? 0) / gpu.powerCapW) * 100)}%; background: {barColor(((gpu.powerW ?? 0) / gpu.powerCapW) * 100, { warn: 70, crit: 90 })};"></span></div>
      <span class="m-foot"><b>{powerHint(gpu.powerW, gpu.powerCapW)}</b> · 한도 {gpu.powerCapW} W</span>
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
        <div class="s-wrap" style="grid-column: span {gpu.mode === 'whole' ? 1 : s.profileWeight};">
          <SliceCell slice={s} {mountedModels} {onContainerClick} {onMarketClick} />
        </div>
      {/each}
      {#if gpu.mode === 'whole'}
        {#each Array(MAX_SLOTS - gpu.slices.length) as _, i (i)}
          <div class="s-wrap s-unalloc" aria-hidden="true"></div>
        {/each}
      {/if}
    </div>
  </div>

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
    <!-- column header: tbody scroll 밖으로 분리 — scrollbar 가 header 아래부터 시작 -->
    <div class="r-col-head" role="row">
      <div></div>
      <div>시간</div>
      <div>이벤트</div>
      <div>메시지</div>
      <div>조치</div>
    </div>
    <div class="r-tbl-scroll">
      <table class="r-tbl">
        <colgroup>
          <col style="width: 28px;" />
          <col style="width: 70px;" />
          <col style="width: 200px;" />
          <col />
          <col style="width: 130px;" />
        </colgroup>
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
    </div>
    {/if}
  </div>
</section>

<style>
  .gpu {
    padding: 14px 0 0;
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 12px;
    position: relative;
    height: 100%;
    min-height: 0;
  }
  .gpu.focused::before {
    content: '';
    position: absolute;
    left: -10px; top: 14px; bottom: 18px;
    width: 2px;
    background: var(--error);
  }
  .gpu:first-child { border-top: none; padding-top: 2px; }

  .head {
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .head-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; flex: 1; }
  .mini-flower {
    width: 64px;
    height: 64px;
    flex-shrink: 0;
  }
  .mini-frame {
    fill: none;
    stroke: rgba(255, 255, 255, 0.55);
    stroke-width: 2;
    stroke-linejoin: round;
  }
  .mini-frame[data-sev='warn']    { stroke: #e0b96b; }
  .mini-frame[data-sev='error']   { stroke: #d97070; }
  .mini-frame[data-sev='offline'] { stroke: #475569; stroke-dasharray: 4 3; }
  .mini-hex {
    stroke: rgba(13, 17, 23, 0.9);
    stroke-width: 0.8;
  }
  .mini-hex.unalloc {
    stroke: rgba(255, 255, 255, 0.06);
    stroke-width: 0.3;
  }
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
    grid-template-columns: repeat(4, minmax(0, 1fr));
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
    border-top: 1px solid rgba(77, 191, 179, 0.18);
    position: relative;
  }
  .m::before {
    content: '';
    position: absolute;
    top: -1px; left: 0;
    width: 28px;
    height: 1px;
    background: var(--accent);
    opacity: 0.6;
  }
  .m-top { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
  .m-label { color: var(--text-primary); font-size: 14px; font-weight: 700; }
  .m-sub { color: var(--text-muted); font-size: 11px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }
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
  .m-foot { color: var(--text-muted); font-size: 12px; }
  .m-foot b { color: var(--text-primary); font-weight: 700; }
  .m-bar {
    height: 4px;
    background: rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    overflow: hidden;
    margin: 2px 0;
  }
  .m-fill {
    display: block;
    height: 100%;
    transition: width 0.25s, background 0.25s;
    border-radius: 2px;
  }
  .m-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    min-width: 0;
    padding-right: 6px; /* icon 이 우측 끝에서 살짝 안쪽 */
  }
  .m-mark {
    width: 30px;
    height: 30px;
    flex-shrink: 0;
    fill: none;
    stroke: var(--accent);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
    opacity: 0.55;
  }

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
  /* Whole GPU 의 분할 안 된 자리 — 빗금 표시 */
  .s-wrap.s-unalloc {
    background:
      repeating-linear-gradient(
        45deg,
        rgba(255, 255, 255, 0.03),
        rgba(255, 255, 255, 0.03) 6px,
        rgba(255, 255, 255, 0.10) 6px,
        rgba(255, 255, 255, 0.10) 7px
      ),
      #14181f;
  }

  .recent {
    padding: 14px 0 0 16px;
    background: #181d26;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
  .r-tbl-scroll {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    scrollbar-gutter: stable;
    scroll-snap-type: y proximity;
    padding-right: 16px;
  }
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
  .r-head {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 0 16px 8px 0;
    border-bottom: 1px solid var(--border);
  }
  .r-title { color: var(--text-primary); font-size: 14px; font-weight: 700; }
  .r-en { color: var(--text-muted); font-size: 12px; font-weight: 500; }
  .r-hint { margin-left: auto; color: var(--text-muted); font-size: 12px; }
  .r-empty { margin: 0; color: var(--text-muted); font-size: 13px; }
  .r-tbl { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 13px; }
  /* tbody-scroll 위 별도 header row (div grid) — table colgroup 과 동일 width */
  .r-col-head {
    display: grid;
    grid-template-columns: 28px 70px 200px 1fr 130px;
    padding: 8px 16px 8px 0;
    border-bottom: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 700;
  }
  .r-col-head > div { padding: 0 10px; }
  .r-col-head > div:first-child { padding: 0; }
  .r-tbl thead { display: none; }
  .r-tbl thead th {
    text-align: left;
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 700;
    background: #181d26;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
  }
  .r-tbl tbody tr { scroll-snap-align: start; }
  .r-tbl tbody td {
    padding: 10px 10px;
    border-bottom: 1px dashed var(--border);
    vertical-align: middle;
    height: 44px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .r-tbl tbody td:first-child,
  .r-tbl thead th:first-child {
    overflow: visible;
    padding: 10px 0 10px 4px;
    text-align: center;
    background: #181d26;
  }
  .r-tbl tbody tr:last-child td { border-bottom: none; }
  .r-tbl tbody tr:hover td { background: rgba(77, 191, 179, 0.04); }
  .r-tbl .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
  .r-tbl .t-time { color: var(--text-muted); font-variant-numeric: tabular-nums; font-size: 12px; }
  .r-tbl .t-kind { color: var(--text-primary); font-weight: 700; font-size: 13px; }
  .r-tbl .t-msg { color: var(--text-secondary); font-size: 13px; line-height: 1.5; }
  .r-tbl .t-act { text-align: right; }
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
