import * as THREE from 'three';
import { Disposer } from './core/Disposer';
import { loadAllTemplates, type TemplateBundle } from './core/MeshFactory';
import { RenderLoop } from './core/RenderLoop';
import { SceneManager } from './core/SceneManager';
import { Starfield } from './core/Starfield';
import { ContainerNode, type ContainerGeometryStyle } from './entities/ContainerNode';
import { Hub } from './entities/Hub';
import { GroupMesh, type GroupVisualMode } from './hubs/GroupMesh';
import { NetworkHub, networkColorFor, setNetworkPalette } from './hubs/NetworkHub';
import type { NetworkHubFxMode, NetworkPaletteMode } from './hubs/NetworkHub';
import { StackHub } from './hubs/StackHub';
import { VolumeHub, volumeColorFor } from './hubs/VolumeHub';
import { CameraAnimator } from './interaction/CameraAnimator';
import { Raycaster } from './interaction/Raycaster';
import type { Entity } from './entities/Entity';
import { ForceLayout, type LayoutEntityRef, type LayoutLink } from './layout/ForceLayout';
import { NodePinner } from './layout/NodePinner';
import type { Connection } from './lines/Connection';
import type { LinePulseMode, TrafficFxStyle, TunnelStyle, VolumeEnergyStyle } from './lines/Connection';
import { NetworkLine } from './lines/NetworkLine';
import { StackLine } from './lines/StackLine';
import { VolumeLine } from './lines/VolumeLine';
import type { TopologyNetworkTrafficIndex } from './traffic-adapter';

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
	/**
	 * Optional mapping from stack name to colour (as a three.js hex
	 * number). When provided, overrides the built-in STACK_COLORS
	 * palette so stack hubs, lines, and group meshes line up with the
	 * caller's own colour scheme (e.g. the sidebar group dots).
	 */
	stackColors?: Record<string, number>;
	networkTraffic?: TopologyNetworkTrafficIndex;
}

export type HubType = 'stack' | 'network' | 'volume';

// Loading stages surfaced to the Svelte layer so it can show a staged
// loading overlay with logo + progress text. Progresses:
//   models      — GLB templates are downloading
//   scene       — templates ready, entities being rebuilt
//   stabilizing — first real frames rendering, waiting for steady dt
//   ready       — overlay can cross-fade out
export type LoadingStage = 'models' | 'scene' | 'stabilizing' | 'ready';

export interface TopologyCallbacks {
	onContainerClick?: (id: string) => void;
	onHubClick?: (hubId: string, hubType: HubType) => void;
	onEmptyClick?: () => void;
	onLoadingStage?: (stage: LoadingStage) => void;
}

// Stack palette — stable mapping across renders, indexed by sorted name.
// Teal/cyan/emerald are reserved for container state + network tunnels,
// so those hues are deliberately absent from this palette to keep group
// membranes visually distinct from the network layer.
const STACK_COLORS: readonly number[] = [
	0xfbbf24, 0xf472b6, 0x60a5fa, 0xa78bfa, 0xfb923c,
	0xf87171, 0xeab308, 0xc084fc, 0xfacc15, 0xfb7185,
	0xd4a574, 0x8e24aa, 0xef5350, 0xba68c8, 0xff9100,
];

