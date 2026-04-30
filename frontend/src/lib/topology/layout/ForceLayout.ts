import {
	forceCenter,
	forceCollide,
	forceLink,
	forceManyBody,
	forceSimulation,
	type Force,
	type LinkForce,
	type Simulation,
	type SimulationNode,
} from 'd3-force-3d';
import type * as THREE from 'three';

export interface LayoutEntityRef {
	readonly id: string;
	readonly position: THREE.Vector3;
}

export interface LayoutLink {
	readonly source: string;
	readonly target: string;
}

interface InternalNode extends SimulationNode {
	id: string;
	entity: LayoutEntityRef;
}

interface InternalLink {
	source: InternalNode;
	target: InternalNode;
}

export type LayoutMode = 'force' | 'ring' | 'bubble';

const LINK_DISTANCE = 60;
const LINK_MIN_DISTANCE = 40;
const LINK_MAX_DISTANCE = 148;

const STACK_HUB_CHARGE = -120;
const NODE_CHARGE = -40;

const STRENGTH_STACK_AFFINITY = 0.08;
const STRENGTH_STACK_TO_CONTAINER = 0.95;
const STRENGTH_HUB_TO_CONTAINER = 0.25;
const STRENGTH_DEFAULT_LINK = 0.5;

const COLLIDE_RADIUS = 20;

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

function isStackId(id: string): boolean { return id.startsWith('stack:'); }
function isNetworkId(id: string): boolean { return id.startsWith('network:'); }
function isVolumeId(id: string): boolean { return id.startsWith('volume:'); }
function isContainerId(id: string): boolean {
	return !isStackId(id) && !isNetworkId(id) && !isVolumeId(id);
}

function chargeStrength(node: SimulationNode): number {
	return isStackId((node as InternalNode).id) ? STACK_HUB_CHARGE : NODE_CHARGE;
}

function linkStrengthByKind(link: { source: unknown; target: unknown }): number {
	const src = typeof link.source === 'string'
		? link.source
		: ((link.source as { id?: string } | null)?.id ?? '');
	const tgt = typeof link.target === 'string'
		? link.target
		: ((link.target as { id?: string } | null)?.id ?? '');
	if (isStackId(src) && isStackId(tgt)) return STRENGTH_STACK_AFFINITY;
	if (isStackId(src)) return STRENGTH_STACK_TO_CONTAINER;
	if (isNetworkId(src) || isVolumeId(src)) return STRENGTH_HUB_TO_CONTAINER;
	return STRENGTH_DEFAULT_LINK;
}

function ringPosition(i: number, total: number, radius: number): [number, number, number] {
	const angle = (i / Math.max(1, total)) * 2 * Math.PI;
	return [Math.cos(angle) * radius, 0, Math.sin(angle) * radius];
}

function sunflower2D(i: number, total: number, scale: number): [number, number, number] {
	const angle = i * GOLDEN_ANGLE;
	const r = scale * Math.sqrt((i + 0.5) / Math.max(1, total));
	return [Math.cos(angle) * r, 0, Math.sin(angle) * r];
}

function fibonacciSphere(i: number, total: number, radius: number): [number, number, number] {
	const phi = Math.acos(1 - (2 * (i + 0.5)) / Math.max(1, total));
	const theta = GOLDEN_ANGLE * i;
	return [
		radius * Math.cos(theta) * Math.sin(phi),
		radius * Math.sin(theta) * Math.sin(phi),
		radius * Math.cos(phi),
	];
}

function computeTopologySignature(entities: readonly LayoutEntityRef[], links: readonly LayoutLink[]): string {
	const ids = entities.map((e) => e.id).sort().join(',');
	const ls = links.map((l) => `${l.source}->${l.target}`).sort().join(',');
	return `${ids}|${ls}`;
}

function createLinkBoundsForce(minDistance: number, maxDistance: number): Force<InternalNode, undefined> {
	let links: InternalLink[] = [];

	const force = (alpha: number) => {
		for (const link of links) {
			const { source, target } = link;
			const sx = source.x ?? 0;
			const sy = source.y ?? 0;
			const sz = source.z ?? 0;
			const tx = target.x ?? 0;
			const ty = target.y ?? 0;
			const tz = target.z ?? 0;
			let dx = tx - sx;
			let dy = ty - sy;
			let dz = tz - sz;
			let distance = Math.hypot(dx, dy, dz);
			if (!distance) {
				dx = 1;
				dy = 0;
				dz = 0;
				distance = 1;
			}

			if (distance >= minDistance && distance <= maxDistance) continue;

			const desired = distance < minDistance ? minDistance : maxDistance;
			const correction = (distance - desired) / distance;
			const strength = alpha * 0.35;
			const offsetX = dx * correction * strength;
			const offsetY = dy * correction * strength;
			const offsetZ = dz * correction * strength;

			target.x = tx - offsetX;
			target.y = ty - offsetY;
			target.z = tz - offsetZ;
			source.x = sx + offsetX;
			source.y = sy + offsetY;
			source.z = sz + offsetZ;
		}
	};

	force.initialize = () => {};

	return Object.assign(force, {
		setLinks(next: InternalLink[]) {
			links = next;
			return force;
		},
	});
}

