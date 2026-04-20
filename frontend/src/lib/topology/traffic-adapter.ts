import type { RawContainerMetrics, RawContainerNetworkStat } from '$lib/stores/ws-store';

export type TrafficMappingMode = 'exact' | 'single-network-fallback' | 'unresolved';

export interface TopologyNetworkTrafficPoint {
	containerId: string;
	networkName: string | null;
	interfaceName: string | null;
	mappingMode: TrafficMappingMode;
	rxBytes: number;
	txBytes: number;
	rxRateBps: number | null;
	txRateBps: number | null;
	totalRateBps: number;
	timestamp: string | null;
}

export type TopologyNetworkTrafficIndex = Map<string, Map<string, TopologyNetworkTrafficPoint>>;

function asNumber(value: unknown): number {
	return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function asNullableRate(value: unknown): number | null {
	return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function normalizeMappingMode(value: unknown): TrafficMappingMode {
	return value === 'exact' || value === 'single-network-fallback' || value === 'unresolved'
		? value
		: 'unresolved';
}

export function adaptContainerNetworkTraffic(
	metrics: RawContainerMetrics | null | undefined
): TopologyNetworkTrafficPoint[] {
	if (!metrics?.containerId || !Array.isArray(metrics.network_stats)) return [];

	return metrics.network_stats.map((stat: RawContainerNetworkStat) => {
		const rxRateBps = asNullableRate(stat.rx_rate_bps);
		const txRateBps = asNullableRate(stat.tx_rate_bps);
		return {
			containerId: metrics.containerId,
			networkName: typeof stat.network_name === 'string' ? stat.network_name : null,
			interfaceName: typeof stat.interface_name === 'string' ? stat.interface_name : null,
			mappingMode: normalizeMappingMode(stat.mapping_mode),
			rxBytes: asNumber(stat.rx_bytes),
			txBytes: asNumber(stat.tx_bytes),
			rxRateBps,
			txRateBps,
			totalRateBps: (rxRateBps ?? 0) + (txRateBps ?? 0),
			timestamp: typeof stat.timestamp === 'string' ? stat.timestamp : null,
		};
	});
}

export function buildNetworkTrafficIndex(
	metricsMap: Map<string, RawContainerMetrics>
): TopologyNetworkTrafficIndex {
	const index: TopologyNetworkTrafficIndex = new Map();

	for (const [containerId, metrics] of metricsMap) {
		const perContainer = new Map<string, TopologyNetworkTrafficPoint>();
		for (const point of adaptContainerNetworkTraffic(metrics)) {
			if (!point.networkName) continue;
			perContainer.set(point.networkName, point);
		}
		if (perContainer.size > 0) {
			index.set(containerId, perContainer);
		}
	}

	return index;
}

export function getNetworkTrafficPoint(
	index: TopologyNetworkTrafficIndex,
	containerId: string,
	networkName: string
): TopologyNetworkTrafficPoint | null {
	return index.get(containerId)?.get(networkName) ?? null;
}
