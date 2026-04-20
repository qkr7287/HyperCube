import { formatBytes } from '$lib/utils/data-adapter';

export function formatDateTime(value?: string | null): string {
	if (!value) return '-';
	try {
		return new Date(value).toLocaleString();
	} catch {
		return value;
	}
}

export function formatRelativeTime(value?: string | null): string {
	if (!value) return '-';
	try {
		const diff = Math.floor((Date.now() - new Date(value).getTime()) / 1000);
		if (diff < 60) return `${diff}s ago`;
		if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
		if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
		return `${Math.floor(diff / 86400)}d ago`;
	} catch {
		return value;
	}
}

export function statusLabel(status?: string | null): string {
	return ({
		running: 'Running',
		stopped: 'Stopped',
		paused: 'Paused',
		exited: 'Exited',
		created: 'Created',
		restarting: 'Restarting',
		dead: 'Dead',
		pending: 'Pending',
		approved: 'Approved',
		deploying: 'Deploying',
		deployed: 'Deployed',
		failed: 'Failed',
		rejected: 'Rejected',
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
