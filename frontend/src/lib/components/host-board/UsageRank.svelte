<script lang="ts">
  // 사용자별 점유 ranking — 카드 X, 표 형식.
  import type { UserUsage } from '$lib/mock/gpu-hosting';

  interface Props {
    items: UserUsage[];
  }
  const { items }: Props = $props();

  const maxS = $derived(Math.max(1, ...items.map((u) => u.slicesUsed)));
</script>

<section class="pane">
  <ul>
    {#each items as u (u.name)}
      {@const pct = (u.slicesUsed / maxS) * 100}
      <li>
        <div class="r1">
          <span class="name">{u.name}</span>
          <span class="n">{u.slicesUsed}<small> 슬라이스 · {u.vramUsedGB}GB</small></span>
        </div>
        <div class="bar"><span class="fill" style="width: {pct}%"></span></div>
        <div class="r2">{u.gpus.join(' · ')}</div>
      </li>
    {/each}
  </ul>
</section>

<style>
  .pane {
    background: #181d26;
    border: none;
    border-radius: 8px;
    padding: 14px 16px;
    height: 100%;
    min-height: 220px;
    overflow-y: auto;
    scrollbar-gutter: stable;
    mask-image: linear-gradient(to bottom, #000 calc(100% - 18px), transparent);
    -webkit-mask-image: linear-gradient(to bottom, #000 calc(100% - 18px), transparent);
  }
  ul { list-style: none; padding: 0 0 18px; margin: 0; display: grid; gap: 14px; }
  li { display: grid; gap: 5px; }

  .r1 { display: flex; justify-content: space-between; align-items: baseline; font-size: 14px; }
  .name { color: var(--text-primary); font-weight: 700; }
  .n { color: var(--text-primary); font-weight: 700; font-variant-numeric: tabular-nums; }
  .n small { color: var(--text-muted); font-size: 12px; font-weight: 500; margin-left: 2px; }

  .bar {
    height: 4px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 2px;
    overflow: hidden;
  }
  .fill {
    display: block; height: 100%;
    background: var(--accent);
  }

  .r2 {
    color: var(--text-muted);
    font-size: 11px;
    font-family: "JetBrains Mono", Consolas, monospace;
  }
</style>
