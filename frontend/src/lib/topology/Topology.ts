import * as THREE from 'three';
import { Disposer } from './core/Disposer';
import { RenderLoop } from './core/RenderLoop';
import { SceneManager } from './core/SceneManager';
import { ContainerNode } from './entities/ContainerNode';
import { Hub } from './entities/Hub';
import { NetworkHub, networkColorFor } from './hubs/NetworkHub';
import { StackHub } from './hubs/StackHub';
import { VolumeHub, volumeColorFor } from './hubs/VolumeHub';
import { CameraAnimator } from './interaction/CameraAnimator';
import { Raycaster } from './interaction/Raycaster';
import { ForceLayout, type LayoutEntityRef, type LayoutLink } from './layout/ForceLayout';
import { NodePinner } from './layout/NodePinner';
import type { Connection } from './lines/Connection';
import { NetworkLine } from './lines/NetworkLine';
import { StackLine } from './lines/StackLine';
import { VolumeLine } from './lines/VolumeLine';

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

export type HubType = 'stack' | 'network' | 'volume';

export interface TopologyCallbacks {
	onContainerClick?: (id: string) => void;
	onHubClick?: (hubId: string, hubType: HubType) => void;
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

// Minimum members for a network / volume hub to be drawn. A hub that
// points at a single container adds noise without carrying any
// "shared resource" meaning.
const MIN_HUB_MEMBERS = 2;

type LineKind = 'stack' | 'network' | 'volume';

function parseLineId(lineId: string): { kind: LineKind; hubId: string; nodeId: string } | null {
	// lineId = `${kind}:${hubId}->${nodeId}` where hubId already contains
	// the kind prefix, e.g. "stack:foo->abc" or "network:bar->abc".
	const arrowIdx = lineId.indexOf('->');
	if (arrowIdx < 0) return null;
	const hubId = lineId.slice(0, arrowIdx);
	const nodeId = lineId.slice(arrowIdx + 2);
	const colon = hubId.indexOf(':');
	if (colon < 0) return null;
	const kind = hubId.slice(0, colon) as LineKind;
	return { kind, hubId, nodeId };
}

export class Topology {
	private scene: SceneManager | null = null;
	private loop: RenderLoop | null = null;
	private layout: ForceLayout | null = null;
	private animator: CameraAnimator | null = null;
	private raycaster: Raycaster | null = null;
	private readonly pinner = new NodePinner();
	private readonly disposer = new Disposer();

	private readonly containers: Map<string, ContainerNode> = new Map();
	private readonly hubs: Map<string, Hub> = new Map();
	private readonly lines: Map<string, Connection> = new Map();

	// Visibility for each hub type. Lines of the same kind follow the
	// hub visibility — a network hub hidden with its lines still
	// hidden is the only sensible behaviour.
	private readonly hubVisibility: Record<HubType, boolean> = {
		stack: true,
		network: false,
		volume: false,
	};

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

		const seenHubs = new Set<string>();
		const seenContainers = new Set<string>();
		const seenLines = new Set<string>();

		// --- containers first so hubs can reference their ids ---
		for (const c of data.containers) {
			const stack = c.stack || 'Unmanaged';
			seenContainers.add(c.id);
			const existing = this.containers.get(c.id);
			if (existing) {
				existing.update({ id: c.id, name: c.name, state: c.state, stack });
			} else {
				const node = new ContainerNode({ id: c.id, name: c.name, state: c.state, stack });
				this.containers.set(c.id, node);
				this.scene.scene.add(node.object);
			}
		}

