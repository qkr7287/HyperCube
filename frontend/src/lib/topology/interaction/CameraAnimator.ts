import { Easing, Group, Tween } from '@tweenjs/tween.js';
import * as THREE from 'three';

/**
 * Smooth curved camera moves. The animator owns a Tween.Group so
 * previous animations are cancelled on each new request, and it
 * drives the OrbitControls target in lockstep with the camera to
 * avoid the "camera moved but controls look at old origin" glitch.
 *
 * Per req #7: hub targets auto-fit a bounding sphere so the
 * connected members remain visible.
 */
export class CameraAnimator {
	private readonly camera: THREE.PerspectiveCamera;
	private readonly controls: { target: THREE.Vector3 };
	private readonly group = new Group();
	private readonly initialPosition: THREE.Vector3;
	private readonly initialTarget: THREE.Vector3;
	private active = false;

	constructor(camera: THREE.PerspectiveCamera, controls: { target: THREE.Vector3 }) {
		this.camera = camera;
		this.controls = controls;
		this.initialPosition = camera.position.clone();
		this.initialTarget = controls.target.clone();
	}

	tick(): void {
		this.group.update();
	}

	isActive(): boolean {
		return this.active;
	}

	tweenTo(targetPos: THREE.Vector3, lookAt: THREE.Vector3, duration = 900): void {
		this.group.removeAll();
		this.active = true;
		const startPos = this.camera.position.clone();
		const startTarget = this.controls.target.clone();
		new Tween({ t: 0 }, this.group)
			.to({ t: 1 }, duration)
			.easing(Easing.Cubic.InOut)
			.onUpdate(({ t }) => {
				this.camera.position.lerpVectors(startPos, targetPos, t);
				this.controls.target.lerpVectors(startTarget, lookAt, t);
			})
			.onComplete(() => {
				this.active = false;
			})
			.start();
	}

	/**
	 * Tween so the given sphere (center + radius) fills a comfortable
	 * share of the viewport.
	 */
	fitSphere(center: THREE.Vector3, radius: number, duration = 900): void {
		const safeRadius = Math.max(radius, 25);
		const fovRad = (this.camera.fov * Math.PI) / 180;
		const dist = (safeRadius * 1.6) / Math.tan(fovRad / 2);
		// Isometric-ish angle so depth is readable.
		const offset = new THREE.Vector3(dist * 0.55, dist * 0.35, dist * 0.55);
		const targetPos = center.clone().add(offset);
		this.tweenTo(targetPos, center, duration);
	}

	resetCamera(duration = 900): void {
		this.tweenTo(this.initialPosition.clone(), this.initialTarget.clone(), duration);
	}

	cancel(): void {
		this.group.removeAll();
		this.active = false;
	}
}
