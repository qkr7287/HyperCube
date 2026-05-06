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
	// Separate group for non-position FX (FOV punch) so a follow-up
	// position tween calling group.removeAll() can't kill the punch
	// mid-flight.
	private readonly fxGroup = new Group();
	private readonly initialPosition: THREE.Vector3;
	private readonly initialTarget: THREE.Vector3;
	private readonly fovBaseline: number;
	private active = false;

	constructor(camera: THREE.PerspectiveCamera, controls: { target: THREE.Vector3 }) {
		this.camera = camera;
		this.controls = controls;
		this.initialPosition = camera.position.clone();
		this.initialTarget = controls.target.clone();
		this.fovBaseline = camera.fov;
	}

	setHome(position: THREE.Vector3, target: THREE.Vector3, snap = false): void {
		this.initialPosition.copy(position);
		this.initialTarget.copy(target);
		if (snap) {
			this.cancel();
			this.camera.position.copy(position);
			this.controls.target.copy(target);
		}
	}

	setHomeFromSphere(center: THREE.Vector3, radius: number, snap = false): void {
		const safeRadius = Math.max(radius, 40);
		const fovRad = (this.camera.fov * Math.PI) / 180;
		const dist = (safeRadius * 1.9) / Math.tan(fovRad / 2);
		const offset = new THREE.Vector3(dist * 0.62, dist * 0.4, dist * 0.62);
		const position = center.clone().add(offset);
		this.setHome(position, center, snap);
	}

	setHomeFromCount(center: THREE.Vector3, count: number, snap = false): void {
		const safeCount = Math.max(count, 1);
		const dist = 420 + Math.sqrt(safeCount) * 48;
		const offset = new THREE.Vector3(dist * 0.62, dist * 0.4, dist * 0.62);
		const position = center.clone().add(offset);
		this.setHome(position, center, snap);
	}

	tick(): void {
		this.group.update();
		this.fxGroup.update();
	}

	isActive(): boolean {
		return this.active;
	}

	tweenTo(targetPos: THREE.Vector3, lookAt: THREE.Vector3, duration = 1100): void {
		this.group.removeAll();
		this.active = true;
		const startPos = this.camera.position.clone();
		const startTarget = this.controls.target.clone();
		new Tween({ t: 0 }, this.group)
			.to({ t: 1 }, duration)
			.easing(Easing.Quintic.InOut)
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
	fitSphere(center: THREE.Vector3, radius: number, duration = 1100): void {
		const safeRadius = Math.max(radius, 25);
		const fovRad = (this.camera.fov * Math.PI) / 180;
		const dist = (safeRadius * 1.6) / Math.tan(fovRad / 2);
		// Isometric-ish angle so depth is readable.
		const offset = new THREE.Vector3(dist * 0.55, dist * 0.35, dist * 0.55);
		const targetPos = center.clone().add(offset);
		this.tweenTo(targetPos, center, duration);
	}

	/**
	 * Cinematic "zoom impact" on click — narrow FOV briefly, then
	 * relax back. Runs in parallel with the position tween via fxGroup.
	 * Baseline is the constructor-time fov so repeated punches never
	 * drift the resting fov.
	 */
	punchFov(deltaDeg = 2.5, downMs = 220, upMs = 700): void {
		this.fxGroup.removeAll();
		const baseline = this.fovBaseline;
		const target = baseline - Math.abs(deltaDeg);
		const camera = this.camera;
		const state = { fov: camera.fov };
		const apply = (v: number) => {
			camera.fov = v;
			camera.updateProjectionMatrix();
		};
		const release = new Tween(state, this.fxGroup)
			.to({ fov: baseline }, upMs)
			.easing(Easing.Quadratic.Out)
			.onUpdate(({ fov }) => apply(fov));
		new Tween(state, this.fxGroup)
			.to({ fov: target }, downMs)
			.easing(Easing.Cubic.Out)
			.onUpdate(({ fov }) => apply(fov))
			.chain(release)
			.start();
	}

	resetCamera(duration = 1100): void {
		this.tweenTo(this.initialPosition.clone(), this.initialTarget.clone(), duration);
	}

	cancel(): void {
		this.group.removeAll();
		this.fxGroup.removeAll();
		// Snap fov back to baseline so a cancel mid-punch doesn't leave
		// the camera locked in a narrowed view.
		this.camera.fov = this.fovBaseline;
		this.camera.updateProjectionMatrix();
		this.active = false;
	}
}