/**
 * 3D force-directed layout. Keeps a map of internal simulation nodes
 * matched to rendered entities, so adding / removing entities across
 * delta syncs never restarts layout from scratch unless needed.
 *
 * Three modes are exposed:
 *   - 'force'  (default) Per-link strength tuning. Stack hubs get a strong
 *              charge; stack→container links are stiff; network/volume
 *              links and stack-stack affinity are loose. Lets the cluster
 *              breathe organically while keeping stack territories tight.
 *   - 'ring'   Stack hubs pinned on a circle in the XZ plane. Containers
 *              are still force-driven and orbit their stack. Network /
 *              volume hubs float between related stacks. Predictable.
 *   - 'bubble' Fully deterministic. Stack hubs spread on a sunflower;
 *              members placed on a fibonacci-sphere around their hub;
 *              network / volume hubs sit at the centroid of the stacks
 *              they connect. No force motion — just static packing.
 */
export class ForceLayout {
	private readonly sim: Simulation;
	private readonly nodes: Map<string, InternalNode> = new Map();
	private readonly linkBoundsForce = createLinkBoundsForce(LINK_MIN_DISTANCE, LINK_MAX_DISTANCE);
	private lastSignature = '';
	private mode: LayoutMode = 'force';
	private lastEntities: readonly LayoutEntityRef[] = [];
	private lastLinks: readonly LayoutLink[] = [];

	constructor() {
		this.sim = forceSimulation([], 3)
			.force('charge', forceManyBody().strength(chargeStrength).distanceMax(400))
			.force(
				'link',
				forceLink([])
					.id((n: SimulationNode) => n.id)
					.distance(LINK_DISTANCE)
					.strength(linkStrengthByKind as unknown as number),
			)
			.force('center', forceCenter(0, 0, 0))
			.force('collide', forceCollide(COLLIDE_RADIUS))
			.force('linkBounds', this.linkBoundsForce as unknown as Force<SimulationNode, undefined>)
			.alphaDecay(0.035)
			.velocityDecay(0.45);
		this.sim.stop();
	}

	setData(entities: readonly LayoutEntityRef[], links: readonly LayoutLink[]): void {
		const next = new Map<string, InternalNode>();
		for (const e of entities) {
			const prev = this.nodes.get(e.id);
			if (prev) {
				prev.entity = e;
				next.set(e.id, prev);
				continue;
			}
			const seeded = e.position.lengthSq() > 0.001;
			next.set(e.id, {
				id: e.id,
				entity: e,
				x: seeded ? e.position.x : (Math.random() - 0.5) * 80,
				y: seeded ? e.position.y : (Math.random() - 0.5) * 80,
				z: seeded ? e.position.z : (Math.random() - 0.5) * 80,
			});
		}
		this.nodes.clear();
		for (const [k, v] of next) this.nodes.set(k, v);

		this.lastEntities = entities;
		this.lastLinks = links;

		const signature = computeTopologySignature(entities, links);
		const isFirstData = this.lastSignature === '';
		const structureChanged = signature !== this.lastSignature;
		this.lastSignature = signature;

		// No structural change → entity references stay current (loop above)
		// but the sim is left alone so it can finish decaying and rest.
		if (!structureChanged) return;

		this.sim.nodes(Array.from(this.nodes.values()));

		const linkForce = this.sim.force('link') as LinkForce | null;
		const resolvedLinks: InternalLink[] = [];
		if (linkForce) {
			linkForce.links(links.map((l) => ({ source: l.source, target: l.target })));
		}
		for (const link of links) {
			const source = this.nodes.get(link.source);
			const target = this.nodes.get(link.target);
			if (source && target) resolvedLinks.push({ source, target });
		}
		this.linkBoundsForce.setLinks(resolvedLinks);

		this.applyModeAnchors();

		// First mount needs a strong kick to spread the initial random seed;
		// subsequent structural deltas only need a gentle nudge so existing
		// neighbours don't get ejected.
		this.sim.alpha(isFirstData ? 0.9 : 0.3).restart();
	}

	setMode(mode: LayoutMode): void {
		if (this.mode === mode) return;
		this.mode = mode;
		this.applyModeAnchors();
		this.sim.alpha(0.4).restart();
	}

	getMode(): LayoutMode {
		return this.mode;
	}

