import type * as THREE from 'three';

/**
 * Active focus — the entities that should gather near a target point
 * and (implicitly) everything else that should scatter away.
 */
export interface FocusDescriptor {
	readonly focusId: string;
	readonly related: ReadonlySet<string>;
	readonly center: THREE.Vector3;
}
