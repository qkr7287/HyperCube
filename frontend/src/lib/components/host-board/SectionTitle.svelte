<script lang="ts">
  // 통일된 section 제목 — 영역 구분 명확.
  // 큰 한국어 + 작은 영문 + 우측 hint + border-bottom.
  interface Props {
    no?: number;
    title: string;
    en?: string;
    hint?: string;
  }
  const { no, title, en = '', hint = '' }: Props = $props();
</script>

<header class="st">
  <div class="left">
    {#if no !== undefined}<span class="no">{no}</span>{/if}
    <h3>{title}</h3>
    {#if en}<span class="en">{en}</span>{/if}
  </div>
  {#if hint}<span class="hint">{hint}</span>{/if}
</header>

<style>
  .st {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0 12px;
    border-bottom: 2px solid var(--border);
    margin-bottom: 6px;
  }
  .left { display: flex; align-items: center; gap: 12px; min-width: 0; }
  .no {
    width: 28px; height: 28px;
    display: inline-flex; align-items: center; justify-content: center;
    background: var(--bg-card);
    color: var(--accent);
    border: 1px solid var(--accent);
    border-radius: 6px;
    font-size: 14px;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }
  h3 {
    margin: 0;
    font-size: 20px;
    font-weight: 800;
    color: var(--text-primary);
    letter-spacing: -0.01em;
  }
  .en {
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 500;
  }
  .hint {
    color: var(--text-muted);
    font-size: 12px;
  }
</style>
