import * as THREE from 'three';
import type { Entity } from '../entities/Entity';

/**
 * Wraps three.js Raycaster for picking entities. Walks up the object
 * parent chain so child meshes (wireframes, glow layers) still resolve
 * to their owning Entity.
 */
export class Raycaster {
	private readonly raycaster = new THREE.Raycaster();
	private readonly pointer = new THREE.Vector2();

	pickAt(
		event: MouseEvent,
		host: HTMLElement,
		camera: THREE.Camera,
		scene: THREE.Scene
	): Entity | null {
		const rect = host.getBoundingClientRect();
		if (rect.width === 0 || rect.height === 0) return null;
		this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
		this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
		this.raycaster.setFromCamera(this.pointer, camera);
		const hits = this.raycaster.intersectObjects(scene.children, true);
		for (const hit of hits) {
			const entity = this.resolveEntity(hit.object);
			if (entity) return entity;
		}
		return null;
	}

	private resolveEntity(start: THREE.Object3D): Entity | null {
		let obj: THREE.Object3D | null = start;
		while (obj) {
			const entity = (obj.userData as { entity?: Entity }).entity;
			if (entity) return entity;
			obj = obj.parent;
		}
		return null;
	}
}
