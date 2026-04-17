import * as THREE from 'three';
import { Hub } from '../entities/Hub';

const NETWORK_GEOMETRY = new THREE.TorusGeometry(14, 4, 12, 24);

// Cyan / blue family — distinct from stack palette and volume palette.
const NETWORK_COLORS: readonly number[] = [
	0x22d3ee, 0x38bdf8, 0x818cf8, 0x67e8f9, 0x7dd3fc,
];

function networkColorFor(name: string, sortedNames: readonly string[]): number {
	const idx = sortedNames.indexOf(name);
	return NETWORK_COLORS[Math.max(idx, 0) % NETWORK_COLORS.length];
}

export interface NetworkHubData {
	name: string;
	color: number;
}

export class NetworkHub extends Hub {
	readonly hubType = 'network' as const;
	readonly id: string;
	name: string;
	color: number;

	constructor(data: NetworkHubData) {
		const material = new THREE.MeshStandardMaterial({
			color: data.color,
			emissive: data.color,
			emissiveIntensity: 0.45,
			roughness: 0.3,
			metalness: 0.4,
			transparent: true,
			opacity: 0.9,
		});
		super(new THREE.Mesh(NETWORK_GEOMETRY, material));
		this.id = `network:${data.name}`;
		this.name = data.name;
		this.color = data.color;
	}

	update(data: NetworkHubData): void {
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

export { networkColorFor };
