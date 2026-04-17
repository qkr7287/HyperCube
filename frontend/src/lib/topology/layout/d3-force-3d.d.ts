/**
 * Minimal ambient typing for d3-force-3d. The published package has
 * no types; we only use the subset below.
 */
declare module 'd3-force-3d' {
	export interface SimulationNode {
		id: string;
		x?: number;
		y?: number;
		z?: number;
		vx?: number;
		vy?: number;
		vz?: number;
		fx?: number | null;
		fy?: number | null;
		fz?: number | null;
	}

	export interface SimulationLink {
		source: string | SimulationNode;
		target: string | SimulationNode;
	}

	export interface Force {
		(alpha?: number): void;
		initialize?: (nodes: SimulationNode[]) => void;
	}

	export interface Simulation {
		nodes(nodes: SimulationNode[]): this;
		nodes(): SimulationNode[];
		force(name: string, force: Force | null): this;
		force(name: string): Force | null;
		alpha(v: number): this;
		alphaTarget(v: number): this;
		alphaDecay(v: number): this;
		velocityDecay(v: number): this;
		restart(): this;
		stop(): this;
		tick(iterations?: number): this;
		on(event: 'tick' | 'end', cb: () => void): this;
	}

	export function forceSimulation(nodes?: SimulationNode[], dimensions?: number): Simulation;

	export interface LinkForce extends Force {
		id(fn: (n: SimulationNode) => string): this;
		distance(v: number | ((l: SimulationLink) => number)): this;
		strength(v: number | ((l: SimulationLink) => number)): this;
		links(links: SimulationLink[]): this;
	}
	export function forceLink(links?: SimulationLink[]): LinkForce;

	export interface ManyBodyForce extends Force {
		strength(v: number | ((n: SimulationNode) => number)): this;
		distanceMin(v: number): this;
		distanceMax(v: number): this;
	}
	export function forceManyBody(): ManyBodyForce;

	export interface CenterForce extends Force {
		x(v: number): this;
		y(v: number): this;
		z(v: number): this;
	}
	export function forceCenter(x?: number, y?: number, z?: number): CenterForce;

	export interface CollideForce extends Force {
		radius(v: number | ((n: SimulationNode) => number)): this;
		strength(v: number): this;
		iterations(v: number): this;
	}
	export function forceCollide(radius?: number | ((n: SimulationNode) => number)): CollideForce;

	export interface RadialForce extends Force {
		radius(v: number | ((n: SimulationNode) => number)): this;
		strength(v: number | ((n: SimulationNode) => number)): this;
		x(v: number): this;
		y(v: number): this;
		z(v: number): this;
	}
	export function forceRadial(radius: number, x?: number, y?: number, z?: number): RadialForce;
}
