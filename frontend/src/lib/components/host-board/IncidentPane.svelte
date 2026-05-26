<script lang="ts">
  // AlertStrip 의 선택 항목에 대한 detail.
  // 영향 GPU / 호스트 / 사용자 / 서비스 / 권장 조치 / 원인 단서.
  import type { Insight, GpuMock, HostMock, EventMock } from '$lib/mock/gpu-hosting';
  import { INCIDENT_LABEL_KO } from '$lib/mock/gpu-hosting';
  import { SEMANTIC_HEX } from '$lib/utils/gpu-palette';

  interface Props {
    insight: Insight | null;
    gpus: GpuMock[];
    host: HostMock | null;
    events: EventMock[];
  }
  const { insight, gpus, host, events }: Props = $props();

  const targetGpu = $derived(insight?.target?.gpuId ? gpus.find((g) => g.id === insight.target!.gpuId) ?? null : null);

  const affectedUsers = $derived.by(() => {
    if (!targetGpu) return [];
    const s = new Set<string>();
    for (const sl of targetGpu.slices) if (sl.user) s.add(sl.user.name);
    return Array.from(s);
  });
  const affectedModels = $derived.by(() => {
    if (!targetGpu) return [];
    const s = new Set<string>();
    for (const sl of targetGpu.slices) if (sl.model) s.add(sl.model.name);
    return Array.from(s);
  });
  const causeEvent = $derived.by(() => {
    if (!insight) return null;
    return events.find((e) =>
      (insight.target?.gpuId && e.gpuId === insight.target.gpuId) ||
      (!targetGpu && host && e.hostId === host.id)
    ) ?? null;
  });

  function formatTs(iso: string): string { return iso.slice(11, 16); }
</script>

<section class="pane" data-tone={insight ? 'alert' : 'ok'}>
  <div class="pane-head">
    <span class="ph-tag">{insight ? '긴급' : '정상'}</span>
    <h3>{insight?.title ?? '처리할 일 없음'}</h3>
    <p>{insight?.detail ?? '이 서버는 안정적으로 운영 중입니다.'}</p>
  </div>

  {#if insight}
    <dl class="info">
      {#if targetGpu}
        <div class="row"><dt>영향 GPU</dt><dd><b>{targetGpu.label}</b> <small>{targetGpu.model} · {targetGpu.mode === 'mig' ? 'MIG' : 'Whole'}</small></dd></div>
      {/if}
      {#if host}
        <div class="row"><dt>호스트</dt><dd>{host.location} <small>{host.hostname}</small></dd></div>
      {/if}
      <div class="row"><dt>영향 사용자</dt><dd class:muted={affectedUsers.length === 0}>{affectedUsers.length === 0 ? '없음 (할당된 사용자 없음)' : affectedUsers.join(', ')}</dd></div>
      {#if affectedModels.length}
        <div class="row"><dt>영향 서비스</dt><dd>{affectedModels.join(', ')}</dd></div>
      {/if}
      {#if insight.target?.reqId}
        <div class="row"><dt>신청 번호</dt><dd class="mono">{insight.target.reqId}</dd></div>
      {/if}
    </dl>

    {#if insight.action}
      <div class="rec">
        <span class="rec-key">권장 조치</span>
        <span class="rec-val">{insight.action}</span>
      </div>
    {/if}

    {#if causeEvent}
      <div class="cause">
        <span class="c-key">원인 단서</span>
        <p class="c-line">
          <time>{formatTs(causeEvent.ts)}</time>
          <span class="c-kind" style="color: {SEMANTIC_HEX[causeEvent.severity]};">{INCIDENT_LABEL_KO[causeEvent.kind] ?? causeEvent.kind}</span>
          <span class="c-msg">{causeEvent.message}</span>
        </p>
      </div>
    {/if}
  {/if}
</section>

<style>
  .pane {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    border-left-width: 3px;
    padding: 0;
    display: flex;
    flex-direction: column;
    height: 220px;
    overflow-y: auto;
  }
  .pane[data-tone='alert'] { border-left-color: var(--error); }
  .pane[data-tone='ok']    { border-left-color: var(--accent); }

  .pane-head { padding: 14px 16px 12px; border-bottom: 1px solid var(--border); }
  .ph-tag {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 700;
    margin-bottom: 6px;
  }
  .pane[data-tone='alert'] .ph-tag { background: rgba(217, 112, 112, 0.18); color: var(--error); }
  .pane[data-tone='ok']    .ph-tag { background: rgba(77, 191, 179, 0.16); color: var(--accent); }
  h3 { margin: 0 0 4px; font-size: 15px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.005em; }
  p { margin: 0; font-size: 12.5px; color: var(--text-secondary); line-height: 1.5; }

  .info { margin: 0; padding: 10px 16px; border-bottom: 1px solid var(--border); display: grid; gap: 6px; }
  .row {
    display: grid;
    grid-template-columns: 92px 1fr;
    gap: 10px;
    font-size: 12.5px;
  }
  dt { color: var(--text-muted); font-weight: 600; font-size: 12px; margin: 0; }
  dd { color: var(--text-primary); margin: 0; }
  dd b { font-weight: 700; }
  dd small { color: var(--text-muted); font-size: 11px; margin-left: 2px; }
  dd.muted { color: var(--text-muted); }
  dd.mono { font-family: "JetBrains Mono", Consolas, monospace; font-size: 12px; }

  .rec { padding: 10px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: baseline; gap: 10px; }
  .rec-key { color: var(--text-muted); font-size: 12px; font-weight: 600; }
  .rec-val { color: var(--accent); font-size: 13px; font-weight: 700; }

  .cause { padding: 10px 16px; display: flex; flex-direction: column; gap: 4px; }
  .c-key { color: var(--text-muted); font-size: 12px; font-weight: 600; }
  .c-line { margin: 0; display: flex; gap: 8px; align-items: baseline; font-size: 12px; flex-wrap: wrap; }
  time { color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .c-kind { font-weight: 700; font-size: 11px; }
  .c-msg { color: var(--text-secondary); }
</style>
