<script lang="ts">
  // Host 의 상태 banner. Status pill 만 — inline insights 는 layout shift 유발해서 제거.
  import type { HostMock } from '$lib/mock/gpu-hosting';

  interface Props {
    host: HostMock;
    statusTone: 'ok' | 'warn' | 'error';
    statusText: string;
  }
  const { host, statusTone, statusText }: Props = $props();
</script>

<header class="hh" data-tone={statusTone}>
  <div class="title-row">
    <div class="loc-block">
      <span class="loc-dot" aria-hidden="true"></span>
      <h1 class="loc">{host.location}</h1>
      <span class="hostname">{host.hostname}</span>
    </div>
    <span class="status">{statusText}</span>
  </div>
</header>

<style>
  .hh {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 4px 0 4px;
  }

  .title-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
  }
  .loc-block { display: flex; align-items: baseline; gap: 10px; min-width: 0; }
  .loc-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--accent);
    align-self: center;
  }
  [data-tone='warn']  .loc-dot { background: var(--warn); }
  [data-tone='error'] .loc-dot { background: var(--error); animation: pulse 1.6s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.55; transform: scale(1.45); } }

  .loc {
    margin: 0;
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--text-primary);
  }
  .hostname {
    color: var(--text-muted);
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 12px;
  }

  .status {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
  }
  [data-tone='warn']  .status { color: var(--warn); }
  [data-tone='error'] .status { color: var(--error); }

</style>
