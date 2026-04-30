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

const LINK_DISTANCE = 55;
const LINK_MIN_DISTANCE = 38;
const LINK_MAX_DISTANCE = 110;

// Charge: stack hubs repel each other strongly so stack territories
// drift apart naturally. Containers / network / volume hubs use a softer
// charge so they don't fly out of their own group.
const STACK_HUB_CHARGE = -220;
const NODE_CHARGE = -55;

// Per-link strength. Stack→container is stiff (containers stay tight to
// their stack). Network / volume → container is loose (those hubs are
// supplementary information, they shouldn't dominate the layout).
// Stack-stack affinity is set to 0 so co-shared-network stacks don't get
// dragged toward each other; the linkBoundsForce also skips stack-stack
// pairs so they can be far apart without being clamped to maxDistance.
const STRENGTH_STACK_TO_CONTAINER = 0.95;
const STRENGTH_HUB_TO_CONTAINER = 0.22;
const STRENGTH_DEFAULT_LINK = 0.5;

const COLLIDE_RADIUS = 24;
const SEED_SPREAD = 160;

function isStackId(id: string): boolean { return id.startsWith('stack:'); }

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
	if (isStackId(src) && isStackId(tgt)) return 0;
	if (isStackId(src)) return STRENGTH_STACK_TO_CONTAINER;
	if (src.startsWith('network:') || src.startsWith('volume:')) return STRENGTH_HUB_TO_CONTAINER;
	return STRENGTH_DEFAULT_LINK;
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
 * Stack hubs get a much stronger repulsive charge than other nodes so
 * stack "territories" drift apart on their own; per-link strength keeps
 * each stack's containers tight while network / volume hubs sit loosely
 * between related stacks. Result: clusters look organically spread, no
 * deterministic anchors needed.
 */
export class ForceLayout {
	private readonly sim: Simulation;
	private readonly nodes: Map<string, InternalNode> = new Map();
	private readonly linkBoundsForce = createLinkBoundsForce(LINK_MIN_DISTANCE, LINK_MAX_DISTANCE);
	private lastSignature = '';

	constructor() {
		this.sim = forceSimulation([], 3)
			.force('charge', forceManyBody().strength(chargeStrength).distanceMax(600))
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
				x: seeded ? e.position.x : (Math.random() - 0.5) * SEED_SPREAD,
				y: seeded ? e.position.y : (Math.random() - 0.5) * SEED_SPREAD,
				z: seeded ? e.position.z : (Math.random() - 0.5) * SEED_SPREAD,
			});
		}
		this.nodes.clear();
		for (const [k, v] of next) this.nodes.set(k, v);

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
			// Stack-stack affinity links exist for the link force (where they
			// sit at strength 0) but must NOT be clamped by linkBoundsForce
			// — clamping would force stack hubs within maxDistance of each
			// other and undo all the charge-driven spread.
			if (isStackId(link.source) && isStackId(link.target)) continue;
			const source = this.nodes.get(link.source);
			const target = this.nodes.get(link.target);
			if (source && target) resolvedLinks.push({ source, target });
		}
		this.linkBoundsForce.setLinks(resolvedLinks);

		// First mount needs a strong kick to spread the initial random seed;
		// subsequent structural deltas only need a gentle nudge so existing
		// neighbours don't get ejected.
		this.sim.alpha(isFirstData ? 0.9 : 0.3).restart();
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
		for (const n of this.nodes.values()) {
			n.fx = null;
			n.fy = null;
			n.fz = null;
		}
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
