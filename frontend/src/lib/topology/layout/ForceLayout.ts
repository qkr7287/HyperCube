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

export type LayoutLinkKind =
	| 'stack-member'        // stack hub → container
	| 'hub-member'          // network/volume hub → container
	| 'stack-affinity'      // stack hub ↔ stack hub (kept for layout history; strength 0)
	| 'container-affinity'; // container ↔ container, score-driven (same stack only)

export interface LayoutLink {
	readonly source: string;
	readonly target: string;
	readonly kind?: LayoutLinkKind;
	/** Used by container-affinity links to scale strength + distance. */
	readonly score?: number;
}

interface InternalNode extends SimulationNode {
	id: string;
	entity: LayoutEntityRef;
}

interface InternalLink {
	source: InternalNode;
	target: InternalNode;
}

const LINK_DISTANCE_DEFAULT = 55;
const LINK_DISTANCE_STACK_MEMBER = 38; // tighter so containers cluster inside their stack bubble
const LINK_DISTANCE_HUB_MEMBER = 70;   // network/volume hubs sit a little farther out
const LINK_MIN_DISTANCE = 38;
const LINK_MAX_DISTANCE = 110;

// Charge: stack hubs repel hard so stack territories drift apart.
// Containers / network / volume hubs use a softer charge so they don't
// fly out of their own group.
const STACK_HUB_CHARGE = -260;
const NODE_CHARGE = -45;

const STRENGTH_STACK_TO_CONTAINER = 0.95;
const STRENGTH_HUB_TO_CONTAINER = 0.22;
const STRENGTH_DEFAULT_LINK = 0.5;
const STRENGTH_AFFINITY_PER_SCORE = 0.06;
const STRENGTH_AFFINITY_MIN = 0.06;
const STRENGTH_AFFINITY_MAX = 0.35;

const COLLIDE_RADIUS_DEFAULT = 24;
const COLLIDE_STRENGTH = 0.9;
const STACK_BUBBLE_FALLBACK = 36;
const SEED_SPREAD = 220;

function isStackId(id: string): boolean { return id.startsWith('stack:'); }
function isNetworkId(id: string): boolean { return id.startsWith('network:'); }
function isVolumeId(id: string): boolean { return id.startsWith('volume:'); }

function readId(node: unknown): string {
	if (typeof node === 'string') return node;
	const v = node as { id?: string } | null;
	return v?.id ?? '';
}

function chargeStrength(node: SimulationNode): number {
	return isStackId((node as InternalNode).id) ? STACK_HUB_CHARGE : NODE_CHARGE;
}

interface RawLink {
	source: unknown;
	target: unknown;
	kind?: LayoutLinkKind;
	score?: number;
}

function linkStrengthByKind(link: RawLink): number {
	const kind = link.kind;
	if (kind === 'stack-affinity') return 0;
	if (kind === 'container-affinity') {
		const score = link.score ?? 1;
		return Math.min(STRENGTH_AFFINITY_MAX, Math.max(STRENGTH_AFFINITY_MIN, score * STRENGTH_AFFINITY_PER_SCORE));
	}
	if (kind === 'stack-member') return STRENGTH_STACK_TO_CONTAINER;
	if (kind === 'hub-member') return STRENGTH_HUB_TO_CONTAINER;
	const src = readId(link.source);
	if (isStackId(src)) return STRENGTH_STACK_TO_CONTAINER;
	if (isNetworkId(src) || isVolumeId(src)) return STRENGTH_HUB_TO_CONTAINER;
	return STRENGTH_DEFAULT_LINK;
}

function linkDistanceByKind(link: RawLink): number {
	const kind = link.kind;
	if (kind === 'container-affinity') {
		const s = Math.min(link.score ?? 1, 4);
		return 50 - s * 5; // 30 ~ 45
	}
	if (kind === 'stack-member') return LINK_DISTANCE_STACK_MEMBER;
	if (kind === 'hub-member') return LINK_DISTANCE_HUB_MEMBER;
	if (kind === 'stack-affinity') return 200; // long, but strength 0 so it doesn't pull
	return LINK_DISTANCE_DEFAULT;
}

function computeTopologySignature(entities: readonly LayoutEntityRef[], links: readonly LayoutLink[]): string {
	const ids = entities.map((e) => e.id).sort().join(',');
	const ls = links.map((l) => `${l.source}->${l.target}|${l.kind ?? ''}|${l.score ?? ''}`).sort().join(',');
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
 * Spread strategy:
 *   - Stack hubs get a strong repulsive charge AND a per-stack collide
 *     radius (computed from member count) so stack bubbles physically
 *     can't overlap.
 *   - Per-link kind: stack→container is stiff & short (containers stay
 *     inside their stack bubble); network/volume→container is loose;
 *     stack-stack affinity has strength 0 + is dropped from
 *     linkBoundsForce so co-shared-network stacks aren't clamped.
 *   - Container-container affinity edges (same stack only) score
 *     shared networks/volumes so tightly-related siblings sub-cluster
 *     inside their bubble.
 */
export class ForceLayout {
	private readonly sim: Simulation;
	private readonly nodes: Map<string, InternalNode> = new Map();
	private readonly linkBoundsForce = createLinkBoundsForce(LINK_MIN_DISTANCE, LINK_MAX_DISTANCE);
	private lastSignature = '';
	private stackBubbleRadii: Map<string, number> = new Map();

	constructor() {
		this.sim = forceSimulation([], 3)
			.force('charge', forceManyBody().strength(chargeStrength).distanceMax(700))
			.force(
				'link',
				forceLink([])
					.id((n: SimulationNode) => n.id)
					.distance(linkDistanceByKind as unknown as number)
					.strength(linkStrengthByKind as unknown as number),
			)
			.force('center', forceCenter(0, 0, 0))
			.force(
				'collide',
				forceCollide((node: SimulationNode) => {
					const id = (node as InternalNode).id;
					if (isStackId(id)) {
						return this.stackBubbleRadii.get(id) ?? STACK_BUBBLE_FALLBACK;
					}
					return COLLIDE_RADIUS_DEFAULT;
				}).strength(COLLIDE_STRENGTH),
			)
			.force('linkBounds', this.linkBoundsForce as unknown as Force<SimulationNode, undefined>)
			.alphaDecay(0.035)
			.velocityDecay(0.45);
		this.sim.stop();
	}

	/**
	 * Replace the per-stack bubble-radius table. Call BEFORE setData so
	 * the next layout pass sees the right radii. The collide force
	 * accessor reads this map per-tick so subsequent calls just
	 * re-tune live.
	 */
	setStackBubbleRadii(radii: Map<string, number>): void {
		this.stackBubbleRadii = radii;
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
			linkForce.links(
				links.map((l) => ({
					source: l.source,
					target: l.target,
					kind: l.kind,
					score: l.score,
				})),
			);
		}
		for (const link of links) {
			// Stack-stack affinity is just a soft bookkeeping link with
			// strength 0; clamping via linkBoundsForce would force the
			// hubs back together and undo the charge-driven spread.
			if (link.kind === 'stack-affinity') continue;
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
