<script lang="ts">
  // 운영 중 모델 — 마켓 공유 여부 inline 표시.
  // 카드 X, 표 형식.
  import type { MountedModel } from '$lib/mock/gpu-hosting';

  interface Props {
    items: MountedModel[];
    onMarketClick: (name: string) => void;
  }
  const { items, onMarketClick }: Props = $props();

  const sorted = $derived([...items].sort((a, b) => {
    const aS = a.marketSharedAt ? 1 : 0;
    const bS = b.marketSharedAt ? 1 : 0;
    if (bS !== aS) return bS - aS;
    return b.marketCalls7d - a.marketCalls7d;
  }));

  function daysAgo(iso: string): string {
    const d = Math.floor((Date.parse('2026-05-26T12:03:00Z') - Date.parse(iso)) / 86400000);
    if (d === 0) return '오늘';
    if (d === 1) return '어제';
    return `${d}일 전`;
  }
</script>

<section class="pane">
  <ul>
    {#each sorted as m (m.modelVersionId)}
      {@const on = m.mountedOn[0]}
      <li>
        <div class="r1">
          <span class="name">{m.modelName}</span>
          {#if m.marketSharedAt}
            <button class="m-btn" type="button" onclick={() => onMarketClick(m.modelName)}>마켓에서 보기 ↗</button>
          {:else}
            <span class="m-private">개인 사용</span>
          {/if}
        </div>
        <div class="r2"><b>{on.user}</b> 님 · <span class="gpu">{on.gpuLabel}</span></div>
        {#if m.marketSharedAt}
          <div class="r3">
            <span>7일 <b>{m.marketCalls7d.toLocaleString()}</b>회</span>
            <span class="dim">{daysAgo(m.marketSharedAt)} 공유</span>
          </div>
        {/if}
      </li>
    {/each}
  </ul>
</section>

<style>
  .pane {
    background: #181d26;
    border: none;
    border-radius: 8px;
    padding: 14px 16px 12px;
    height: 100%;
    min-height: 220px;
    overflow-y: auto;
  }
  ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }
  li { display: grid; gap: 2px; padding-bottom: 8px; border-bottom: 1px dashed var(--border); }
  li:last-child { border-bottom: none; padding-bottom: 0; }

  .r1 { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  .name { color: var(--text-primary); font-weight: 700; font-size: 15px; }
  .m-btn {
    appearance: none; background: none; border: none;
    color: var(--accent); font: inherit; font-size: 11px; font-weight: 600;
    cursor: pointer; padding: 0;
  }
  .m-btn:hover { color: var(--text-primary); }
  .m-private { color: var(--text-muted); font-size: 11px; }

  .r2 { font-size: 12px; color: var(--text-secondary); }
  .r2 b { color: var(--text-primary); font-weight: 700; }
  .gpu { color: var(--accent); }

  .r3 { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); }
  .r3 b { color: var(--text-primary); font-weight: 700; }
  .r3 .dim { color: var(--text-muted); }
</style>
