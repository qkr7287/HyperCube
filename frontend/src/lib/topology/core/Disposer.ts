import * as THREE from 'three';

/**
 * Recursively disposes three.js resources owned by an Object3D.
 * Shared geometries (cached module-level) should not be passed here —
 * only per-instance resources.
 */
export class Disposer {
	dispose(obj: THREE.Object3D): void {
		obj.traverse((child) => {
			const mesh = child as THREE.Mesh;
			if (mesh.geometry) mesh.geometry.dispose();
			const mat = mesh.material;
			if (!mat) return;
			if (Array.isArray(mat)) mat.forEach((m) => this.disposeMaterial(m));
			else this.disposeMaterial(mat);
		});
	}

	private disposeMaterial(m: THREE.Material): void {
		for (const v of Object.values(m)) {
			if (v instanceof THREE.Texture) v.dispose();
		}
		m.dispose();
	}
}
