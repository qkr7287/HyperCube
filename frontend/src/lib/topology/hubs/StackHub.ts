import * as THREE from 'three';
import { buildFromTemplate } from '../core/MeshFactory';
import { Hub } from '../entities/Hub';

const FALLBACK_GEOMETRY = new THREE.IcosahedronGeometry(18, 1);

export interface StackHubData {
	name: string;
	color: number;
}

function isTintableMaterial(mat: THREE.Material): mat is THREE.MeshStandardMaterial {
	return 'emissive' in mat && 'emissiveIntensity' in mat;
}

// Clone the GLB-shared material(s) into per-instance copies. Without
// this, every StackHub points at the same MeshStandardMaterial coming
// out of the template — so when the click-focus pipeline writes
// `m.opacity = 0.18` to dim the *other* stack hubs, the focused hub's
// material is mutated too and it appears dimmed. Per-instance clones
// keep each hub's dim/focus state isolated.
function cloneMaterialSet(
	src: THREE.Material | THREE.Material[],
	into: THREE.MeshStandardMaterial[]
): THREE.Material | THREE.Material[] {
	if (Array.isArray(src)) {
		return src.map((mat) => {
			const cloned = mat.clone();
			if (isTintableMaterial(cloned)) into.push(cloned);
			return cloned;
		});
	}
	const cloned = src.clone();
	if (isTintableMaterial(cloned)) into.push(cloned);
	return cloned;
}

export class StackHub extends Hub {
	readonly hubType = 'stack' as const;
	readonly id: string;
	name: string;
	color: number;

	private readonly materials: THREE.MeshStandardMaterial[];

	constructor(data: StackHubData, template: THREE.Object3D | null = null) {
		const params: THREE.MeshStandardMaterialParameters = {
			color: data.color,
			emissive: data.color,
			emissiveIntensity: 0.4,
			roughness: 0.25,
			metalness: 0.35,
			transparent: true,
			opacity: 0.9,
		};

		let object: THREE.Object3D;
		let materials: THREE.MeshStandardMaterial[];
		if (template) {
			const built = buildFromTemplate(template);
			object = built.object;
			materials = [];
			object.traverse((child) => {
				const mesh = child as THREE.Mesh;
				if (!mesh.isMesh) return;
				mesh.material = cloneMaterialSet(mesh.material, materials);
			});
		} else {
			const mat = new THREE.MeshStandardMaterial(params);
			object = new THREE.Mesh(FALLBACK_GEOMETRY, mat);
			materials = [mat];
		}

		super(object);
		this.id = `stack:${data.name}`;
		this.name = data.name;
		this.color = data.color;
		this.materials = materials;
	}

	update(data: StackHubData): void {
		this.name = data.name;
		if (data.color !== this.color) {
			this.color = data.color;
			for (const mat of this.materials) {
				mat.color.setHex(data.color);
				mat.emissive.setHex(data.color);
			}
		}
	}

	dispose(): void {
		for (const mat of this.materials) mat.dispose();
	}
}
