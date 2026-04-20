import * as THREE from 'three';
import { Connection } from './Connection';

/**
 * Long-dash line for volume hub links. Distinct from solid stack
 * line and short-dash network line.
 */
export class VolumeLine extends Connection {
	constructor(color: number) {
		super(
			new THREE.LineDashedMaterial({
				color,
				transparent: true,
				opacity: 1,
				dashSize: 9,
				gapSize: 3,
			})
		);
		this.enableEnergyLine();
	}
}
