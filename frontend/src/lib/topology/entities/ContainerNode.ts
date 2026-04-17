import * as THREE from 'three';
import { Entity } from './Entity';

const FALLBACK_GEOMETRY = new THREE.CylinderGeometry(8, 8, 12, 6);
FALLBACK_GEOMETRY.rotateX(Math.PI / 2);

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

/**
 * A container node is rendered from a GLB template if one is
 * available, otherwise from the cached fallback cylinder. When a
 * template is supplied we deep-clone it; three.js' clone() reuses
 * the geometry by reference, so only per-instance materials get
 * disposed — the template geometry stays alive for the next clone.
 */
export class ContainerNode extends Entity {
	readonly kind = 'container' as const;
	readonly id: string;
	name: string;
	state: string;
	stack: string;

	private readonly materials: THREE.MeshStandardMaterial[];

	constructor(data: ContainerNodeData, template: THREE.Object3D | null = null) {
		const color = colorFor(data.state);
		let object: THREE.Object3D;
		const materials: THREE.MeshStandardMaterial[] = [];

		if (template) {
			object = template.clone(true);
			object.traverse((child) => {
				const mesh = child as THREE.Mesh;
				if (!mesh.isMesh) return;
				const mat = new THREE.MeshStandardMaterial({
					color,
					emissive: color,
					emissiveIntensity: 0.3,
					roughness: 0.4,
					metalness: 0.15,
				});
				mesh.material = mat;
				materials.push(mat);
			});
		} else {
			const mat = new THREE.MeshStandardMaterial({
				color,
				emissive: color,
				emissiveIntensity: 0.25,
				roughness: 0.35,
				metalness: 0.1,
			});
			object = new THREE.Mesh(FALLBACK_GEOMETRY, mat);
			materials.push(mat);
		}

		super(object);
		this.id = data.id;
		this.name = data.name;
		this.state = data.state;
		this.stack = data.stack;
		this.materials = materials;
	}

	update(data: ContainerNodeData): void {
		this.name = data.name;
		this.stack = data.stack;
		if (data.state !== this.state) {
			this.state = data.state;
			const color = colorFor(this.state);
			for (const mat of this.materials) {
				mat.color.setHex(color);
				mat.emissive.setHex(color);
			}
		}
	}

	dispose(): void {
		// Geometry is shared (fallback module-level or GLB template),
		// so only per-instance materials are disposed here.
		for (const mat of this.materials) mat.dispose();
	}
}
