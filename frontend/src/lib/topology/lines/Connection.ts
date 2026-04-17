import * as THREE from 'three';

/**
 * Base single-segment line between a hub and a container. Subclasses
 * pick the material (solid / dashed / dotted) and color.
 */
export abstract class Connection {
	readonly object: THREE.Line;
	protected readonly geometry: THREE.BufferGeometry;
	protected readonly material: THREE.LineBasicMaterial | THREE.LineDashedMaterial;

	protected constructor(material: THREE.LineBasicMaterial | THREE.LineDashedMaterial) {
		this.geometry = new THREE.BufferGeometry();
		this.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
		this.material = material;
		this.object = new THREE.Line(this.geometry, material);
		// Lines must never be pickable — only containers and hubs can be
		// clicked. Without this, a line in front of a distant hub can
		// absorb the ray and the picker falls through to an unrelated
		// node behind it.
		this.object.raycast = () => {};
	}

	setEndpoints(a: THREE.Vector3, b: THREE.Vector3): void {
		const pos = this.geometry.attributes.position as THREE.BufferAttribute;
		pos.setXYZ(0, a.x, a.y, a.z);
		pos.setXYZ(1, b.x, b.y, b.z);
		pos.needsUpdate = true;
		if (this.material instanceof THREE.LineDashedMaterial) {
			this.object.computeLineDistances();
		}
	}

	dispose(): void {
		this.geometry.dispose();
		this.material.dispose();
	}
}
