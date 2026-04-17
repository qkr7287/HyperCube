import * as THREE from 'three';
import { Disposer } from './core/Disposer';
import { RenderLoop } from './core/RenderLoop';
import { SceneManager } from './core/SceneManager';
import { ContainerNode } from './entities/ContainerNode';
import type { Entity } from './entities/Entity';
import { Hub } from './entities/Hub';
import { StackHub } from './hubs/StackHub';
import { CameraAnimator } from './interaction/CameraAnimator';
import { InputController } from './interaction/InputController';
import { Raycaster } from './interaction/Raycaster';
import { ForceLayout, type LayoutEntityRef, type LayoutLink } from './layout/ForceLayout';
import { NodePinner } from './layout/NodePinner';
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

// Delay before newly-scattered unrelated nodes get pinned in place.
// The layout needs a moment to actually push them outward before we
// freeze their position (req #10).
const SCATTER_PIN_DELAY_MS = 1500;

export class Topology {
	private scene: SceneManager | null = null;
	private loop: RenderLoop | null = null;
	private layout: ForceLayout | null = null;
	private animator: CameraAnimator | null = null;
	private raycaster: Raycaster | null = null;
	private input: InputController | null = null;
	private readonly pinner = new NodePinner();
	private readonly disposer = new Disposer();

	private readonly containers: Map<string, ContainerNode> = new Map();
	private readonly hubs: Map<string, Hub> = new Map();
	private readonly lines: Map<string, StackLine> = new Map();

	private host: HTMLElement | null = null;
	private callbacks: TopologyCallbacks = {};
	private detachTick: (() => void) | null = null;
	private detachClick: (() => void) | null = null;
	private scatterPinTimer: ReturnType<typeof setTimeout> | null = null;
	private activeFocusId: string | null = null;

	mount(host: HTMLElement, data: TopologyData, cb?: TopologyCallbacks): void {
		if (this.scene) throw new Error('Topology.mount: already mounted');

		this.host = host;
		this.callbacks = cb ?? {};

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
		this.animator = new CameraAnimator(scene.camera, scene.controls);
		this.raycaster = new Raycaster();
		this.input = new InputController();
		this.input.attach(() => this.resetFocus());

		this.update(data);

		this.detachTick = this.loop.add(() => {
			this.layout?.tick();
			this.syncEntityPositions();
			this.syncLinePositions();
			this.animator?.tick();
			this.scene?.render();
		});
		this.loop.start();

		const onClick = (e: MouseEvent) => this.handlePointerClick(e);
		host.addEventListener('click', onClick);
		this.detachClick = () => host.removeEventListener('click', onClick);
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
			if (existing && existing instanceof StackHub) {
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
			this.hubs.get(hubId)?.addMember(c.id);

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
				if (!(hub instanceof StackHub)) continue;
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

		// Re-pin anything the pinner still remembers (node objects are
		// recreated across server switches, but pin ids may persist).
		for (const id of this.pinner.snapshot()) {
			if (this.layout.hasNode(id)) this.layout.pin(id);
			else this.pinner.unpin(id);
		}
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

	// ---- Click dispatch ----

	private handlePointerClick(event: MouseEvent): void {
		if (!this.scene || !this.raycaster || !this.host) return;
		const hit = this.raycaster.pickAt(event, this.host, this.scene.camera, this.scene.scene);
		if (!hit) return;
		if (hit instanceof ContainerNode) {
			this.focusContainer(hit.id);
			this.callbacks.onContainerClick?.(hit.id);
			return;
		}
		if (hit instanceof Hub) {
			this.focusHub(hit.id, hit.hubType);
			this.callbacks.onHubClick?.(hit.id, hit.hubType);
		}
	}

	// ---- Focus API (Phase 2) ----

	focusContainer(id: string): void {
		const node = this.containers.get(id);
		if (!node) return;
		this.applyFocus(id, new Set([id]), node.position);
		this.animator?.fitSphere(node.position, 18);
	}

	focusHub(id: string, _type: 'stack' | 'network' | 'volume'): void {
		const hub = this.hubs.get(id);
		if (!hub) return;
		const related = new Set<string>([hub.id, ...hub.memberIds]);
		const center = hub.position.clone();
		let maxDist = 0;
		for (const mid of hub.memberIds) {
			const n = this.containers.get(mid);
			if (!n) continue;
			const d = n.position.distanceTo(center);
			if (d > maxDist) maxDist = d;
		}
		this.applyFocus(id, related, center);
		this.animator?.fitSphere(center, maxDist + 25);
	}

	resetFocus(): void {
		if (!this.layout) return;
		if (this.scatterPinTimer) {
			clearTimeout(this.scatterPinTimer);
			this.scatterPinTimer = null;
		}
		this.activeFocusId = null;
		this.pinner.clear();
		this.layout.unpinAll();
		this.layout.clearFocus();
		this.animator?.resetCamera();
	}

	private applyFocus(focusId: string, related: ReadonlySet<string>, center: THREE.Vector3): void {
		if (!this.layout) return;
		this.activeFocusId = focusId;

		// Release pins on nodes that are now *back* in the related set —
		// they should re-gather toward the new focus (req #10, second half).
		for (const id of this.pinner.snapshot()) {
			if (related.has(id)) {
				this.pinner.unpin(id);
				this.layout.unpin(id);
			}
		}

		this.layout.setFocus(related, { x: center.x, y: center.y, z: center.z });

		if (this.scatterPinTimer) clearTimeout(this.scatterPinTimer);
		const capturedFocusId = focusId;
		this.scatterPinTimer = setTimeout(() => {
			this.scatterPinTimer = null;
			// Only pin if the user hasn't moved on to a different focus.
			if (this.activeFocusId !== capturedFocusId) return;
			if (!this.layout) return;
			for (const id of this.containers.keys()) {
				if (related.has(id)) continue;
				if (this.pinner.isPinned(id)) continue;
				this.pinner.pin(id);
				this.layout.pin(id);
			}
		}, SCATTER_PIN_DELAY_MS);
	}

	// ---- Phase 3 placeholder ----

	setHubVisibility(_type: 'stack' | 'network' | 'volume', _visible: boolean): void {
		/* Phase 3 */
	}

	dispose(): void {
		if (this.scatterPinTimer) {
			clearTimeout(this.scatterPinTimer);
			this.scatterPinTimer = null;
		}
		if (this.detachClick) {
			this.detachClick();
			this.detachClick = null;
		}
		if (this.detachTick) {
			this.detachTick();
			this.detachTick = null;
		}
		this.input?.detach();
		this.animator?.cancel();
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
		this.pinner.clear();
		this.scene = null;
		this.loop = null;
		this.layout = null;
		this.animator = null;
		this.raycaster = null;
		this.input = null;
		this.host = null;
		this.activeFocusId = null;
	}
}