	private applyModeAnchors(): void {
		// Reset every pin first so a previous mode's anchors don't leak
		// into the new mode (e.g. switching ring → force should free hubs).
		for (const n of this.nodes.values()) {
			n.fx = null;
			n.fy = null;
			n.fz = null;
		}
		if (this.mode === 'force') return;

		const stackIds: string[] = [];
		const stackMembers = new Map<string, string[]>();
		for (const e of this.lastEntities) {
			if (isStackId(e.id)) {
				stackIds.push(e.id);
				stackMembers.set(e.id, []);
			}
		}
		stackIds.sort();
		for (const l of this.lastLinks) {
			if (isStackId(l.source) && isContainerId(l.target)) {
				stackMembers.get(l.source)?.push(l.target);
			}
		}
		for (const arr of stackMembers.values()) arr.sort();

		const N = stackIds.length;

		if (this.mode === 'ring') {
			// Stack hubs pinned on a ring; containers free.
			const ringR = Math.max(140, N * 16);
			stackIds.forEach((sid, i) => {
				const node = this.nodes.get(sid);
				if (!node) return;
				const [x, y, z] = ringPosition(i, N, ringR);
				node.fx = x;
				node.fy = y;
				node.fz = z;
				// Snap initial position too so containers see a meaningful target.
				node.x = x;
				node.y = y;
				node.z = z;
			});
			return;
		}

		if (this.mode === 'bubble') {
			// Sunflower in XZ plane for stack hubs (visually balanced spread).
			const planeScale = Math.max(140, N * 22);
			const stackPos = new Map<string, { x: number; y: number; z: number }>();
			stackIds.forEach((sid, i) => {
				const stackNode = this.nodes.get(sid);
				if (!stackNode) return;
				const [sx, sy, sz] = sunflower2D(i, N, planeScale);
				stackNode.fx = sx;
				stackNode.fy = sy;
				stackNode.fz = sz;
				stackNode.x = sx;
				stackNode.y = sy;
				stackNode.z = sz;
				stackPos.set(sid, { x: sx, y: sy, z: sz });

				// Members on fibonacci sphere around the hub. Bubble radius
				// grows slowly with member count (cube-root) so a 20-container
				// stack isn't 5× the size of a 5-container stack.
				const memberIds = stackMembers.get(sid) ?? [];
				const sphereR = Math.max(22, 12 + Math.cbrt(memberIds.length) * 9);
				memberIds.forEach((mid, mi) => {
					const node = this.nodes.get(mid);
					if (!node) return;
					const [dx, dy, dz] = fibonacciSphere(mi, memberIds.length, sphereR);
					node.fx = sx + dx;
					node.fy = sy + dy;
					node.fz = sz + dz;
					node.x = node.fx;
					node.y = node.fy;
					node.z = node.fz;
				});
			});

			// Network / volume hubs at centroid of related stacks. We need to
			// know which stacks each hub touches: walk hub→container links and
			// look up each container's stack via the inverted member map.
			const containerToStack = new Map<string, string>();
			for (const [sid, members] of stackMembers) {
				for (const mid of members) containerToStack.set(mid, sid);
			}
			const hubRelStacks = new Map<string, Set<string>>();
			for (const l of this.lastLinks) {
				if ((isNetworkId(l.source) || isVolumeId(l.source)) && isContainerId(l.target)) {
					const sid = containerToStack.get(l.target);
					if (!sid) continue;
					if (!hubRelStacks.has(l.source)) hubRelStacks.set(l.source, new Set());
					hubRelStacks.get(l.source)!.add(sid);
				}
			}
			for (const [hubId, relStacks] of hubRelStacks) {
				const node = this.nodes.get(hubId);
				if (!node) continue;
				let cx = 0, cy = 0, cz = 0;
				let n = 0;
				for (const sid of relStacks) {
					const p = stackPos.get(sid);
					if (!p) continue;
					cx += p.x; cy += p.y; cz += p.z;
					n += 1;
				}
				if (n === 0) continue;
				node.fx = cx / n;
				// Lift hubs above the stack plane so they don't sit on top
				// of containers — gives a clear "extra layer" feel.
				node.fy = cy / n + (isNetworkId(hubId) ? 60 : -60);
				node.fz = cz / n;
				node.x = node.fx;
				node.y = node.fy;
				node.z = node.fz;
			}
		}
	}

	/** Advance the simulation one step and project positions onto entities. */
	tick(): void {
		this.sim.tick(1);
		for (const n of this.nodes.values()) {
			n.entity.position.set(n.x ?? 0, n.y ?? 0, n.z ?? 0);
		}
	}

	stop(): void {
		this.sim.stop();
	}

	pin(id: string): void {
		const n = this.nodes.get(id);
		if (!n) return;
		n.fx = n.x ?? 0;
		n.fy = n.y ?? 0;
		n.fz = n.z ?? 0;
	}

	unpin(id: string): void {
		const n = this.nodes.get(id);
		if (!n) return;
		n.fx = null;
		n.fy = null;
		n.fz = null;
	}

	unpinAll(): void {
		// In ring / bubble modes the user may legitimately reset focus, but
		// the mode anchors are *not* user pins — they must be re-applied.
		for (const n of this.nodes.values()) {
			n.fx = null;
			n.fy = null;
			n.fz = null;
		}
		this.applyModeAnchors();
	}

	hasNode(id: string): boolean {
		return this.nodes.has(id);
	}

	getPosition(id: string): { x: number; y: number; z: number } | null {
		const n = this.nodes.get(id);
		if (!n) return null;
		return { x: n.x ?? 0, y: n.y ?? 0, z: n.z ?? 0 };
	}
}
