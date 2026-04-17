/**
 * Topology facade.
 *
 * Svelte components instantiate this, call `mount(containerEl, initialData)`,
 * feed it data with `update(data)`, and `dispose()` on teardown.
 *
 * Implementation lands in Phase 1.
 */

export interface TopologyContainerData {
	id: string;
	name: string;
	state: string;
	stack: string;
	networks?: string[];
	mounts?: { name: string; type: 'volume' | 'bind' }[];
}

export interface TopologyData {
	containers: TopologyContainerData[];
}

export interface TopologyCallbacks {
	onContainerClick?: (id: string) => void;
	onHubClick?: (hubId: string, hubType: 'stack' | 'network' | 'volume') => void;
}

export class Topology {
	mount(_container: HTMLElement, _data: TopologyData, _cb?: TopologyCallbacks): void {
		throw new Error('Topology.mount() — Phase 1 pending');
	}

	update(_data: TopologyData): void {
		throw new Error('Topology.update() — Phase 1 pending');
	}

	focusContainer(_id: string): void {
		throw new Error('Topology.focusContainer() — Phase 2 pending');
	}

	focusHub(_id: string, _type: 'stack' | 'network' | 'volume'): void {
		throw new Error('Topology.focusHub() — Phase 2 pending');
	}

	resetFocus(): void {
		throw new Error('Topology.resetFocus() — Phase 2 pending');
	}

	setHubVisibility(_type: 'stack' | 'network' | 'volume', _visible: boolean): void {
		throw new Error('Topology.setHubVisibility() — Phase 3 pending');
	}

	dispose(): void {
		throw new Error('Topology.dispose() — Phase 1 pending');
	}
}
