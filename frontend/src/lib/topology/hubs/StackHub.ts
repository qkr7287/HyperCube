import * as THREE from 'three';
import { Hub } from '../entities/Hub';

const STACK_GEOMETRY = new THREE.IcosahedronGeometry(18, 1);

export interface StackHubData {
	name: string;
	color: number;
}

export class StackHub extends Hub {
	readonly hubType = 'stack' as const;
	readonly id: string;
	name: string;
	color: number;

	constructor(data: StackHubData) {
		const material = new THREE.MeshStandardMaterial({
			color: data.color,
			emissive: data.color,
			emissiveIntensity: 0.4,
			roughness: 0.25,
			metalness: 0.35,
			transparent: true,
			opacity: 0.9,
		});
		super(new THREE.Mesh(STACK_GEOMETRY, material));
		this.id = `stack:${data.name}`;
		this.name = data.name;
		this.color = data.color;
	}

	update(data: StackHubData): void {
		this.name = data.name;
		if (data.color !== this.color) {
			this.color = data.color;
			const mat = (this.object as THREE.Mesh).material as THREE.MeshStandardMaterial;
			mat.color.setHex(data.color);
			mat.emissive.setHex(data.color);
		}
	}

	dispose(): void {
		const mat = (this.object as THREE.Mesh).material as THREE.Material;
		mat.dispose();
	}
}