		// --- stack hubs (always computed; visibility toggled later) ---
		const sortedStacks = Array.from(
			new Set(data.containers.map((c) => c.stack || 'Unmanaged'))
		).sort();
		for (const stack of sortedStacks) {
			const hubId = `stack:${stack}`;
			seenHubs.add(hubId);
			const color = stackColorFor(stack, sortedStacks);
			const existing = this.hubs.get(hubId);
			if (existing instanceof StackHub) {
				existing.update({ name: stack, color });
				existing.clearMembers();
			} else {
				const hub = new StackHub({ name: stack, color });
				this.hubs.set(hubId, hub);
				this.scene.scene.add(hub.object);
			}
		}
		// Stack membership
		for (const c of data.containers) {
			const stack = c.stack || 'Unmanaged';
			this.hubs.get(`stack:${stack}`)?.addMember(c.id);
			const lineId = `stack:${stack}->${c.id}`;
			seenLines.add(lineId);
			if (!this.lines.has(lineId)) {
				const hub = this.hubs.get(`stack:${stack}`);
				if (hub instanceof StackHub) {
					const line = new StackLine(hub.color);
					this.lines.set(lineId, line);
					this.scene.scene.add(line.object);
				}
			}
		}

		// --- network hubs (from optional containers[].networks) ---
		const networkMembers = new Map<string, string[]>();
		for (const c of data.containers) {
			for (const net of c.networks ?? []) {
				if (!net) continue;
				const arr = networkMembers.get(net);
				if (arr) arr.push(c.id);
				else networkMembers.set(net, [c.id]);
			}
		}
		const activeNetworks = Array.from(networkMembers.entries())
			.filter(([, members]) => members.length >= MIN_HUB_MEMBERS)
			.map(([name]) => name)
			.sort();
		for (const net of activeNetworks) {
			const hubId = `network:${net}`;
			seenHubs.add(hubId);
			const color = networkColorFor(net, activeNetworks);
			const existing = this.hubs.get(hubId);
			if (existing instanceof NetworkHub) {
				existing.update({ name: net, color });
				existing.clearMembers();
			} else {
				const hub = new NetworkHub({ name: net, color });
				this.hubs.set(hubId, hub);
				this.scene.scene.add(hub.object);
			}
			for (const memberId of networkMembers.get(net) ?? []) {
				this.hubs.get(hubId)?.addMember(memberId);
				const lineId = `${hubId}->${memberId}`;
				seenLines.add(lineId);
				if (!this.lines.has(lineId)) {
					const hub = this.hubs.get(hubId) as NetworkHub;
					const line = new NetworkLine(hub.color);
					this.lines.set(lineId, line);
					this.scene.scene.add(line.object);
				}
			}
		}

