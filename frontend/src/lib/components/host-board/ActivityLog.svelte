<script lang="ts">
  // 자연어 활동 로그 — 카드 X, 표 형식.
  import type { EventMock } from '$lib/mock/gpu-hosting';
  import { INCIDENT_LABEL_KO } from '$lib/mock/gpu-hosting';
  import { SEMANTIC_HEX } from '$lib/utils/gpu-palette';

  interface Props {
    events: EventMock[];
  }
  const { events }: Props = $props();

  const sorted = $derived([...events].sort((a, b) => b.ts.localeCompare(a.ts)));

  function relTime(iso: string): string {
    const sec = Math.max(0, Math.floor((Date.parse('2026-05-26T12:03:00Z') - Date.parse(iso)) / 1000));
    if (sec < 60) return `${sec}초 전`;
    if (sec < 3600) return `${Math.floor(sec / 60)}분 전`;
    return `${Math.floor(sec / 3600)}시간 전`;
  }
</script>

<section class="pane">
  <ul>
    {#each sorted as e (e.ts + e.kind)}
      <li>
        <span class="dot" style="background: {SEMANTIC_HEX[e.severity]};" aria-hidden="true"></span>
        <div class="body">
          <div class="r1">
            <time>{relTime(e.ts)}</time>
            <span class="kind">{INCIDENT_LABEL_KO[e.kind] ?? e.kind}</span>
            {#if e.gpuId}<span class="tag">{e.gpuId}</span>{:else if e.hostId}<span class="tag">{e.hostId}</span>{:else if e.requestId}<span class="tag">{e.requestId}</span>{/if}
          </div>
          <p class="msg">{e.message}</p>
        </div>
      </li>
    {/each}
  </ul>
</section>

<style>
  .pane {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px 12px;
    height: 220px;
    overflow-y: auto;
    overflow: hidden;
  }
  ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
  li {
    display: grid;
    grid-template-columns: 10px 1fr;
    gap: 10px;
    padding-bottom: 6px;
    border-bottom: 1px dashed var(--border);
  }
  li:last-child { border-bottom: none; }
  .dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; }
  .body { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .r1 { display: flex; gap: 8px; align-items: baseline; font-size: 13px; flex-wrap: wrap; }
  time { color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .kind { color: var(--text-primary); font-weight: 700; font-size: 12px; }
  .tag {
    color: var(--accent);
    background: rgba(77, 191, 179, 0.10);
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 4px;
    font-family: "JetBrains Mono", Consolas, monospace;
  }
  .msg { margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.5; }
</style>
