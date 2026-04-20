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
				opacity: 1,
				dashSize: 5,
				gapSize: 2.5,
			})
		);
		this.enablePackets(0xffffff, 7, 0.34, 4);
		this.enableTunnelVisual(color, 2.1);
	}
}
