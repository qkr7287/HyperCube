import * as THREE from 'three';
import { buildFromTemplate } from '../core/MeshFactory';
import { Hub } from '../entities/Hub';

const FALLBACK_GEOMETRY = new THREE.OctahedronGeometry(15, 0);

// Orange / amber family — storage connotation, distinct from stack
// and network palettes.
// Single orange shared by every volume hub / line / strand so the
// viewer can tell the kind of hub from the line colour alone.
const VOLUME_COLOR = 0xfb923c;

// Multiplier applied to the authored emissiveIntensity of every GLB
// material on a volume hub. Lowering this calms the bloom-driven
// sparkle that gets amplified when many volume hubs are on screen at
// once. Set to 1.0 to restore the original authored look.
const VOLUME_EMISSIVE_DAMP = 0.12;

// Volume hubs share one GLB template across every instance, so we only
// need to sanitise its geometry + materials once. Subsequent clones
// inherit the fixed state via shared references.
//
// The original symptom was: viewed from far away the volume model
// "지직지직" flickered as the camera orbited — classic z-fighting
// between coplanar triangles inside the authored GLB, made worse by
// logarithmic depth-buffer precision at distance and by UnrealBloom
// amplifying the winning fragment each frame.
// Remedies applied here (order matters):
//   1. Recompute vertex normals so any inverted face is consistent.
//   2. Force opaque, single-sided, depth-writing rendering — removes
//      transparency ordering ambiguity that also contributed to the
//      flicker. (Previous attempt used DoubleSide which REINTRODUCED
//      z-fight between the now-visible back faces and the front faces.)
//   3. polygonOffset pushes the volume fragments slightly forward so
//      coplanar internal triangles inside the GLB stop tying in the
//      depth test.
//   4. Neutralise the normal-map contribution that re-introduces
//      specular flicker after step 1.
//   5. Knock metalness down + raise roughness to soften specular so
//      remaining highlights are diffuse instead of stabby.
//   6. Dim emissiveIntensity (original bloom-calm fix).
let volumeTemplatePatched = false;
function patchTemplateOnce(template: THREE.Object3D): void {
	if (volumeTemplatePatched) return;
	volumeTemplatePatched = true;
	let meshIndex = 0;
	template.traverse((child) => {
		const mesh = child as THREE.Mesh;
		if (!mesh.isMesh) return;
		mesh.renderOrder = 24 + meshIndex;
		meshIndex += 1;
		// (1) Regenerate normals from the mesh positions.
		const geom = mesh.geometry;
		if (geom && typeof (geom as THREE.BufferGeometry).computeVertexNormals === 'function') {
			(geom as THREE.BufferGeometry).computeVertexNormals();
			(geom as THREE.BufferGeometry).computeBoundingSphere();
		}
		const src = mesh.material;
		if (!src) return;
		const list = Array.isArray(src) ? src : [src];
		for (const m of list) {
			const std = m as THREE.MeshStandardMaterial;
			// (2) Opaque, front-side, depth-writing.
			std.side = THREE.FrontSide;
			std.transparent = false;
			std.opacity = 1;
			std.depthTest = true;
			std.depthWrite = true;
			// (3) Nudge forward so coplanar triangles stop z-fighting.
			std.polygonOffset = true;
			std.polygonOffsetFactor = -1;
			// Each mesh gets a slightly different depth bias so overlapping
			// shells inside the authored GLB stop tying with each other at
			// distance. A single shared offset still flickers when two
			// coplanar sub-meshes occupy the same depth slice.
			std.polygonOffsetUnits = -(1 + mesh.renderOrder * 0.08);
			// (4) Kill normal-map contribution that re-introduces flicker.
			if ('normalScale' in std && std.normalScale) {
				std.normalScale.set(0, 0);
			}
			// (5) Soften specular.
			if (typeof std.metalness === 'number') {
				std.metalness = Math.min(std.metalness, 0.15);
			}
			if (typeof std.roughness === 'number') {
				std.roughness = Math.max(std.roughness, 0.6);
			}
			// (6) Dim emissive.
			if (typeof std.emissiveIntensity === 'number') {
				std.emissiveIntensity *= VOLUME_EMISSIVE_DAMP;
			}
			std.needsUpdate = true;
		}
	});
}

function volumeColorFor(_name: string, _sortedNames: readonly string[]): number {
	return VOLUME_COLOR;
}

function isTintableMaterial(mat: THREE.Material): mat is THREE.MeshStandardMaterial {
	return 'emissive' in mat && 'emissiveIntensity' in mat;
}

// Volume hubs share one GLB template, but the click-focus dim writes
// m.opacity per-instance every frame. Without per-instance material
// clones every VolumeHub points at the same material and the dimmed
// siblings' opacity write clobbers the focused hub's — same shared-
// material trap that StackHub had. Clone every mesh.material here so
// each hub's dim/focus state stays isolated.
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
			// Patch the template's geometry + materials once (shared across
			// every volume hub clone), then use the authored models.
			patchTemplateOnce(template);
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
