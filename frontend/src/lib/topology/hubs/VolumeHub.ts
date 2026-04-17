import * as THREE from 'three';
import { Hub } from '../entities/Hub';

const VOLUME_GEOMETRY = new THREE.OctahedronGeometry(15, 0);

// Orange / amber family — storage connotation, distinct from stack
// and network palettes.
const VOLUME_COLORS: readonly number[] = [
	0xfb923c, 0xf97316, 0xfdba74, 0xfbbf24, 0xf59e0b,
];

function volumeColorFor(name: string, sortedNames: readonly string[]): number {
	const idx = sortedNames.indexOf(name);
	return VOLUME_COLORS[Math.max(idx, 0) % VOLUME_COLORS.length];
}

export interface VolumeHubData {
	name: string;
	color: number;
}

export class VolumeHub extends Hub {
	readonly hubType = 'volume' as const;
	readonly id: string;
	name: string;
	color: number;

	constructor(data: VolumeHubData) {
		const material = new THREE.MeshStandardMaterial({
			color: data.color,
			emissive: data.color,
			emissiveIntensity: 0.4,
			roughness: 0.35,
			metalness: 0.25,
			transparent: true,
			opacity: 0.9,
		});
		super(new THREE.Mesh(VOLUME_GEOMETRY, material));
		this.id = `volume:${data.name}`;
		this.name = data.name;
		this.color = data.color;
	}

	update(data: VolumeHubData): void {
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

export { volumeColorFor };
