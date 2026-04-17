import * as THREE from 'three';
import { Connection } from './Connection';

/**
 * Short-dash line for network hub links. Distinct from the solid
 * stack line and the long-dash volume line.
 */
export class NetworkLine extends Connection {
	constructor(color: number) {
		super(
			new THREE.LineDashedMaterial({
				color,
				transparent: true,
				opacity: 0.5,
				dashSize: 4,
				gapSize: 3,
			})
		);
	}
}
