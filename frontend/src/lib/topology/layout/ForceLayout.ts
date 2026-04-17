import {
	forceCenter,
	forceCollide,
	forceLink,
	forceManyBody,
	forceRadial,
	forceSimulation,
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

/**
 * 3D force-directed layout. Keeps a map of internal simulation nodes
 * matched to rendered entities, so adding / removing entities across
 * delta syncs never restarts layout from scratch unless needed.
 */
export class ForceLayout {
	private readonly sim: Simulation;
	private readonly nodes: Map<string, InternalNode> = new Map();

	constructor() {
		this.sim = forceSimulation([], 3)
			.force('charge', forceManyBody().strength(-40).distanceMax(400))
			.force('link', forceLink([]).id((n: SimulationNode) => n.id).distance(55).strength(0.7))
			.force('center', forceCenter(0, 0, 0))
			.force('collide', forceCollide(14))
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
			next.set(e.id, {
				id: e.id,
				entity: e,
				x: (Math.random() - 0.5) * 60,
				y: (Math.random() - 0.5) * 60,
				z: (Math.random() - 0.5) * 60,
			});
		}
		this.nodes.clear();
		for (const [k, v] of next) this.nodes.set(k, v);

		this.sim.nodes(Array.from(this.nodes.values()));

		const linkForce = this.sim.force('link') as LinkForce | null;
		if (linkForce) {
			linkForce.links(links.map((l) => ({ source: l.source, target: l.target })));
		}
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
	 * Install focus forces: related ids gather toward center, unrelated
	 * ids are pushed to a shell well outside the cluster. Pinned nodes
	 * are unaffected (their positions are already frozen via fx/fy/fz).
	 */
	setFocus(related: ReadonlySet<string>, center: { x: number; y: number; z: number }): void {
		const gather = forceRadial(0, center.x, center.y, center.z).strength((n: SimulationNode) =>
			related.has(n.id) ? 0.35 : 0
		);
		const scatter = forceRadial(450, center.x, center.y, center.z).strength((n: SimulationNode) =>
			related.has(n.id) ? 0 : 0.09
		);
		this.sim.force('focusGather', gather);
		this.sim.force('focusScatter', scatter);
		this.sim.alpha(0.85).restart();
	}

	clearFocus(): void {
		this.sim.force('focusGather', null);
		this.sim.force('focusScatter', null);
		this.sim.alpha(0.6).restart();
	}
}