function stackColorFor(
	stackName: string,
	sortedNames: readonly string[],
	override?: Record<string, number>
): number {
	if (override && override[stackName] !== undefined) return override[stackName];
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

function hashString(input: string): number {
	let hash = 0;
	for (let i = 0; i < input.length; i += 1) {
		hash = ((hash << 5) - hash + input.charCodeAt(i)) | 0;
	}
	return Math.abs(hash);
}

function networkPacketColorFor(mode: NetworkPaletteMode): number {
	switch (mode) {
		case 'cyan':
			return 0x06b6d4;
		case 'emerald':
			return 0x86efac;
		case 'sunset':
			return 0xfcd34d;
		case 'fuchsia':
		default:
			return 0xa3e635;
	}
}

export class Topology {
	private static readonly CLICK_MOVE_THRESHOLD_PX = 4;
	private scene: SceneManager | null = null;
	private loop: RenderLoop | null = null;
	private layout: ForceLayout | null = null;
	private animator: CameraAnimator | null = null;
	private raycaster: Raycaster | null = null;
	private starfield: Starfield | null = null;
	// Current selection — the Svelte layer reads this each frame and
	// renders a DOM tooltip on top of the canvas, which avoids every
	// z-ordering and depthTest pitfall that a 3D sprite ran into.
	private selectionTarget: Entity | null = null;
	private readonly pinner = new NodePinner();
	private readonly disposer = new Disposer();

	private readonly containers: Map<string, ContainerNode> = new Map();
	private readonly hubs: Map<string, Hub> = new Map();
	private readonly lines: Map<string, Connection> = new Map();
	// Stack name → mesh wrapping its members. Same lifecycle as StackHub.
	private readonly groupMeshes: Map<string, GroupMesh> = new Map();

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
	private pointerDownId: number | null = null;
	private pointerDownX = 0;
	private pointerDownY = 0;
	private pointerMoved = false;
	private scatterPinTimer: ReturnType<typeof setTimeout> | null = null;
	// --- Loading overlay state ---
	private loadingStage: LoadingStage = 'models';
	private stableFrameCount = 0;
	private loadingWatchdog: ReturnType<typeof setTimeout> | null = null;
	private loadingSceneHoldTimer: ReturnType<typeof setTimeout> | null = null;
	private loadingStartedAt = 0;
	private static readonly STABLE_FRAME_TARGET = 30;
	private static readonly STABLE_DT_MAX = 0.022; // ~45fps floor
	private static readonly LOADING_SAFETY_MS = 8000;
	private static readonly STAGE_HOLD_MS = 350;
	// Even on fast loads, hold the overlay for this long so users can
	// register the branding / stage text instead of a sub-second flash.
	private static readonly LOADING_MIN_MS = 1400;
	private activeFocusId: string | null = null;
	private curvedLines = false;
	private groupVisualMode: GroupVisualMode = 'soft';
	private networkPaletteMode: NetworkPaletteMode = 'cyan';
	private networkHubFxMode: NetworkHubFxMode = 'ripple';
	private linePulseMode: LinePulseMode = 'tunnel';
	private tunnelStyle: TunnelStyle = 'subsea';
	private networkTunnelThickness = 0.7;
	private trafficFxStyle: TrafficFxStyle = 'soft';
	private packetGlowStrength = 1;
	private volumeEnergyStyle: VolumeEnergyStyle = 'tendril';
	private containerGeometryStyle: ContainerGeometryStyle = 'crate';
	private bloomStrength = 0.1;
	private templates: TemplateBundle = {
		container: null,
		stack: null,
		network: null,
		volume: null,
	};
	private modelBaseUrl: string = '';
	private lastData: TopologyData | null = null;

	setModelBaseUrl(baseUrl: string): void {
		this.modelBaseUrl = baseUrl;
	}

	mount(host: HTMLElement, data: TopologyData, cb?: TopologyCallbacks): void {
		if (this.scene) throw new Error('Topology.mount: already mounted');

		this.host = host;
		this.callbacks = cb ?? {};
		setNetworkPalette(this.networkPaletteMode);

		const scene = new SceneManager(host);
		scene.scene.add(new THREE.AmbientLight(0xffffff, 0.55));
		const hemi = new THREE.HemisphereLight(0x9bd7ff, 0x0d1117, 0.85);
		scene.scene.add(hemi);
		const dir = new THREE.DirectionalLight(0xffffff, 0.85);
		dir.position.set(150, 250, 350);
		scene.scene.add(dir);
		const fill = new THREE.DirectionalLight(0x60a5fa, 0.25);
		fill.position.set(-200, -100, -150);
		scene.scene.add(fill);
		const rim = new THREE.PointLight(0x30d5c8, 12000, 0, 2);
		rim.position.set(-220, 140, 260);
		scene.scene.add(rim);

		this.scene = scene;
		scene.setBloomStrength(this.bloomStrength);
		this.layout = new ForceLayout();
		this.loop = new RenderLoop();
		this.animator = new CameraAnimator(scene.camera, scene.controls);
		this.raycaster = new Raycaster();
		this.starfield = new Starfield();
		scene.scene.add(this.starfield.object);

		this.update(data);

		// Kick off the staged loading overlay. 'models' fires immediately;
		// 'scene' / 'stabilizing' fire from loadTemplatesAsync below; the
		// tick below promotes 'stabilizing' → 'ready' once frame dt has
		// been steady for STABLE_FRAME_TARGET frames.
		this.loadingStage = 'models';
		this.stableFrameCount = 0;
		this.loadingStartedAt = performance.now();
		this.callbacks.onLoadingStage?.('models');
		this.loadingWatchdog = setTimeout(
			() => this.emitLoadingStage('ready'),
			Topology.LOADING_SAFETY_MS
		);

		this.detachTick = this.loop.add((dt) => {
			this.layout?.tick();
			this.starfield?.tick(dt);
			this.syncEntityPositions();
			this.syncLinePositions();
			this.updateGroupMeshes();
			this.updateNetworkTrafficVisuals(dt);
			this.animator?.tick();
			this.scene?.render();

			if (this.loadingStage !== 'ready') {
				if (dt > 0 && dt < Topology.STABLE_DT_MAX) this.stableFrameCount += 1;
				else this.stableFrameCount = 0;
				const stable =
					this.loadingStage === 'stabilizing' &&
					this.stableFrameCount >= Topology.STABLE_FRAME_TARGET;
				const elapsedOk =
					performance.now() - this.loadingStartedAt >= Topology.LOADING_MIN_MS;
				if (stable && elapsedOk) {
					this.emitLoadingStage('ready');
				}
			}
		});
		this.loop.start();

		const onPointerDown = (e: PointerEvent) => this.handlePointerDown(e);
		const onPointerMove = (e: PointerEvent) => this.handlePointerMove(e);
		const onPointerUp = (e: PointerEvent) => this.handlePointerUp(e);
		const onPointerCancel = () => this.resetPointerTracking();
		host.addEventListener('pointerdown', onPointerDown);
		host.addEventListener('pointermove', onPointerMove);
		host.addEventListener('pointerup', onPointerUp);
		host.addEventListener('pointercancel', onPointerCancel);
		this.detachClick = () => {
			host.removeEventListener('pointerdown', onPointerDown);
			host.removeEventListener('pointermove', onPointerMove);
			host.removeEventListener('pointerup', onPointerUp);
			host.removeEventListener('pointercancel', onPointerCancel);
		};

		// Kick off GLB load in the background. Scene already rendered
		// with the fallback geometries; once templates arrive we
		// rebuild every entity so they switch to the GLB meshes.
		this.loadTemplatesAsync();
	}

	private async loadTemplatesAsync(): Promise<void> {
		try {
			const bundle = await loadAllTemplates(this.modelBaseUrl);
			if (!this.scene) return;
			this.templates = bundle;
			this.rebuildAllFromTemplates();
			this.emitLoadingStage('scene');
			this.loadingSceneHoldTimer = setTimeout(
				() => this.emitLoadingStage('stabilizing'),
				Topology.STAGE_HOLD_MS
			);
		} catch {
			// Silent fallback — still progress the overlay so the user
			// isn't stuck on "Loading models" when GLBs can't be fetched.
			this.emitLoadingStage('scene');
			this.loadingSceneHoldTimer = setTimeout(
				() => this.emitLoadingStage('stabilizing'),
				120
			);
		}
	}

	private emitLoadingStage(stage: LoadingStage): void {
		if (this.loadingStage === stage) return;
		this.loadingStage = stage;
		this.callbacks.onLoadingStage?.(stage);
		if (stage === 'ready' && this.loadingWatchdog !== null) {
			clearTimeout(this.loadingWatchdog);
			this.loadingWatchdog = null;
		}
	}

	private rebuildAllFromTemplates(): void {
		if (!this.scene || !this.lastData) return;
		// Drop every entity so they re-create with the GLB templates.
		for (const node of this.containers.values()) {
			this.scene.scene.remove(node.object);
			node.dispose();
		}
		this.containers.clear();
		for (const hub of this.hubs.values()) {
			this.scene.scene.remove(hub.object);
			hub.dispose();
		}
		this.hubs.clear();
		for (const line of this.lines.values()) {
			this.scene.scene.remove(line.object);
			line.dispose();
		}
		this.lines.clear();
		// Group meshes survive: they don't carry geometry that depends
		// on GLB templates, only on live member positions. But their
		// members now point at disposed ContainerNodes — clear and let
		// update() rebuild them.
		for (const gm of this.groupMeshes.values()) {
			this.scene.scene.remove(gm.object);
			gm.dispose();
		}
		this.groupMeshes.clear();

		this.update(this.lastData);
	}

	update(data: TopologyData): void {
		if (!this.scene || !this.layout) return;
		const mergedData: TopologyData = {
			...data,
			networkTraffic: data.networkTraffic ?? this.lastData?.networkTraffic,
		};
		this.lastData = mergedData;

		const seenHubs = new Set<string>();
		const seenContainers = new Set<string>();
		const seenLines = new Set<string>();

		// --- containers first so hubs can reference their ids ---
		for (const c of mergedData.containers) {
			const stack = c.stack || 'Unmanaged';
			seenContainers.add(c.id);
			const existing = this.containers.get(c.id);
			if (existing) {
				existing.update({ id: c.id, name: c.name, state: c.state, stack });
			} else {
				const node = new ContainerNode(
					{ id: c.id, name: c.name, state: c.state, stack },
					this.templates.container,
					this.containerGeometryStyle
				);
				this.containers.set(c.id, node);
				this.scene.scene.add(node.object);
			}
		}

		// --- stack hubs (always computed; visibility toggled later) ---
		const sortedStacks = Array.from(
			new Set(mergedData.containers.map((c) => c.stack || 'Unmanaged'))
		).sort();
		const seenGroups = new Set<string>();
		for (const stack of sortedStacks) {
			const hubId = `stack:${stack}`;
			seenHubs.add(hubId);
			seenGroups.add(stack);
			const color = stackColorFor(stack, sortedStacks, mergedData.stackColors);
			const existing = this.hubs.get(hubId);
			if (existing instanceof StackHub) {
				existing.update({ name: stack, color });
				existing.clearMembers();
			} else {
				const hub = new StackHub({ name: stack, color }, this.templates.stack);
				this.hubs.set(hubId, hub);
				this.scene.scene.add(hub.object);
			}
			// GroupMesh: one per stack, tracks the hub color.
			let gm = this.groupMeshes.get(stack);
			if (!gm) {
				gm = new GroupMesh(color);
				gm.setMode(this.groupVisualMode);
				this.groupMeshes.set(stack, gm);
				this.scene.scene.add(gm.object);
			} else {
				gm.setColor(color);
				gm.setMode(this.groupVisualMode);
			}
		}
		// Stack membership
		for (const c of mergedData.containers) {
			const stack = c.stack || 'Unmanaged';
			this.hubs.get(`stack:${stack}`)?.addMember(c.id);
			const lineId = `stack:${stack}->${c.id}`;
			seenLines.add(lineId);
			if (!this.lines.has(lineId)) {
				const hub = this.hubs.get(`stack:${stack}`);
				if (hub instanceof StackHub) {
					const line = new StackLine(hub.color);
					line.setCurved(this.curvedLines);
					line.setPulseMode(this.linePulseMode);
					line.setTunnelStyle(this.tunnelStyle);
					line.setTunnelThickness(this.networkTunnelThickness);
					line.setTrafficFxStyle(this.trafficFxStyle);
					line.setPacketGlowStrength(this.packetGlowStrength);
					line.setVolumeEnergyStyle(this.volumeEnergyStyle);
					line.setCurveSeed(hashString(lineId));
					this.lines.set(lineId, line);
					this.scene.scene.add(line.object);
				}
			}
		}

		// --- network hubs (from optional containers[].networks) ---
		const networkMembers = new Map<string, string[]>();
		for (const c of mergedData.containers) {
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
				existing.setFxMode(this.networkHubFxMode);
				existing.clearMembers();
			} else {
				const hub = new NetworkHub({ name: net, color }, this.templates.network);
				hub.setFxMode(this.networkHubFxMode);
				this.seedHubPosition(hub, networkMembers.get(net) ?? []);
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
					line.setCurved(this.curvedLines);
					line.setPulseMode(this.linePulseMode);
					line.setTunnelStyle(this.tunnelStyle);
					line.setTunnelThickness(this.networkTunnelThickness);
					line.setTrafficFxStyle(this.trafficFxStyle);
					line.setPacketGlowStrength(this.packetGlowStrength);
					line.setVolumeEnergyStyle(this.volumeEnergyStyle);
					line.setCurveSeed(hashString(lineId));
					line.setColor(hub.color, networkPacketColorFor(this.networkPaletteMode));
					this.lines.set(lineId, line);
					this.scene.scene.add(line.object);
				} else {
					this.lines.get(lineId)?.setColor(color, networkPacketColorFor(this.networkPaletteMode));
				}
			}
		}

		// --- volume hubs (named volumes shared by 2+ containers) ---
		const volumeMembers = new Map<string, string[]>();
		for (const c of mergedData.containers) {
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
				const hub = new VolumeHub({ name: vol, color }, this.templates.volume);
				this.seedHubPosition(hub, volumeMembers.get(vol) ?? []);
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
					line.setCurved(this.curvedLines);
					line.setPulseMode(this.linePulseMode);
					line.setTunnelStyle(this.tunnelStyle);
					line.setTunnelThickness(this.networkTunnelThickness);
					line.setTrafficFxStyle(this.trafficFxStyle);
					line.setPacketGlowStrength(this.packetGlowStrength);
					line.setVolumeEnergyStyle(this.volumeEnergyStyle);
					line.setCurveSeed(hashString(lineId));
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
		this.pruneStale(this.groupMeshes, seenGroups, (gm) => {
			this.scene!.scene.remove(gm.object);
			gm.dispose();
		});

		// --- rewire group mesh memberships ---
		for (const [stack, gm] of this.groupMeshes) {
			const members: Array<ContainerNode | Hub> = [];
			const stackHub = this.hubs.get(`stack:${stack}`);
			if (stackHub) members.push(stackHub);
			for (const node of this.containers.values()) {
				if ((node.stack || 'Unmanaged') === stack) members.push(node);
			}
			gm.setMembers(members);
		}

		// --- apply current visibility toggles (some hubs are new) ---
		this.applyVisibility();
		this.applyNetworkTraffic(mergedData.networkTraffic);

		// --- feed layout ---
		const { entities, links } = this.buildLayoutGraph();
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

	private buildLayoutGraph(): { entities: LayoutEntityRef[]; links: LayoutLink[] } {
		const entities: LayoutEntityRef[] = [
			...Array.from(this.hubs.values()).map((h) => ({ id: h.id, position: h.position })),
			...Array.from(this.containers.values()).map((n) => ({ id: n.id, position: n.position })),
		];
		const links: LayoutLink[] = [];
		const affinityPairs = new Set<string>();
		for (const hub of this.hubs.values()) {
			for (const memberId of hub.memberIds) {
				if (this.containers.has(memberId)) {
					links.push({ source: hub.id, target: memberId });
				}
			}
			if (hub.hubType === 'network' || hub.hubType === 'volume') {
				const relatedStacks = Array.from(
					new Set(
						Array.from(hub.memberIds)
							.map((memberId) => this.containers.get(memberId)?.stack || 'Unmanaged')
							.filter(Boolean)
					)
				).sort();
				for (let i = 0; i < relatedStacks.length; i += 1) {
					for (let j = i + 1; j < relatedStacks.length; j += 1) {
						const stackA = `stack:${relatedStacks[i]}`;
						const stackB = `stack:${relatedStacks[j]}`;
						const key = `${stackA}|${stackB}`;
						if (affinityPairs.has(key)) continue;
						affinityPairs.add(key);
						links.push({ source: stackA, target: stackB });
					}
				}
			}
		}
		return { entities, links };
	}

	private seedHubPosition(hub: Hub, memberIds: readonly string[]): void {
		const anchors: THREE.Vector3[] = [];
		for (const memberId of memberIds) {
			const node = this.containers.get(memberId);
			if (!node) continue;
			const stackHub = this.hubs.get(`stack:${node.stack || 'Unmanaged'}`);
			if (stackHub) anchors.push(stackHub.position);
			else anchors.push(node.position);
		}
		if (anchors.length === 0) return;
		hub.position.set(0, 0, 0);
		for (const anchor of anchors) hub.position.add(anchor);
		hub.position.multiplyScalar(1 / anchors.length);
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
			if (hub && node) line.setEndpoints(hub.getWorldAnchor(), node.getWorldAnchor());
		}
	}

	private updateGroupMeshes(): void {
		const stackVisible = this.hubVisibility.stack;
		for (const [stack, gm] of this.groupMeshes) {
			gm.object.visible = stackVisible;
			gm.setMode(this.groupVisualMode);
			gm.setHighlighted(this.activeFocusId === `stack:${stack}`);
			if (stackVisible) gm.update();
		}
	}

	private updateNetworkTrafficVisuals(dt: number): void {
		for (const hub of this.hubs.values()) {
			if (hub instanceof NetworkHub) {
				hub.tick(dt);
			}
		}
		for (const line of this.lines.values()) {
			line.tick(dt);
		}
	}

	setNetworkTraffic(networkTraffic?: TopologyNetworkTrafficIndex): void {
		if (!this.scene) return;
		this.lastData = {
			containers: this.lastData?.containers ?? [],
			stackColors: this.lastData?.stackColors,
			networkTraffic,
		};
		this.applyNetworkTraffic(networkTraffic);
	}

	private applyNetworkTraffic(networkTraffic?: TopologyNetworkTrafficIndex): void {
		const hubRates = new Map<string, number>();
		const lineRates = new Map<string, number>();

		for (const [hubId, hub] of this.hubs) {
			if (!(hub instanceof NetworkHub)) continue;
			let totalRate = 0;
			for (const memberId of hub.memberIds) {
				const point = networkTraffic?.get(memberId)?.get(hub.name);
				const rate = point?.totalRateBps ?? 0;
				totalRate += rate;
				lineRates.set(`${hubId}->${memberId}`, rate);
			}
			hubRates.set(hubId, totalRate);
		}

		const maxHubRate = Math.max(0, ...hubRates.values());
		const maxLineRate = Math.max(0, ...lineRates.values());

		for (const [hubId, hub] of this.hubs) {
			if (hub instanceof NetworkHub) {
				hub.setTrafficLevel(normalizeTrafficLevel(hubRates.get(hubId) ?? 0, maxHubRate));
			}
		}

		for (const [lineId, line] of this.lines) {
			const parsed = parseLineId(lineId);
			if (!parsed) {
				line.setTrafficLevel(0);
				continue;
			}
			if (parsed.kind === 'network') {
				line.setTrafficLevel(normalizeTrafficLevel(lineRates.get(lineId) ?? 0, maxLineRate));
				continue;
			}
			if (parsed.kind === 'volume') {
				line.setTrafficLevel(0.3);
				continue;
			}
			line.setTrafficLevel(0);
		}
	}

	// ---- Click dispatch ----

	private handlePointerDown(event: PointerEvent): void {
		if (event.button !== 0) return;
		this.pointerDownId = event.pointerId;
		this.pointerDownX = event.clientX;
		this.pointerDownY = event.clientY;
		this.pointerMoved = false;
	}

	private handlePointerMove(event: PointerEvent): void {
		if (this.pointerDownId !== event.pointerId) return;
		const dx = event.clientX - this.pointerDownX;
		const dy = event.clientY - this.pointerDownY;
		if ((dx * dx + dy * dy) > Topology.CLICK_MOVE_THRESHOLD_PX * Topology.CLICK_MOVE_THRESHOLD_PX) {
			this.pointerMoved = true;
		}
	}

	private handlePointerUp(event: PointerEvent): void {
		if (this.pointerDownId !== event.pointerId) return;
		const isClick = !this.pointerMoved;
		this.resetPointerTracking();
		if (!isClick) return;
		this.handlePointerClick(event);
	}

	private resetPointerTracking(): void {
		this.pointerDownId = null;
		this.pointerMoved = false;
	}

	private handlePointerClick(event: MouseEvent): void {
		if (!this.scene || !this.raycaster || !this.host) return;
		const hit = this.raycaster.pickAt(event, this.host, this.scene.camera, this.scene.scene);
		if (!hit) {
			// Empty-space click → drop tooltip immediately and let the page
			// clear HUD / sidebar highlight. We don't call resetFocus()
			// here because the camera reset is disruptive; only selection
			// state is dropped.
			this.selectionTarget = null;
			this.callbacks.onEmptyClick?.();
			return;
		}
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

	/**
	 * Return the active selection projected to pixel coordinates of
	 * the given host. The Svelte layer calls this per frame to place
	 * a DOM tooltip above the canvas — avoids the z-fighting / render-
	 * order pitfalls of a 3D sprite label.
	 */
	getActiveTooltip(host: HTMLElement):
		| { text: string; x: number; y: number }
		| null {
		if (!this.scene || !this.selectionTarget) return null;
		const target = this.selectionTarget;
		const text =
			target instanceof ContainerNode || target instanceof Hub ? target.name : '';
		if (!text) return null;

		const topCentre = this.tooltipTopCentre;
		target.getTooltipAnchor(topCentre);

		const ndc = topCentre.project(this.scene.camera);
		if (ndc.z < -1 || ndc.z > 1) return null;
		const rect = host.getBoundingClientRect();
		const x = ((ndc.x + 1) / 2) * rect.width;
		const y = ((1 - (ndc.y + 1) / 2)) * rect.height;
		return { text, x, y };
	}
	private readonly tooltipTopCentre = new THREE.Vector3();

	focusContainer(id: string): void {
		const node = this.containers.get(id);
		if (!node) return;
		this.applyFocus(id, new Set([id]), node.position);
		this.animator?.fitSphere(node.position, 18);
		this.selectionTarget = node;
	}

	focusHub(id: string, _type: HubType): void {
		const hub = this.hubs.get(id);
		if (!hub) return;
		this.selectionTarget = hub;
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
		this.selectionTarget = null;
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

	// ---- Auto-rotate (Phase 5) ----

	setAutoRotate(enabled: boolean, speed: number = 1.2): void {
		if (!this.scene) return;
		// OrbitControls has built-in autoRotate; we just flip the flag
		// and ensure damping continues to drive the camera each tick.
		this.scene.controls.autoRotate = enabled;
		this.scene.controls.autoRotateSpeed = speed;
	}

	setCurvedLines(enabled: boolean): void {
		this.curvedLines = enabled;
		for (const line of this.lines.values()) {
			line.setCurved(enabled);
		}
	}

	setGroupVisualMode(mode: GroupVisualMode): void {
		this.groupVisualMode = mode;
		for (const mesh of this.groupMeshes.values()) {
			mesh.setMode(mode);
		}
	}

	setNetworkHubFxMode(mode: NetworkHubFxMode): void {
		this.networkHubFxMode = mode;
		for (const hub of this.hubs.values()) {
			if (hub instanceof NetworkHub) hub.setFxMode(mode);
		}
	}

	setLinePulseMode(mode: LinePulseMode): void {
		this.linePulseMode = mode;
		for (const line of this.lines.values()) {
			line.setPulseMode(mode);
		}
	}

	setTunnelStyle(style: TunnelStyle): void {
		this.tunnelStyle = style;
		for (const line of this.lines.values()) {
			line.setTunnelStyle(style);
		}
	}

	setNetworkTunnelThickness(multiplier: number): void {
		this.networkTunnelThickness = multiplier;
		for (const line of this.lines.values()) {
			line.setTunnelThickness(multiplier);
		}
	}

	setTrafficFxStyle(style: TrafficFxStyle): void {
		this.trafficFxStyle = style;
		for (const line of this.lines.values()) {
			line.setTrafficFxStyle(style);
		}
	}

	setNetworkPaletteMode(mode: NetworkPaletteMode): void {
		if (this.networkPaletteMode === mode) return;
		this.networkPaletteMode = mode;
		setNetworkPalette(mode);
		if (this.lastData) {
			this.update(this.lastData);
		}
	}

	setPacketGlowStrength(strength: number): void {
		this.packetGlowStrength = strength;
		for (const line of this.lines.values()) {
			line.setPacketGlowStrength(strength);
		}
	}

	setVolumeEnergyStyle(style: VolumeEnergyStyle): void {
		this.volumeEnergyStyle = style;
		for (const line of this.lines.values()) {
			line.setVolumeEnergyStyle(style);
		}
	}

	setBloomStrength(strength: number): void {
		this.bloomStrength = strength;
		this.scene?.setBloomStrength(strength);
	}

	setContainerGeometryStyle(style: ContainerGeometryStyle): void {
		if (this.containerGeometryStyle === style) return;
		this.containerGeometryStyle = style;
		if (!this.scene || !this.lastData) return;
		for (const node of this.containers.values()) {
			this.scene.scene.remove(node.object);
			node.dispose();
		}
		this.containers.clear();
		this.update(this.lastData);
	}

	// ---- Visibility API (Phase 3) ----

	setHubVisibility(type: HubType, visible: boolean): void {
		if (this.hubVisibility[type] === visible) return;
		this.hubVisibility[type] = visible;
		if (!visible && this.activeFocusId?.startsWith(`${type}:`)) {
			this.resetFocus();
		}
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
		// Group meshes follow stack visibility. Per-tick updateGroupMeshes
		// also sets this, but apply it here so the first frame after a
		// toggle is consistent even before the next tick runs.
		for (const gm of this.groupMeshes.values()) {
			gm.object.visible = this.hubVisibility.stack;
		}
	}

	private rebuildLayoutLinks(): void {
		if (!this.layout) return;
		const { entities, links } = this.buildLayoutGraph();
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
		if (this.loadingWatchdog) {
			clearTimeout(this.loadingWatchdog);
			this.loadingWatchdog = null;
		}
		if (this.loadingSceneHoldTimer) {
			clearTimeout(this.loadingSceneHoldTimer);
			this.loadingSceneHoldTimer = null;
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
			for (const gm of this.groupMeshes.values()) {
				this.scene.scene.remove(gm.object);
				gm.dispose();
			}
			if (this.starfield) {
				this.scene.scene.remove(this.starfield.object);
				this.starfield.dispose();
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
		this.groupMeshes.clear();
		this.pinner.clear();
		this.scene = null;
		this.loop = null;
		this.layout = null;
		this.animator = null;
		this.raycaster = null;
		this.starfield = null;
		this.selectionTarget = null;
		this.host = null;
		this.activeFocusId = null;
	}
}

function normalizeTrafficLevel(value: number, maxValue: number): number {
	if (value <= 0 || maxValue <= 0) return 0;
	return THREE.MathUtils.clamp(Math.log1p(value) / Math.log1p(maxValue), 0, 1);
}
