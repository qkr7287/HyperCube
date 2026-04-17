import * as THREE from 'three';
// @ts-ignore — three.js addon typings are resolved at runtime
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

/**
 * Loads GLB templates once and hands out clones. Meshes share the
 * original geometry (three.js clone() is shallow for geometry/material
 * references), so only per-instance materials are disposed later.
 *
 * A failed load resolves to null so callers can silently fall back to
 * their procedural geometry.
 */

let cachedContainer: THREE.Object3D | null = null;
let containerPromise: Promise<THREE.Object3D | null> | null = null;

export async function loadContainerTemplate(
	baseUrl: string
): Promise<THREE.Object3D | null> {
	if (cachedContainer) return cachedContainer;
	if (containerPromise) return containerPromise;

	const url = `${baseUrl}/models/container.glb`;
	const loader = new GLTFLoader();
	containerPromise = loader
		.loadAsync(url)
		.then((gltf: { scene: THREE.Object3D }) => {
			cachedContainer = normalize(gltf.scene);
			return cachedContainer;
		})
		.catch((err: unknown) => {
			console.warn('[topology] container.glb failed to load:', err);
			containerPromise = null;
			return null;
		});
	return containerPromise;
}

/**
 * Fit the imported model into a cube of roughly the same size the
 * old CylinderGeometry occupied (diameter ~16) and center it on the
 * origin so the force-layout position drives its world transform.
 */
function normalize(root: THREE.Object3D): THREE.Object3D {
	const box = new THREE.Box3().setFromObject(root);
	const size = new THREE.Vector3();
	box.getSize(size);
	const diameter = Math.max(size.x, size.y, size.z);
	const targetDiameter = 16;

	if (diameter > 0) {
		const scale = targetDiameter / diameter;
		root.scale.multiplyScalar(scale);
		root.updateMatrixWorld(true);
	}

	const center = new THREE.Vector3();
	new THREE.Box3().setFromObject(root).getCenter(center);
	root.position.sub(center);
	root.updateMatrixWorld(true);

	return root;
}
