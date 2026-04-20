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
		// Lime capsules against the fuchsia tunnel — complementary hue
		// so traffic reads clearly, shape+orientation signal flow. The
		// capsule is rotated per-frame to the line tangent in screen
		// space (see Connection.enablePackets).
		this.enablePackets(0xa3e635, 14, 0.4, 4);
		this.enableTunnelVisual(color, 2.1);
	}
}
