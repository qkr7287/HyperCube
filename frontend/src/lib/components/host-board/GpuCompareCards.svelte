<script lang="ts">
  // GPU 비교 카드 그리드 — 표 대신 시각 카드.
  // 한 화면에 모든 GPU 의 상태 + 작업률 + 메모리 + 사용자.
  // 카드 클릭 시 우측 detail panel 갱신.
  import type { GpuMock, HostMock } from '$lib/mock/gpu-hosting';
  import { INCIDENT_LABEL_KO } from '$lib/mock/gpu-hosting';
  import { effectiveGpuSeverity } from '$lib/utils/gpu-severity';
  import { SEMANTIC_HEX } from '$lib/utils/gpu-palette';

  interface Props {
    gpus: GpuMock[];
    host: HostMock;
    selectedGpuId: string | null;
    onSelect: (id: string) => void;
  }
  const { gpus, host, selectedGpuId, onSelect }: Props = $props();

  function usersOf(g: GpuMock): string[] {
    const s = new Set<string>();
    for (const sl of g.slices) if (sl.user) s.add(sl.user.name);
    return Array.from(s);
  }
</script>

<div class="grid">
  {#each gpus as g (g.id)}
    {@const sev = effectiveGpuSeverity(g, host)}
    {@const vp = g.vramTotalGB > 0 ? Math.round((g.vramUsedGB / g.vramTotalGB) * 100) : 0}
    {@const cp = g.computePct ?? 0}
    {@const users = usersOf(g)}
    {@const isSelected = selectedGpuId === g.id}
    <button
      class="card"
      class:selected={isSelected}
      data-sev={sev}
      type="button"
      onclick={() => onSelect(g.id)}
      aria-pressed={isSelected}
    >
      <header class="hd">
        <span class="dot" style="background: {SEMANTIC_HEX[sev]};" aria-hidden="true"></span>
        <span class="name">{g.label}</span>
        <span class="modetag">{g.model}·{g.mode === 'mig' ? 'MIG' : 'W'}</span>
        {#if g.incident}<span class="inc">{INCIDENT_LABEL_KO[g.incident]}</span>{/if}
      </header>

      <div class="metric">
        <div class="m-row">
          <span class="m-key">작업률</span>
          {#if g.computePct !== null}
            <span class="m-val" style="color: {SEMANTIC_HEX[sev]};">{cp}<small>%</small></span>
          {:else}<span class="m-val dim">—</span>{/if}
        </div>
        <div class="bar"><span class="fill" style="width: {cp}%; background: {SEMANTIC_HEX[sev]};"></span></div>

        <div class="m-row">
          <span class="m-key">메모리</span>
          {#if g.vramTotalGB > 0}<span class="m-val">{vp}<small>%</small></span>{:else}<span class="m-val dim">—</span>{/if}
        </div>
        <div class="bar"><span class="fill" style="width: {vp}%; background: #fb923c;"></span></div>
      </div>

      <footer class="ft">
        <span class="aux">
          <span>슬라이스 <b>{g.slices.filter((s) => s.containerId !== null).length}</b>/{g.slices.length}</span>
          {#if g.tempC !== null}<span>·</span><span>{g.tempC}°C</span>{/if}
        </span>
        <span class="users">{users.length === 0 ? '—' : users.join(', ')}</span>
      </footer>
    </button>
  {/each}
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    grid-auto-rows: 120px;
    gap: 8px;
    /* padding(16) + 2 rows(240) + 1 row-gap(8) = 264px → 6 카드 한 세트로 fit */
    height: 264px;
    overflow-y: auto;
    padding: 8px;
    background: #131820;
    border-radius: 8px;
    align-content: start;
  }
  .grid::-webkit-scrollbar { width: 6px; }
  .grid::-webkit-scrollbar-thumb { background: rgba(100, 116, 139, 0.3); border-radius: 3px; }
  .grid::-webkit-scrollbar-track { background: transparent; }
  .card {
    appearance: none;
    background: #181d26;
    border: none;
    border-left: 3px solid var(--offline);
    border-radius: 6px;
    padding: 10px 12px;
    color: var(--text-primary);
    font: inherit;
    text-align: left;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 6px;
    min-width: 0;
    height: 120px;
    overflow: hidden;
    transition: border-color 0.12s, background 0.12s;
  }
  .card:hover { background: #11161e; }
  .card.selected {
    border-color: var(--accent);
    background: rgba(77, 191, 179, 0.08);
    box-shadow: 0 0 0 1px var(--accent);
  }
  .card[data-sev='ok']      { border-left-color: var(--accent); }
  .card[data-sev='warn']    { border-left-color: var(--warn); }
  .card[data-sev='error']   { border-left-color: var(--error); }
  .card[data-sev='offline'] { border-left-color: var(--offline); opacity: 0.85; }

  .hd { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .name { color: var(--text-primary); font-weight: 700; font-size: 14px; }
  .modetag {
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 10px;
    color: var(--text-muted);
    background: var(--tag-bg);
    padding: 1px 6px;
    border-radius: 3px;
  }
  .inc {
    color: var(--error);
    background: rgba(217, 112, 112, 0.18);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 700;
  }

  .metric { display: grid; gap: 3px; }
  .m-row { display: flex; justify-content: space-between; align-items: baseline; font-size: 11px; }
  .m-key { color: var(--text-muted); font-weight: 600; }
  .m-val { font-size: 18px; font-weight: 800; color: var(--text-primary); font-variant-numeric: tabular-nums; line-height: 1; }
  .m-val small { font-size: 10px; color: var(--text-muted); font-weight: 600; margin-left: 1px; }
  .m-val.dim { color: var(--text-muted); }
  .bar {
    height: 4px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 2px;
    overflow: hidden;
  }
  .fill { display: block; height: 100%; }

  .ft {
    display: flex; justify-content: space-between; gap: 8px;
    font-size: 10px;
    color: var(--text-muted);
    padding-top: 4px;
    border-top: 1px dashed var(--border);
  }
  .aux { display: inline-flex; gap: 4px; }
  .aux b { color: var(--text-primary); font-weight: 700; }
  .users { color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 60%; }
</style>
