import * as THREE from 'three';
import { Disposer } from './core/Disposer';
import { RenderLoop } from './core/RenderLoop';
import { SceneManager } from './core/SceneManager';
import { ContainerNode } from './entities/ContainerNode';
import { StackHub } from './hubs/StackHub';
import { ForceLayout, type LayoutEntityRef, type LayoutLink } from './layout/ForceLayout';
import { StackLine } from './lines/StackLine';

export interface TopologyContainerData {
	id: string;
	name: string;
	state: string;
	stack: string;
	networks?: string[];
	mounts?: { name: string; type: 'volume' }[];
}

export interface TopologyData {
	containers: TopologyContainerData[];
}

export interface TopologyCallbacks {
	onContainerClick?: (id: string) => void;
	onHubClick?: (hubId: string, hubType: 'stack' | 'network' | 'volume') => void;
}

// Stack palette — stable mapping across renders, indexed by sorted name.
const STACK_COLORS: readonly number[] = [
	0x30d5c8, 0xfbbf24, 0xf472b6, 0x60a5fa, 0xa78bfa,
	0x4ade80, 0xfb923c, 0xf87171, 0x2dd4bf, 0xeab308,
	0xc084fc, 0x38bdf8, 0x34d399, 0xfacc15, 0xfb7185,
];

function stackColorFor(stackName: string, sortedNames: readonly string[]): number {
	const idx = sortedNames.indexOf(stackName);
	return STACK_COLORS[Math.max(idx, 0) % STACK_COLORS.length];
}

/**
 * Facade over the topology. Svelte components instantiate this,
 * mount it into a host element, feed it data with update(), and
 * dispose() on teardown.
 *
 * Phase 1 scope: stack hub + stack line + force layout. Focus /
 * pin / network / volume / sidebar events land in later phases.
 */
export class Topology {
	private scene: SceneManager | null = null;
	private loop: RenderLoop | null = null;
	private layout: ForceLayout | null = null;
	private readonly disposer = new Disposer();

	private readonly containers: Map<string, ContainerNode> = new Map();
	private readonly hubs: Map<string, StackHub> = new Map();
	private readonly lines: Map<string, StackLine> = new Map();

	private detachTick: (() => void) | null = null;

	mount(host: HTMLElement, data: TopologyData, _cb?: TopologyCallbacks): void {
		if (this.scene) throw new Error('Topology.mount: already mounted');

		const scene = new SceneManager(host);
		scene.scene.add(new THREE.AmbientLight(0xffffff, 0.55));
		const dir = new THREE.DirectionalLight(0xffffff, 0.85);
		dir.position.set(150, 250, 350);
		scene.scene.add(dir);
		const fill = new THREE.DirectionalLight(0x60a5fa, 0.25);
		fill.position.set(-200, -100, -150);
		scene.scene.add(fill);

		this.scene = scene;
		this.layout = new ForceLayout();
		this.loop = new RenderLoop();

		this.update(data);

		this.detachTick = this.loop.add(() => {
			this.layout?.tick();
			this.syncEntityPositions();
			this.syncLinePositions();
			this.scene?.render();
		});
		this.loop.start();
	}

