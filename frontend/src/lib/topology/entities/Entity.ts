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

	protected constructor(object: THREE.Object3D) {
		this.object = object;
		(object.userData as { entity?: Entity }).entity = this;
	}

	syncPosition(): void {
		this.object.position.copy(this.position);
	}

	abstract dispose(): void;
}
