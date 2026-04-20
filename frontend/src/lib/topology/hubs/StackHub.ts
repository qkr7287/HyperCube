import * as THREE from 'three';
import { buildFromTemplate } from '../core/MeshFactory';
import { Hub } from '../entities/Hub';

const FALLBACK_GEOMETRY = new THREE.IcosahedronGeometry(18, 1);

export interface StackHubData {
	name: string;
	color: number;
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
			materials = built.materials;
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
