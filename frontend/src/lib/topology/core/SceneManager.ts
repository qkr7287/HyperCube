import * as THREE from 'three';
// @ts-ignore — three.js addon typings are resolved at runtime
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
// @ts-ignore
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
// @ts-ignore
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
// @ts-ignore
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

/**
 * Owns three.js Scene / Camera / Renderer / OrbitControls + an
 * EffectComposer with a bloom pass so emissive hubs glow without
 * every entity needing its own sprite halo. Handles container
 * sizing and controlled disposal so nothing leaks on server switch
 * or unmount.
 */
export class SceneManager {
	readonly scene: THREE.Scene;
	readonly camera: THREE.PerspectiveCamera;
	readonly renderer: THREE.WebGLRenderer;
	readonly controls: OrbitControls;
	private readonly composer: EffectComposer;

	private readonly host: HTMLElement;
	private readonly resizeObserver: ResizeObserver;

	constructor(host: HTMLElement) {
		this.host = host;

		this.scene = new THREE.Scene();
		this.scene.background = new THREE.Color(0x0d1117);

		this.camera = new THREE.PerspectiveCamera(60, 1, 0.1, 10000);
		this.camera.position.set(0, 0, 500);

		this.renderer = new THREE.WebGLRenderer({ antialias: true });
		this.renderer.setPixelRatio(window.devicePixelRatio);
		host.appendChild(this.renderer.domElement);

		this.controls = new OrbitControls(this.camera, this.renderer.domElement);
		this.controls.enableDamping = true;
		this.controls.dampingFactor = 0.08;

		this.composer = new EffectComposer(this.renderer);
		this.composer.addPass(new RenderPass(this.scene, this.camera));
		const bloomPass = new UnrealBloomPass(
			new THREE.Vector2(host.clientWidth || 1, host.clientHeight || 1),
			0.75, // strength
			0.35, // radius
			0.82 // threshold — keeps dim nebula/background out of the bloom
		);
		this.composer.addPass(bloomPass);

		this.applySize();
		this.resizeObserver = new ResizeObserver(() => this.applySize());
		this.resizeObserver.observe(host);
	}

	private applySize(): void {
		const w = this.host.clientWidth || 1;
		const h = this.host.clientHeight || 1;
		this.renderer.setSize(w, h, false);
		this.composer.setSize(w, h);
		this.camera.aspect = w / h;
		this.camera.updateProjectionMatrix();
	}

	render(): void {
		this.controls.update();
		this.composer.render();
	}

	dispose(): void {
		this.resizeObserver.disconnect();
		this.controls.dispose();
		this.composer.dispose?.();
		// Force the WebGL context to release before the renderer and canvas
		// go away. Without this, repeated server switches can leave GPU
		// contexts alive until GC and eventually exhaust the browser's
		// fixed WebGL context budget.
		try {
			this.renderer.forceContextLoss();
		} catch {
			/* some drivers throw on dead contexts — safe to ignore */
		}
		this.renderer.dispose();
		if (this.renderer.domElement.parentElement === this.host) {
			this.host.removeChild(this.renderer.domElement);
		}
	}
}
