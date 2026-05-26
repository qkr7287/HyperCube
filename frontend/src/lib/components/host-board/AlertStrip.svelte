<script lang="ts">
  // 한 줄 incident strip. 직접 클릭 으로 detail focus 갱신.
  // 카드 없음 — 텍스트 기반 줄.
  import type { Insight } from '$lib/mock/gpu-hosting';

  interface Props {
    actions: Insight[];
    focusedIdx: number;
    onSelect: (idx: number) => void;
  }
  const { actions, focusedIdx, onSelect }: Props = $props();
</script>

{#if actions.length > 0}
  <div class="strip alert">
    <span class="lead-dot" aria-hidden="true">●</span>
    <span class="lead">처리할 일 <b>{actions.length}건</b></span>
    <div class="items" role="tablist">
      {#each actions as a, i (i)}
        <button
          class="item"
          class:focused={focusedIdx === i}
          type="button"
          role="tab"
          aria-selected={focusedIdx === i}
          onclick={() => onSelect(i)}
        >
          <span class="seq">{i + 1}</span>
          <span class="title">{a.title}</span>
        </button>
      {/each}
    </div>
  </div>
{/if}

<style>
  .strip {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 14px;
    background: var(--bg-card);
    border-radius: 8px;
    border: 1px solid var(--border);
    border-left-width: 3px;
    flex-wrap: wrap;
  }

  .alert { border-left-color: var(--error); }
  @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .lead-dot { color: var(--error); font-size: 10px; animation: blink 1.4s ease-in-out infinite; }
  .lead { color: var(--text-secondary); font-size: 13px; }
  .lead b { color: var(--error); font-weight: 700; }

  .items {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    min-width: 0;
  }
  .item {
    appearance: none;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-secondary);
    font: inherit;
    font-size: 12px;
    padding: 4px 12px 4px 4px;
    border-radius: 9999px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: border-color 0.12s, background 0.12s, color 0.12s;
  }
  .item:hover { color: var(--text-primary); border-color: rgba(217, 112, 112, 0.5); }
  .item.focused {
    color: var(--text-primary);
    border-color: var(--error);
    background: rgba(217, 112, 112, 0.10);
  }
  .seq {
    width: 18px; height: 18px;
    display: inline-flex; align-items: center; justify-content: center;
    background: rgba(217, 112, 112, 0.18);
    color: var(--error);
    border-radius: 9999px;
    font-size: 10px;
    font-weight: 800;
  }
  .item.focused .seq { background: var(--error); color: #fff; }
  .title { font-weight: 600; }
</style>
