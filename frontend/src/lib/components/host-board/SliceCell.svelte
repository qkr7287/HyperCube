<script lang="ts">
  // 슬라이스 1칸. 카드가 아닌 작은 분할 셀.
  // 칩 폐기, 모든 정보 텍스트 + 색만.
  import type { SliceMock, MountedModel } from '$lib/mock/gpu-hosting';
  import { SEMANTIC_HEX } from '$lib/utils/gpu-palette';

  interface Props {
    slice: SliceMock;
    mountedModels: MountedModel[];
    onContainerClick: (id: string) => void;
    onMarketClick: (name: string) => void;
  }
  const { slice, mountedModels, onContainerClick, onMarketClick }: Props = $props();

  const filled = $derived(slice.containerId !== null);
  const idle = $derived(slice.qualityState === 'idle_waste');
  const sat = $derived(slice.qualityState === 'saturation');
  const market = $derived(
    slice.model ? mountedModels.find((m) => m.modelVersionId === slice.model!.versionId) ?? null : null
  );
  const accent = $derived(idle || sat ? SEMANTIC_HEX.warn : filled ? SEMANTIC_HEX.ok : SEMANTIC_HEX.offline);
</script>

<div class="cell" class:filled class:dim={!filled} style="--accent-line: {accent}">
  <div class="top">
    <span class="prof">{slice.profile}</span>
    {#if idle}<span class="note">10분 안 씀</span>{:else if sat}<span class="note">포화</span>{/if}
  </div>
  {#if filled}
    <div class="who">{slice.user?.name}</div>
    <button class="model" type="button" onclick={() => onMarketClick(slice.model!.name)}>
      {slice.model?.name}
      {#if market?.marketSharedAt}<span class="shared" aria-label="마켓 공유">↗</span>{/if}
    </button>
    <button class="cont" type="button" onclick={() => onContainerClick(slice.containerId!)}>{slice.containerId}</button>
    <div class="m">
      <span class="m-k">작업</span><span class="m-v">{slice.computePct ?? '—'}{slice.computePct !== null ? '%' : ''}</span>
      <span class="m-k">VRAM</span><span class="m-v">{slice.vramUsedGB}<small>/{slice.vramTotalGB}</small></span>
    </div>
  {:else}
    <div class="empty">
      <span class="e-title">비어 있음</span>
      <span class="e-sub">신청 가능 · {slice.vramTotalGB} GB</span>
    </div>
  {/if}
</div>

<style>
  .cell {
    border-left: 2px solid var(--accent-line);
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
    background: transparent;
  }
  .cell.dim { opacity: 0.65; }

  .top { display: flex; justify-content: space-between; align-items: baseline; }
  .prof {
    color: var(--text-muted);
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 11px;
  }
  .note {
    color: var(--warn);
    font-size: 10px;
    font-weight: 600;
  }

  .who { color: var(--text-primary); font-weight: 700; font-size: 14px; }
  .model {
    appearance: none; background: none; border: none; padding: 0;
    color: var(--accent); font: inherit; font-size: 13px; cursor: pointer;
    text-align: left;
    display: inline-flex; align-items: baseline; gap: 4px;
  }
  .model:hover { color: var(--text-primary); }
  .shared { font-size: 11px; color: var(--accent); }
  .cont {
    appearance: none; background: none; border: none; padding: 0;
    color: var(--text-muted); font: inherit; font-size: 11px;
    font-family: "JetBrains Mono", Consolas, monospace;
    cursor: pointer; text-align: left;
    text-decoration: underline dotted;
  }
  .cont:hover { color: var(--text-secondary); }

  .m {
    display: grid;
    grid-template-columns: auto 1fr auto 1fr;
    gap: 6px;
    margin-top: 4px;
    font-size: 11px;
  }
  .m-k { color: var(--text-muted); }
  .m-v { color: var(--text-primary); font-weight: 700; font-variant-numeric: tabular-nums; }
  .m-v small { color: var(--text-muted); font-weight: 500; }

  .empty {
    display: flex; flex-direction: column; gap: 1px;
    color: var(--text-muted);
    padding: 6px 0;
  }
  .e-title { font-size: 13px; font-weight: 600; color: var(--text-secondary); }
  .e-sub { font-size: 11px; }
</style>
