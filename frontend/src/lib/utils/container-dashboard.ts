import { formatBytes } from '$lib/utils/data-adapter';

export function formatDateTime(value?: string | null): string {
	if (!value) return '-';
	try {
		return new Date(value).toLocaleString('ko-KR');
	} catch {
		return value;
	}
}

export function formatRelativeTime(value?: string | null): string {
	if (!value) return '-';
	try {
		const diff = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
		if (diff < 10) return '방금 전';
		if (diff < 60) return `${diff}초 전`;
		if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
		if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
		return `${Math.floor(diff / 86400)}일 전`;
	} catch {
		return value;
	}
}

export function statusLabel(status?: string | null): string {
	return ({
		running: '실행 중',
		stopped: '중지됨',
		paused: '일시정지',
		exited: '종료됨',
		created: '생성됨',
		restarting: '재시작 중',
		dead: '비정상 종료',
		pending: '승인 대기',
		approved: '승인 완료',
		deploying: '배포 중',
		deployed: '배포 완료',
		failed: '실패',
		rejected: '반려됨',
	} as Record<string, string>)[status ?? ''] ?? (status || '-');
}

export function statusTone(status?: string | null): string {
	return ({
		running: '#22c55e',
		stopped: '#64748b',
		paused: '#f59e0b',
		exited: '#ef4444',
		created: '#3b82f6',
		restarting: '#8b5cf6',
		dead: '#ef4444',
		pending: '#f59e0b',
		approved: '#3b82f6',
		deploying: '#8b5cf6',
		deployed: '#22c55e',
		failed: '#ef4444',
		rejected: '#64748b',
	} as Record<string, string>)[status ?? ''] ?? '#64748b';
}

export function formatPercent(value?: number | null, digits = 1): string {
	return `${Number(value ?? 0).toFixed(digits)}%`;
}

export function formatBytesValue(value?: number | null): string {
	return formatBytes(value ?? 0);
}

export function formatMemoryUsage(usage?: number | null, limit?: number | null): string {
	const used = formatBytesValue(usage ?? 0);
	if (!limit) return used;
	return `${used} / ${formatBytesValue(limit)}`;
}
