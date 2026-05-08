/**
 * 컨테이너 라이프사이클 이벤트 (kind) 의 시각 표현 / 차트 markLine 매핑.
 * EventList.svelte 와 차트 markLine 호출처가 같은 색을 쓰도록 단일 source.
 */

export type EventKind =
	| 'start'
	| 'stop'
	| 'die'
	| 'restart'
	| 'pause'
	| 'unpause'
	| 'kill'
	| 'oom'
	| 'health_status';

export type EventRow = {
	id: number;
	ts: string;
	kind: string;
	exit_code?: number | null;
	signal?: string;
	health_status?: string;
};

export const EVENT_KIND_META: Record<string, { label: string; color: string }> = {
	start:         { label: '시작',     color: '#10b981' },
	stop:          { label: '중지',     color: '#f59e0b' },
	die:           { label: '종료',     color: '#fb923c' },
	restart:       { label: '재시작',   color: '#3b82f6' },
	pause:         { label: '일시정지', color: '#eab308' },
	unpause:       { label: '재개',     color: '#10b981' },
	kill:          { label: '강제종료', color: '#ef4444' },
	oom:           { label: 'OOM',      color: '#ef4444' },
	health_status: { label: 'Health',   color: '#06b6d4' },
};

export function eventColor(kind: string): string {
	return EVENT_KIND_META[kind]?.color || '#94a3b8';
}

export function eventLabel(kind: string): string {
	return EVENT_KIND_META[kind]?.label || kind;
}