	update(data: TopologyData): void {
		if (!this.scene || !this.layout) return;

		const sortedStacks = Array.from(
			new Set(data.containers.map((c) => c.stack || 'Unmanaged'))
		).sort();

		const seenHubs = new Set<string>();
		const seenContainers = new Set<string>();
		const seenLines = new Set<string>();

		// --- hubs ---
		for (const stack of sortedStacks) {
			const hubId = `stack:${stack}`;
			seenHubs.add(hubId);
			const color = stackColorFor(stack, sortedStacks);
			const existing = this.hubs.get(hubId);
			if (existing) {
				existing.update({ name: stack, color });
				existing.clearMembers();
			} else {
				const hub = new StackHub({ name: stack, color });
				this.hubs.set(hubId, hub);
				this.scene.scene.add(hub.object);
			}
		}

		// --- containers ---
		for (const c of data.containers) {
			const stack = c.stack || 'Unmanaged';
			seenContainers.add(c.id);
			const hubId = `stack:${stack}`;
			const hub = this.hubs.get(hubId);
			hub?.addMember(c.id);

			const existing = this.containers.get(c.id);
			if (existing) {
				existing.update({ id: c.id, name: c.name, state: c.state, stack });
			} else {
				const node = new ContainerNode({ id: c.id, name: c.name, state: c.state, stack });
				this.containers.set(c.id, node);
				this.scene.scene.add(node.object);
			}
		}

		// --- lines ---
		for (const c of data.containers) {
			const stack = c.stack || 'Unmanaged';
			const hubId = `stack:${stack}`;
			const lineId = `${hubId}->${c.id}`;
			seenLines.add(lineId);
			if (!this.lines.has(lineId)) {
				const hub = this.hubs.get(hubId);
				if (!hub) continue;
				const line = new StackLine(hub.color);
				this.lines.set(lineId, line);
				this.scene.scene.add(line.object);
			}
		}

		// --- drop stale ---
		this.pruneStale(this.containers, seenContainers, (n) => {
			this.scene!.scene.remove(n.object);
			n.dispose();
		});
		this.pruneStale(this.hubs, seenHubs, (h) => {
			this.scene!.scene.remove(h.object);
			h.dispose();
		});
		this.pruneStale(this.lines, seenLines, (l) => {
			this.scene!.scene.remove(l.object);
			l.dispose();
		});

		// --- feed layout ---
		const entities: LayoutEntityRef[] = [
			...Array.from(this.hubs.values()).map((h) => ({ id: h.id, position: h.position })),
			...Array.from(this.containers.values()).map((n) => ({ id: n.id, position: n.position })),
		];
		const links: LayoutLink[] = data.containers.map((c) => ({
			source: `stack:${c.stack || 'Unmanaged'}`,
			target: c.id,
		}));
		this.layout.setData(entities, links);
	}

	private pruneStale<T>(
		map: Map<string, T>,
		seen: ReadonlySet<string>,
		onDrop: (v: T) => void
	): void {
		for (const [id, v] of map) {
			if (seen.has(id)) continue;
			onDrop(v);
			map.delete(id);
		}
	}

	private syncEntityPositions(): void {
		for (const n of this.containers.values()) n.syncPosition();
		for (const h of this.hubs.values()) h.syncPosition();
	}

	private syncLinePositions(): void {
		for (const [lineId, line] of this.lines) {
			const arrowIdx = lineId.indexOf('->');
			if (arrowIdx < 0) continue;
			const hubId = lineId.slice(0, arrowIdx);
			const nodeId = lineId.slice(arrowIdx + 2);
			const hub = this.hubs.get(hubId);
			const node = this.containers.get(nodeId);
			if (hub && node) line.setEndpoints(hub.position, node.position);
		}
	}

	// Phase 2 hooks — currently no-ops.
	focusContainer(_id: string): void {
		/* Phase 2 */
	}
	focusHub(_id: string, _type: 'stack' | 'network' | 'volume'): void {
		/* Phase 2 */
	}
	resetFocus(): void {
		/* Phase 2 */
	}

	// Phase 3 hook — currently no-op.
	setHubVisibility(_type: 'stack' | 'network' | 'volume', _visible: boolean): void {
		/* Phase 3 */
	}

	dispose(): void {
		if (this.detachTick) {
			this.detachTick();
			this.detachTick = null;
		}
		this.loop?.stop();
		this.layout?.stop();

		if (this.scene) {
			for (const n of this.containers.values()) {
				this.scene.scene.remove(n.object);
				n.dispose();
			}
			for (const h of this.hubs.values()) {
				this.scene.scene.remove(h.object);
				h.dispose();
			}
			for (const l of this.lines.values()) {
				this.scene.scene.remove(l.object);
				l.dispose();
			}
			// Clear ambient/directional lights and anything else we added.
			const toRemove: THREE.Object3D[] = [];
			this.scene.scene.traverse((o) => {
				if (o.type.includes('Light')) toRemove.push(o);
			});
			for (const o of toRemove) this.scene.scene.remove(o);
			this.scene.dispose();
		}

		this.containers.clear();
		this.hubs.clear();
		this.lines.clear();
		this.scene = null;
		this.loop = null;
		this.layout = null;
	}
}
