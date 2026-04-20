import * as THREE from 'three';
import { buildFromTemplate } from '../core/MeshFactory';
import { Hub } from '../entities/Hub';

const FALLBACK_GEOMETRY = new THREE.OctahedronGeometry(15, 0);

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

	// Only populated on the fallback path; GLB-backed materials are
	// left untouched so the authored look is preserved.
	private readonly materials: THREE.MeshStandardMaterial[];

	constructor(data: VolumeHubData, template: THREE.Object3D | null = null) {
		const params: THREE.MeshStandardMaterialParameters = {
			color: data.color,
			emissive: data.color,
			emissiveIntensity: 0.4,
			roughness: 0.35,
			metalness: 0.25,
			transparent: true,
			opacity: 0.9,
		};

		let object: THREE.Object3D;
		let materials: THREE.MeshStandardMaterial[];
		if (template) {
			// GLB materials kept untouched — no clone, no emissive
			// overlay.
			const built = buildFromTemplate(template);
			object = built.object;
			materials = built.materials;
		} else {
			const mat = new THREE.MeshStandardMaterial(params);
			object = new THREE.Mesh(FALLBACK_GEOMETRY, mat);
			materials = [mat];
		}

		super(object);
		this.id = `volume:${data.name}`;
		this.name = data.name;
		this.color = data.color;
		this.materials = materials;
	}

	update(data: VolumeHubData): void {
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

export { volumeColorFor };
