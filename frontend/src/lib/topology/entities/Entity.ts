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
	private readonly tooltipBox = new THREE.Box3();
	private readonly tooltipTmpBox = new THREE.Box3();
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

	getTooltipAnchor(out: THREE.Vector3): THREE.Vector3 {
		const box = this.tooltipBox;
		const tmp = this.tooltipTmpBox;
		box.makeEmpty();
		this.object.traverse((child) => {
			const mesh = child as THREE.Mesh;
			if (!mesh.isMesh) return;
			if (mesh.userData?.tooltipIgnore) return;
			const geom = mesh.geometry;
			if (!geom) return;
			if (!geom.boundingBox) geom.computeBoundingBox();
			if (!geom.boundingBox) return;
			mesh.updateWorldMatrix(true, false);
			tmp.copy(geom.boundingBox).applyMatrix4(mesh.matrixWorld);
			box.union(tmp);
		});
		if (box.isEmpty()) box.setFromObject(this.object);
		if (box.isEmpty()) return this.object.getWorldPosition(out);
		out.set(
			(box.min.x + box.max.x) * 0.5,
			box.max.y,
			(box.min.z + box.max.z) * 0.5
		);
		return out;
	}

	abstract dispose(): void;
}
