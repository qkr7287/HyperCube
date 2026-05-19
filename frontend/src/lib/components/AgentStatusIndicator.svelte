<!--
  AgentStatusIndicator — 단일 agent 의 online/offline + last_seen 상대시간 표시.

  AgentStatusBadge (admin 헤더, 전체 fleet 단위) 와 달리 컨테이너 상세 hero meta
  안에서 inline 으로 쓰는 작은 단위. activeAgentIds store + last_seen 상대시간
  으로 판단.

  online dot — accent 색
  stale (5분~) dot — warn 노랑
  offline dot — error 빨강
-->
<script lang="ts">
	import { activeAgentIds } from '$lib/stores/global-events';
	import { formatRelativeTime } from '$lib/utils/container-dashboard';

	let {
		agentId,
		hostname,
		lastSeen,
	}: {
		agentId: string | null | undefined;
		hostname: string | null | undefined;
		lastSeen: string | null | undefined;
	} = $props();

	const STALE_SECONDS = 5 * 60; // 5 minutes

	let now = $state(Date.now());

	// 30초마다 relative time 갱신
	$effect(() => {
		const id = setInterval(() => {
			now = Date.now();
		}, 30_000);
		return () => clearInterval(id);
	});

	let secondsSince = $derived.by(() => {
		if (!lastSeen) return Number.POSITIVE_INFINITY;
		const t = new Date(lastSeen).getTime();
		if (!Number.isFinite(t)) return Number.POSITIVE_INFINITY;
		return Math.max(0, Math.floor((now - t) / 1000));
	});
	// online 판단: global event store 우선, 비어있으면 last_seen 2분 이내면 online 가정.
	// (사용자 페이지 globalWS 연결이 늦거나 backend 가 transition event 못 보낸 케이스,
	//  메트릭 폴링이 잠깐 지연되는 경우까지 흡수 — 120s 안전마진)
	let online = $derived.by(() => {
		if (agentId && $activeAgentIds.has(agentId)) return true;
		return secondsSince < 120;
	});
	let stale = $derived(online && secondsSince >= STALE_SECONDS);
	let relative = $derived(formatRelativeTime(lastSeen));

	let level = $derived(!online ? 'offline' : stale ? 'stale' : 'online');
	let levelLabel = $derived(
		level === 'offline' ? '오프라인' : level === 'stale' ? '동기화 지연' : '온라인',
	);
</script>

<span class="agent-indicator" data-level={level} title={`${hostname ?? '-'} · ${levelLabel} · ${relative}`}>
	<span class="dot" aria-hidden="true"></span>
	<span class="host">{hostname ?? '-'}</span>
	<span class="sep" aria-hidden="true">·</span>
	<span class="meta">{levelLabel} · {relative}</span>
</span>

<style>
	.agent-indicator {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 3px 8px;
		border-radius: var(--radius-full);
		background: rgba(13, 17, 23, 0.62);
		border: 1px solid var(--border);
		font-size: 11px;
		font-weight: 700;
		color: var(--text-secondary);
		line-height: 1.4;
		white-space: nowrap;
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--text-muted);
		box-shadow: 0 0 0 2px rgba(13, 17, 23, 0.6);
	}

	.agent-indicator[data-level='online'] {
		border-color: rgba(48, 213, 200, 0.35);
		color: var(--text-primary);
	}
	.agent-indicator[data-level='online'] .dot {
		background: var(--accent);
		box-shadow: 0 0 0 2px rgba(48, 213, 200, 0.18);
	}

	.agent-indicator[data-level='stale'] {
		border-color: rgba(251, 191, 36, 0.4);
		color: #fde68a;
	}
	.agent-indicator[data-level='stale'] .dot {
		background: #fbbf24;
		box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.18);
	}

	.agent-indicator[data-level='offline'] {
		border-color: rgba(239, 68, 68, 0.4);
		color: #fca5a5;
	}
	.agent-indicator[data-level='offline'] .dot {
		background: #ef4444;
		box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.18);
	}

	.host {
		font-weight: 800;
	}

	.sep {
		color: var(--text-muted);
		font-weight: 500;
	}

	.meta {
		font-weight: 600;
	}
</style>
