import * as THREE from 'three';

export type EntityKind = 'container' | 'hub';

/**
 * Base class for every selectable / layoutable object in the scene.
 * Position is owned by the layout engine; syncPosition() copies it
 * onto the three.js object before rendering.
 */
export abstract class Entity {
	abstract readonly id: string;
	abstract readonly kind: EntityKind;
	readonly position: THREE.Vector3 = new THREE.Vector3();
	readonly object: THREE.Object3D;
	private readonly anchorBox = new THREE.Box3();
	private readonly anchorCenter = new THREE.Vector3();

	protected constructor(object: THREE.Object3D) {
		this.object = object;
		(object.userData as { entity?: Entity }).entity = this;
		this.object.traverse((child) => {
			if ('renderOrder' in child) {
				(child as THREE.Object3D).renderOrder = 10;
			}
		});
	}

	syncPosition(): void {
		this.object.position.copy(this.position);
	}

	getWorldAnchor(): THREE.Vector3 {
		this.object.updateMatrixWorld(true);
		this.anchorBox.setFromObject(this.object);
		if (!this.anchorBox.isEmpty()) {
			this.anchorBox.getCenter(this.anchorCenter);
			return this.anchorCenter;
		}
		return this.object.getWorldPosition(this.anchorCenter);
	}

	abstract dispose(): void;
}
