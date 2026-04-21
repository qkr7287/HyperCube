import * as THREE from 'three';
import { Connection } from './Connection';

/**
 * Solid line, stack-hub color. Phase 1.
 */
export class StackLine extends Connection {
	constructor(color: number) {
		super(
			new THREE.LineBasicMaterial({
				color,
				transparent: true,
				opacity: 0.9,
			})
		);
	}
}
