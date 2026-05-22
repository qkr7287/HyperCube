/**
 * 서버 자원 이벤트 — 백엔드 `/api/metrics/resource-events/` 의 프론트 표현.
 *
 * 임계 초과/급증 판정과 라이프사이클((agent, metric) 단위 활성 1건, 생성→지속→
 * 해소/확인)은 백엔드(`apps/metrics/tasks.py` `detect_resource_events`, 1분 주기)가
 * 단일 출처로 수행한다. 이 모듈은 타입·라벨·API 응답 매핑만 담당한다.
 */

export type EventMetric = 'cpu' | 'memory' | 'disk' | 'gpu';
export type FleetEventKind = 'threshold' | 'spike';
export type FleetEventSeverity = 'critical' | 'warning';
export type FleetEventEndedReason = 'resolved' | 'acknowledged';

export type FleetEvent = {
	id: string;
	agentId: string;
	hostname: string;
	metric: EventMetric;
	kind: FleetEventKind;
	severity: FleetEventSeverity;
	/** 최근 판정의 사용률 % */
	value: number;
	/** 구간 내 최대 사용률 % */
	peakValue: number;
	/** spike 증가폭 (%p) — threshold 면 null */
	delta: number | null;
	/** 이벤트 시작 시각 (epoch ms) */
	occurredAt: number;
	/** 종료 시각 (epoch ms) — 진행 중이면 null */
	endedAt: number | null;
	endedReason: FleetEventEndedReason | null;
	isActive: boolean;
	/** 원인 컨테이너 — 미확인이면 null */
	container: { name: string; value: number } | null;
};

const METRIC_LABEL: Record<EventMetric, string> = {
	cpu: 'CPU',
	memory: '메모리',
	disk: '디스크',
	gpu: 'GPU',
};

export function metricLabel(metric: EventMetric): string {
	return METRIC_LABEL[metric] ?? metric;
}

function toEpochMs(iso: string | null | undefined): number | null {
	if (!iso) return null;
	const t = new Date(iso).getTime();
	return Number.isFinite(t) ? t : null;
}

/** 백엔드 ResourceEvent 응답(row) → FleetEvent. */
export function mapResourceEvent(raw: any): FleetEvent {
	return {
		id: String(raw.id),
		agentId: String(raw.server_id ?? ''),
		hostname: String(raw.hostname ?? ''),
		metric: raw.metric,
		kind: raw.kind,
		severity: raw.severity,
		value: Number(raw.last_value ?? 0),
		peakValue: Number(raw.peak_value ?? 0),
		delta: raw.spike_delta == null ? null : Number(raw.spike_delta),
		occurredAt: toEpochMs(raw.started_at) ?? Date.now(),
		endedAt: toEpochMs(raw.ended_at),
		endedReason: raw.ended_reason ?? null,
		isActive: !!raw.is_active,
		container: raw.cause_container_name
			? {
					name: String(raw.cause_container_name),
					value: Number(raw.cause_container_value ?? 0),
				}
			: null,
	};
}
