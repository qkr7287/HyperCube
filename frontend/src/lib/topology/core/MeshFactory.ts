import * as THREE from 'three';
// @ts-ignore — three.js addon typings are resolved at runtime
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
// @ts-ignore ??safe clone for skinned / animated GLBs too
import { clone as cloneSkeleton } from 'three/addons/utils/SkeletonUtils.js';

/**
 * Loads GLB templates once and hands out clones. Meshes share the
 * original geometry (three.js clone() is shallow for geometry/material
 * references), so only per-instance materials are disposed later.
 *
 * A failed load resolves to null so callers can silently fall back to
 * their procedural geometry.
 */

export type TemplateKind = 'container' | 'stack' | 'network' | 'volume';

export type TemplateBundle = Record<TemplateKind, THREE.Object3D | null>;

// Per-kind target size (longest bbox axis after normalize).
// Containers are smaller than hubs so hubs remain visually dominant.
const TARGET_SIZE: Record<TemplateKind, number> = {
	container: 14,
	stack: 22,
	network: 30,
	volume: 22,
};

const ASSET_FILE: Record<TemplateKind, string> = {
	container: 'Container_node.glb',
	stack: 'Stack_hub.glb',
	network: 'Network_hub.glb',
	volume: 'Volume_hub.glb',
};

const cache: Partial<Record<TemplateKind, THREE.Object3D | null>> = {};
const inflight: Partial<Record<TemplateKind, Promise<THREE.Object3D | null>>> = {};

export async function loadTemplate(
	kind: TemplateKind,
	baseUrl: string
): Promise<THREE.Object3D | null> {
	if (kind === 'container') {
		cache[kind] = null;
		return null;
	}
	if (Object.prototype.hasOwnProperty.call(cache, kind)) return cache[kind] ?? null;
	if (inflight[kind]) return inflight[kind]!;

	const url = `${baseUrl}/models/${ASSET_FILE[kind]}`;
	const loader = new GLTFLoader();
	loader.setMeshoptDecoder(MeshoptDecoder);
	const promise = loader
		.loadAsync(url)
		.then((gltf: { scene: THREE.Object3D }) => {
			const normalized = normalize(gltf.scene, TARGET_SIZE[kind]);
			cache[kind] = normalized;
			delete inflight[kind];
			return normalized;
		})
		.catch((err: unknown) => {
			console.warn(`[topology] ${ASSET_FILE[kind]} failed to load:`, err);
			delete cache[kind];
			delete inflight[kind];
			return null;
		});
	inflight[kind] = promise;
	return promise;
}

export async function loadAllTemplates(baseUrl: string): Promise<TemplateBundle> {
	const kinds: TemplateKind[] = ['stack', 'network', 'volume'];
	const results = await Promise.all(kinds.map((k) => loadTemplate(k, baseUrl)));
	return {
		container: null,
		stack: results[0],
		network: results[1],
		volume: results[2],
	};
}

/**
 * Fit the imported model into a cube whose longest axis equals
 * targetSize and recenter its visual bounding box on the origin so
 * force-layout positions drive its world transform.
 *
 * The returned object is a wrapper Group whose own position is (0,0,0),
 * with the imported scene held as its child shifted by -bboxCenter.
 * Callers copy the layout position onto the wrapper.position; the
 * inner offset is preserved through cloning, so line endpoints anchor
 * at the model's visual centre instead of wherever the GLB happened
 * to place its own origin. (The previous implementation set the offset
 * on the root itself, but entity syncPosition() overwrote root.position
 * every frame and the offset was lost — line endpoints drifted into
 * empty space next to the rendered model.)
 */
function normalize(root: THREE.Object3D, targetSize: number): THREE.Object3D {
	root.updateMatrixWorld(true);

	const size = new THREE.Vector3();
	new THREE.Box3().setFromObject(root).getSize(size);
	const longest = Math.max(size.x, size.y, size.z);
	if (longest > 0) {
		const scale = targetSize / longest;
		root.scale.multiplyScalar(scale);
		root.updateMatrixWorld(true);
	}

	const center = new THREE.Vector3();
	new THREE.Box3().setFromObject(root).getCenter(center);

	const wrapper = new THREE.Group();
	wrapper.add(root);
	root.position.sub(center);
	wrapper.updateMatrixWorld(true);
	return wrapper;
}

/**
 * Back-compat alias. Some older call sites still reach for the
 * container-only loader.
 */
export function loadContainerTemplate(baseUrl: string): Promise<THREE.Object3D | null> {
	void baseUrl;
	return Promise.resolve(null);
}

export interface BuiltFromTemplate {
	object: THREE.Object3D;
	/** Non-empty only when a material override was requested. */
	materials: THREE.MeshStandardMaterial[];
}

/**
 * Clone a GLB template. When `params` is provided every child mesh
 * gets a per-instance MeshStandardMaterial so callers can mutate
 * colour without affecting other clones. When `params` is omitted
 * the original GLB materials (and their textures) are kept as-is,
 * shared across clones — use this for models whose authored look
 * should stay intact.
 */
export function buildFromTemplate(
	template: THREE.Object3D,
	params?: THREE.MeshStandardMaterialParameters
): BuiltFromTemplate {
	const object = cloneSkeleton(template);
	if (!params) {
		return { object, materials: [] };
	}
	const materials: THREE.MeshStandardMaterial[] = [];
	object.traverse((child) => {
		const mesh = child as THREE.Mesh;
		if (!mesh.isMesh) return;
		const mat = new THREE.MeshStandardMaterial(params);
		mesh.material = mat;
		materials.push(mat);
	});
	return { object, materials };
}