		// --- volume hubs (named volumes shared by 2+ containers) ---
		const volumeMembers = new Map<string, string[]>();
		for (const c of data.containers) {
			for (const m of c.mounts ?? []) {
				if (!m || m.type !== 'volume' || !m.name) continue;
				const arr = volumeMembers.get(m.name);
				if (arr) arr.push(c.id);
				else volumeMembers.set(m.name, [c.id]);
			}
		}
		const activeVolumes = Array.from(volumeMembers.entries())
			.filter(([, members]) => members.length >= MIN_HUB_MEMBERS)
			.map(([name]) => name)
			.sort();
		for (const vol of activeVolumes) {
			const hubId = `volume:${vol}`;
			seenHubs.add(hubId);
			const color = volumeColorFor(vol, activeVolumes);
			const existing = this.hubs.get(hubId);
			if (existing instanceof VolumeHub) {
				existing.update({ name: vol, color });
				existing.clearMembers();
			} else {
				const hub = new VolumeHub({ name: vol, color });
				this.hubs.set(hubId, hub);
				this.scene.scene.add(hub.object);
			}
			for (const memberId of volumeMembers.get(vol) ?? []) {
				this.hubs.get(hubId)?.addMember(memberId);
				const lineId = `${hubId}->${memberId}`;
				seenLines.add(lineId);
				if (!this.lines.has(lineId)) {
					const hub = this.hubs.get(hubId) as VolumeHub;
					const line = new VolumeLine(hub.color);
					this.lines.set(lineId, line);
					this.scene.scene.add(line.object);
				}
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

		// --- apply current visibility toggles (some hubs are new) ---
		this.applyVisibility();

		// --- feed layout ---
		const visibleHubs = Array.from(this.hubs.values()).filter((h) => this.hubVisibility[h.hubType]);
		const entities: LayoutEntityRef[] = [
			...visibleHubs.map((h) => ({ id: h.id, position: h.position })),
			...Array.from(this.containers.values()).map((n) => ({ id: n.id, position: n.position })),
		];
		const links: LayoutLink[] = [];
		for (const hub of visibleHubs) {
			for (const memberId of hub.memberIds) {
				if (this.containers.has(memberId)) {
					links.push({ source: hub.id, target: memberId });
				}
			}
		}
		this.layout.setData(entities, links);

		// Re-pin anything the pinner still remembers.
		for (const id of this.pinner.snapshot()) {
			if (this.layout.hasNode(id)) this.layout.pin(id);
			else this.pinner.unpin(id);
		}

		// Codex P1: if the focused entity was pruned by this update, the
		// old focus forces would still point at a ghost. Clear focus so
		// the scene can re-cluster instead of scattering around nothing.
		if (this.activeFocusId) {
			const stillExists =
				this.containers.has(this.activeFocusId) || this.hubs.has(this.activeFocusId);
			if (!stillExists) this.resetFocus();
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
			const parsed = parseLineId(lineId);
			if (!parsed) continue;
			const hub = this.hubs.get(parsed.hubId);
			const node = this.containers.get(parsed.nodeId);
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

	// ---- Focus API ----

	focusContainer(id: string): void {
		const node = this.containers.get(id);
		if (!node) return;
		this.applyFocus(id, new Set([id]), node.position);
		this.animator?.fitSphere(node.position, 18);
	}

	focusHub(id: string, _type: HubType): void {
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
		this.layout.reheat(1.0);
		this.animator?.resetCamera();
	}

	private applyFocus(focusId: string, related: ReadonlySet<string>, center: THREE.Vector3): void {
		if (!this.layout) return;
		this.activeFocusId = focusId;

		for (const id of this.pinner.snapshot()) {
			if (related.has(id)) {
				this.pinner.unpin(id);
				this.layout.unpin(id);
			}
		}

		for (const id of related) {
			if (this.layout.hasNode(id)) {
				this.layout.pin(id);
				this.pinner.pin(id);
			}
		}

		this.layout.setFocus(related, { x: center.x, y: center.y, z: center.z });

		if (this.scatterPinTimer) clearTimeout(this.scatterPinTimer);
		const capturedFocusId = focusId;

		this.scatterPinTimer = setTimeout(() => {
			this.scatterPinTimer = null;
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

	// ---- Visibility API (Phase 3) ----

	setHubVisibility(type: HubType, visible: boolean): void {
		if (this.hubVisibility[type] === visible) return;
		this.hubVisibility[type] = visible;
		this.applyVisibility();
		// Lines / hubs just turned visible need their links reflected
		// in the layout so force positions work; recompute links.
		this.rebuildLayoutLinks();
	}

	private applyVisibility(): void {
		for (const hub of this.hubs.values()) {
			hub.object.visible = this.hubVisibility[hub.hubType];
		}
		for (const [lineId, line] of this.lines) {
			const parsed = parseLineId(lineId);
			if (!parsed) continue;
			line.object.visible = this.hubVisibility[parsed.kind as HubType];
		}
	}

	private rebuildLayoutLinks(): void {
		if (!this.layout) return;
		const visibleHubs = Array.from(this.hubs.values()).filter(
			(h) => this.hubVisibility[h.hubType]
		);
		const entities: LayoutEntityRef[] = [
			...visibleHubs.map((h) => ({ id: h.id, position: h.position })),
			...Array.from(this.containers.values()).map((n) => ({ id: n.id, position: n.position })),
		];
		const links: LayoutLink[] = [];
		for (const hub of visibleHubs) {
			for (const memberId of hub.memberIds) {
				if (this.containers.has(memberId)) {
					links.push({ source: hub.id, target: memberId });
				}
			}
		}
		this.layout.setData(entities, links);
		for (const id of this.pinner.snapshot()) {
			if (this.layout.hasNode(id)) this.layout.pin(id);
		}
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
		this.host = null;
		this.activeFocusId = null;
	}
}
