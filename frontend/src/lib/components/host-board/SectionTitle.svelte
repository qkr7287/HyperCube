<script lang="ts">
  // 통일된 section 제목 — 영역 구분 명확.
  // 큰 한국어 + 작은 영문 + 우측 hint + ? 아이콘 (호버 tooltip) + border-bottom.
  interface Props {
    no?: number;
    title: string;
    en?: string;
    hint?: string;
    tooltip?: string;
  }
  const { no, title, en = '', hint = '', tooltip = '' }: Props = $props();
</script>

<header class="st">
  <div class="left">
    {#if no !== undefined}<span class="no">{no}</span>{/if}
    <h3>{title}</h3>
    {#if en}<span class="en">{en}</span>{/if}
    {#if tooltip}
      <span class="help" tabindex="0" aria-label="도움말">
        ?
        <span class="tip" role="tooltip">{tooltip}</span>
      </span>
    {/if}
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
  .help {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 700;
    cursor: help;
    outline: none;
    transition: background 0.12s, color 0.12s;
  }
  .help:hover, .help:focus { background: var(--accent); color: #fff; }
  .tip {
    position: absolute;
    top: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    background: #0d1117;
    border: 1px solid var(--accent);
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-primary);
    line-height: 1.5;
    white-space: pre-line;
    min-width: 220px;
    max-width: 320px;
    opacity: 0;
    pointer-events: none;
    transform-origin: top center;
    transition: opacity 0.12s;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.6);
    z-index: 50;
  }
  .tip::before {
    content: '';
    position: absolute;
    top: -5px;
    left: 50%;
    transform: translateX(-50%) rotate(45deg);
    width: 8px;
    height: 8px;
    background: #0d1117;
    border-left: 1px solid var(--accent);
    border-top: 1px solid var(--accent);
  }
  .help:hover .tip,
  .help:focus .tip { opacity: 1; }
</style>
