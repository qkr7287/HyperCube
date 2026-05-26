<script lang="ts">
  // 한 표 안에 모든 GPU 의 metric 비교.
  // 한 행 = GPU. 클릭 시 해당 detail panel 로 scroll.
  import type { GpuMock, HostMock } from '$lib/mock/gpu-hosting';
  import { INCIDENT_LABEL_KO } from '$lib/mock/gpu-hosting';
  import { effectiveGpuSeverity } from '$lib/utils/gpu-severity';
  import { SEMANTIC_HEX } from '$lib/utils/gpu-palette';

  interface Props {
    gpus: GpuMock[];
    host: HostMock;
    focusedGpuId: string | null;
  }
  const { gpus, host, focusedGpuId }: Props = $props();

  function scrollTo(id: string) {
    if (typeof document === 'undefined') return;
    const el = document.querySelector(`[data-gpu-id="${id}"]`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function usersOf(g: GpuMock): string[] {
    const s = new Set<string>();
    for (const sl of g.slices) if (sl.user) s.add(sl.user.name);
    return Array.from(s);
  }
</script>

<div class="tbl" role="table" aria-label="GPU 비교">
  <div class="thead" role="row">
    <span class="th">GPU</span>
    <span class="th">작업률</span>
    <span class="th">메모리</span>
    <span class="th">온도</span>
    <span class="th">전력</span>
    <span class="th">슬라이스</span>
    <span class="th wide">사용자 · 모델</span>
  </div>
  {#each gpus as g (g.id)}
    {@const sev = effectiveGpuSeverity(g, host)}
    {@const vp = g.vramTotalGB > 0 ? (g.vramUsedGB / g.vramTotalGB) * 100 : 0}
    {@const cp = g.computePct ?? 0}
    {@const users = usersOf(g)}
    {@const isFocused = focusedGpuId === g.id}
    <button
      class="row"
      class:focused={isFocused}
      type="button"
      onclick={() => scrollTo(g.id)}
      aria-pressed={isFocused}
    >
      <span class="cell gpu">
        <span class="dot" style="background: {SEMANTIC_HEX[sev]};" aria-hidden="true"></span>
        <span class="name">{g.label}</span>
        <span class="modetag">{g.model}·{g.mode === 'mig' ? 'MIG' : 'Whole'}</span>
        {#if g.incident}<span class="inc">{INCIDENT_LABEL_KO[g.incident]}</span>{/if}
      </span>
      <span class="cell metric">
        {#if g.computePct !== null}
          <span class="bar"><span class="fill" style="width: {cp}%; background: {SEMANTIC_HEX[sev]};"></span></span>
          <span class="num">{g.computePct}%</span>
        {:else}<span class="dim">—</span>{/if}
      </span>
      <span class="cell metric">
        {#if g.vramTotalGB > 0 && g.vramUsedGB > 0}
          <span class="bar"><span class="fill" style="width: {vp}%; background: #fb923c;"></span></span>
          <span class="num">{Math.round(vp)}<small>%</small></span>
        {:else}<span class="dim">—</span>{/if}
      </span>
      <span class="cell num-only">{g.tempC ?? '—'}{g.tempC !== null ? '°' : ''}</span>
      <span class="cell num-only">{g.powerW ?? '—'}{g.powerW !== null ? 'W' : ''}</span>
      <span class="cell num-only"><b>{g.slices.filter((s) => s.containerId !== null).length}</b><small>/{g.slices.length}</small></span>
      <span class="cell users">
        {#if users.length === 0}<span class="dim">—</span>
        {:else}{users.join(', ')}{/if}
      </span>
    </button>
  {/each}
</div>

<style>
  .tbl {
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
    background: #0f1419;
    max-height: 320px;
    overflow-y: auto;
  }
  .thead, .row {
    display: grid;
    grid-template-columns: 210px 160px 130px 70px 80px 80px minmax(0, 1fr);
    align-items: center;
    gap: 14px;
    padding: 12px 18px;
  }
  .thead {
    background: #11161e;
    border-bottom: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 700;
  }
  .row {
    appearance: none;
    background: transparent;
    border: none;
    border-top: 1px solid var(--border);
    color: var(--text-primary);
    font: inherit;
    cursor: pointer;
    text-align: left;
    font-size: 14px;
    transition: background 0.12s;
  }
  .row:first-of-type { border-top: none; }
  .row:hover { background: rgba(77, 191, 179, 0.05); }
  .row.focused { background: rgba(77, 191, 179, 0.10); box-shadow: inset 3px 0 0 var(--accent); }

  .cell { display: flex; align-items: center; gap: 6px; min-width: 0; overflow: hidden; }
  .gpu { gap: 8px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .name { font-weight: 700; color: var(--text-primary); font-size: 15px; white-space: nowrap; }
  .modetag {
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 11px;
    color: var(--text-muted);
    background: var(--tag-bg);
    padding: 2px 7px;
    border-radius: 4px;
    white-space: nowrap;
  }
  .inc {
    color: var(--error);
    background: rgba(217, 112, 112, 0.16);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
  }
  .metric { gap: 10px; }
  .bar {
    flex: 1;
    height: 8px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
    overflow: hidden;
    min-width: 40px;
  }
  .fill { display: block; height: 100%; }
  .num { font-weight: 700; font-variant-numeric: tabular-nums; color: var(--text-primary); white-space: nowrap; font-size: 14px; }
  .num small { color: var(--text-muted); font-weight: 600; font-size: 12px; }
  .num-only {
    color: var(--text-primary);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    font-size: 14px;
  }
  .num-only b { font-weight: 800; color: var(--accent); }
  .num-only small { color: var(--text-muted); font-weight: 500; font-size: 12px; }
  .users {
    color: var(--text-secondary);
    font-size: 13px;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .dim { color: var(--text-muted); }
</style>
