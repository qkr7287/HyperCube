import {
	forceCenter,
	forceCollide,
	forceLink,
	forceManyBody,
	forceRadial,
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

const LINK_DISTANCE = 60;
const LINK_MIN_DISTANCE = 40;
const LINK_MAX_DISTANCE = 148;

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
 */
export class ForceLayout {
	private readonly sim: Simulation;
	private readonly nodes: Map<string, InternalNode> = new Map();
	private readonly linkBoundsForce = createLinkBoundsForce(LINK_MIN_DISTANCE, LINK_MAX_DISTANCE);

	constructor() {
		this.sim = forceSimulation([], 3)
			.force('charge', forceManyBody().strength(-40).distanceMax(400))
			.force('link', forceLink([]).id((n: SimulationNode) => n.id).distance(LINK_DISTANCE).strength(0.78))
			.force('center', forceCenter(0, 0, 0))
			.force('collide', forceCollide(14))
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
				x: seeded ? e.position.x : (Math.random() - 0.5) * 60,
				y: seeded ? e.position.y : (Math.random() - 0.5) * 60,
				z: seeded ? e.position.z : (Math.random() - 0.5) * 60,
			});
		}
		this.nodes.clear();
		for (const [k, v] of next) this.nodes.set(k, v);

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
		this.sim.alpha(0.9).restart();
	}

	/** Advance the simulation one step and project positions onto entities. */
	tick(): void {
		this.sim.tick(1);
		for (const n of this.nodes.values()) {
			n.entity.position.set(n.x ?? 0, n.y ?? 0, n.z ?? 0);
		}
	}

	reheat(alpha: number = 0.6): void {
		this.sim.alpha(alpha).restart();
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

	/**
	 * Install focus forces. Only unrelated, unpinned ids are pushed
	 * outward — related nodes are expected to be pinned at their
	 * click-time position by the caller, so a gather radial would
	 * be a no-op and just adds load. Alpha kick is small so the rest
	 * of the cluster doesn't reshuffle.
	 */
	setFocus(related: ReadonlySet<string>, center: { x: number; y: number; z: number }): void {
		const scatter = forceRadial(450, center.x, center.y, center.z).strength((n: SimulationNode) =>
			related.has(n.id) ? 0 : 0.09
		);
		this.sim.force('focusGather', null);
		this.sim.force('focusScatter', scatter);
		this.sim.alpha(0.3).restart();
	}

	clearFocus(): void {
		this.sim.force('focusGather', null);
		this.sim.force('focusScatter', null);
		this.sim.alpha(0.3).restart();
	}
}
