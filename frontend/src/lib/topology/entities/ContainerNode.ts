import * as THREE from 'three';
import { Entity } from './Entity';

const CONTAINER_GEOMETRY = new THREE.CylinderGeometry(8, 8, 12, 6);
CONTAINER_GEOMETRY.rotateX(Math.PI / 2);

const STATE_COLOR: Record<string, number> = {
	running: 0x30d5c8,
	paused: 0xfbbf24,
	restarting: 0x60a5fa,
};
const STOPPED_COLOR = 0xef4444;

function colorFor(state: string): number {
	return STATE_COLOR[state] ?? STOPPED_COLOR;
}

export interface ContainerNodeData {
	id: string;
	name: string;
	state: string;
	stack: string;
}

export class ContainerNode extends Entity {
	readonly kind = 'container' as const;
	readonly id: string;
	name: string;
	state: string;
	stack: string;

	constructor(data: ContainerNodeData) {
		const color = colorFor(data.state);
		const material = new THREE.MeshStandardMaterial({
			color,
			emissive: color,
			emissiveIntensity: 0.25,
			roughness: 0.35,
			metalness: 0.1,
		});
		super(new THREE.Mesh(CONTAINER_GEOMETRY, material));
		this.id = data.id;
		this.name = data.name;
		this.state = data.state;
		this.stack = data.stack;
	}

	update(data: ContainerNodeData): void {
		this.name = data.name;
		this.stack = data.stack;
		if (data.state !== this.state) {
			this.state = data.state;
			const mat = (this.object as THREE.Mesh).material as THREE.MeshStandardMaterial;
			const color = colorFor(this.state);
			mat.color.setHex(color);
			mat.emissive.setHex(color);
		}
	}

	dispose(): void {
		const mesh = this.object as THREE.Mesh;
		(mesh.material as THREE.Material).dispose();
		// shared geometry is module-level and never disposed per-instance
	}
}
