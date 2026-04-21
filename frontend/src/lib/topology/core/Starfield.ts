import * as THREE from 'three';

interface Disposable {
	geometry: THREE.BufferGeometry;
	material: THREE.Material;
}

/**
 * Multi-layer starfield with a soft nebula shell. Kept as a separate
 * entity so Topology.mount just does `scene.add(starfield.object)` and
 * drops it through Disposer on teardown.
 *
 * Slow rotation on both axes gives the cluster a feeling of depth
 * without the camera having to move.
 */
export class Starfield {
	readonly object: THREE.Group;
	private readonly disposables: Disposable[] = [];

	constructor() {
		this.object = new THREE.Group();
		this.addStarLayer(2800, 500, 1200, 0xaabbcc, 0.75, 0.24);
		this.addStarLayer(1000, 350, 800, 0xffffff, 1.25, 0.44);
		this.addStarLayer(70, 300, 600, 0xffffff, 2.5, 0.72);
		this.addStarLayer(150, 400, 900, 0x4fc3f7, 1.5, 0.28);
		this.addStarLayer(80, 400, 900, 0xffaa44, 1.3, 0.18);
		this.addStarLayer(60, 450, 900, 0xbb77ff, 1.35, 0.16);
		this.addNebulae([0x1a0a3e, 0x0a1a3e, 0x0a2a2a]);
	}

	private addStarLayer(
		count: number,
		minR: number,
		maxR: number,
		color: number,
		size: number,
		opacity: number
	): void {
		const positions = new Float32Array(count * 3);
		for (let i = 0; i < count; i++) {
			const r = minR + Math.random() * (maxR - minR);
			const theta = Math.random() * Math.PI * 2;
			const phi = Math.acos(2 * Math.random() - 1);
			positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
			positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
			positions[i * 3 + 2] = r * Math.cos(phi);
		}
		const geometry = new THREE.BufferGeometry();
		geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
		const material = new THREE.PointsMaterial({
			color,
			size,
			transparent: true,
			opacity,
			sizeAttenuation: true,
		});
		this.object.add(new THREE.Points(geometry, material));
		this.disposables.push({ geometry, material });
	}

	private addNebulae(colors: number[]): void {
		colors.forEach((color, i) => {
			const geometry = new THREE.SphereGeometry(600 + i * 150, 16, 16);
			const material = new THREE.MeshBasicMaterial({
				color,
				transparent: true,
				opacity: 0.08 - i * 0.02,
				side: THREE.BackSide,
				depthWrite: false,
			});
			const mesh = new THREE.Mesh(geometry, material);
			mesh.rotation.set(i * 0.5, i * 0.8, i * 0.3);
			this.object.add(mesh);
			this.disposables.push({ geometry, material });
		});
	}

	tick(dt: number): void {
		this.object.rotation.y += dt * 0.006;
		this.object.rotation.x += dt * 0.002;
	}

	dispose(): void {
		for (const { geometry, material } of this.disposables) {
			geometry.dispose();
			material.dispose();
		}
		this.object.clear();
		this.disposables.length = 0;
	}
}
