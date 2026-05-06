import * as THREE from 'three';

export type EntityKind = 'container' | 'hub';

// Click-focus fade duration (ms). Time-based with Cubic.InOut easing
// so the curve is symmetric — slow at the start AND end, fastest at
// the middle. The previous exp-decay lerp was front-loaded which read
// fine for the appearance (eye attention follows the rising shape)
// but felt like an instant cut on disappearance (50% brightness loss
// in the first 100ms reads as motion in peripheral vision). Cubic.InOut
// removes that asymmetry.
const FADE_DURATION_MS = 600;

// Cubic.InOut easing — slow at both ends, fast in the middle. Matches
// CameraAnimator's tween polish and reads as a natural deceleration.
function cubicInOut(t: number): number {
	if (t < 0.5) return 4 * t * t * t;
	const f = 2 * t - 2;
	return 0.5 * f * f * f + 1;
}

const FOCUSED_OPACITY = 1;
// Click-focus now fully fades out unrelated entities and toggles
// object.visible=false once they reach this threshold, so a dense
// stack-bubble doesn't visually cover the focused subset.
const DIMMED_OPACITY = 0;
// Below this opacity the entity is hidden (visible=false) so it stops
// occluding raycasts and bloom. Lowered from 0.01 so the last 1% of
// the fade still renders — additive-blended materials and bloom can
// still register a slight presence at 0.01, which read as a snap when
// visible=false flipped a frame later.
const HIDE_OPACITY_THRESHOLD = 0.001;
const FOCUSED_SCALE = 1.18;
const FOCUSED_EMISSIVE_BOOST = 6;

const SETTLED_EPSILON = 0.001;

interface MaterialBaseline {
	baseOpacity: number;
	baseEmissive: number;
}

/**
 * Base class for every selectable / layoutable object in the scene.
 * Position is owned by the layout engine; syncPosition() copies it
 * onto the three.js object before rendering.
 *
 * Also owns smoothly-animated per-entity visual state (dim / focus /
 * scale). Topology calls tick(dt) every frame; the default
 * applyVisualState() walks every material on the object and multiplies
 * opacity / emissiveIntensity by the lerped factors. Subclasses that
 * already drive their own per-frame material animation (e.g.
 * NetworkHub) should override applyVisualState() to incorporate the
 * factors into their existing math instead of letting the base class
 * fight them.
 */
export abstract class Entity {
	abstract readonly id: string;
	abstract readonly kind: EntityKind;
	readonly position: THREE.Vector3 = new THREE.Vector3();
	readonly object: THREE.Object3D;
	private readonly anchorBox = new THREE.Box3();
	private readonly tooltipBox = new THREE.Box3();
	private readonly tooltipTmpBox = new THREE.Box3();
	private readonly anchorCenter = new THREE.Vector3();

	// Animated visual state. target is what we're tweening toward,
	// current is where we are right now (driven by tick), fadeStart is
	// the snapshot taken when target last changed so the easing always
	// runs from "wherever we are now" rather than restarting from full.
	private targetOpacity = FOCUSED_OPACITY;
	protected currentOpacity = FOCUSED_OPACITY;
	private fadeStartOpacity = FOCUSED_OPACITY;
	private targetEmissiveBoost = 1;
	protected currentEmissiveBoost = 1;
	private fadeStartBoost = 1;
	private targetScale = 1;
	protected currentScale = 1;
	private fadeStartScale = 1;
	private fadeStartTime = 0;
	// True when *we* turned object.visible off via the dim fade-out, so
	// the un-dim path knows it owns re-showing this entity. External
	// hub-type visibility (Topology.applyVisibility) is tracked
	// separately and stays authoritative when dim is inactive.
	private dimHidden = false;

	protected constructor(object: THREE.Object3D) {
		this.object = object;
		(object.userData as { entity?: Entity }).entity = this;
		this.object.traverse((child) => {
			if ('renderOrder' in child) {
				(child as THREE.Object3D).renderOrder = 10;
			}
		});
	}

	syncPosition(): void {
		this.object.position.copy(this.position);
	}

	setDimmed(dimmed: boolean): void {
		this.snapshotFadeStart();
		this.targetOpacity = dimmed ? DIMMED_OPACITY : FOCUSED_OPACITY;
		// Only re-show on un-dim if we're the one that hid it. Avoids
		// reviving entities the user explicitly turned off via the
		// System Topology checkboxes.
		if (!dimmed && this.dimHidden) {
			this.object.visible = true;
			this.dimHidden = false;
		}
	}

	setFocused(focused: boolean): void {
		this.snapshotFadeStart();
		this.targetEmissiveBoost = focused ? FOCUSED_EMISSIVE_BOOST : 1;
		this.targetScale = focused ? FOCUSED_SCALE : 1;
	}

	// Capture the current animated values as the start of a fresh tween
	// segment. Without this, mid-fade target changes would "jump" because
	// the easing curve always interpolates from start to target across
	// FADE_DURATION_MS — we want each new target to ease from "now".
	private snapshotFadeStart(): void {
		this.fadeStartOpacity = this.currentOpacity;
		this.fadeStartBoost = this.currentEmissiveBoost;
		this.fadeStartScale = this.currentScale;
		this.fadeStartTime = performance.now();
	}

	/** Per-frame visual state animation. */
	tick(_dt: number): void {
		const elapsed = performance.now() - this.fadeStartTime;
		const t = Math.min(1, Math.max(0, elapsed / FADE_DURATION_MS));
		const eased = cubicInOut(t);
		this.currentOpacity = this.fadeStartOpacity + (this.targetOpacity - this.fadeStartOpacity) * eased;
		this.currentEmissiveBoost =
			this.fadeStartBoost + (this.targetEmissiveBoost - this.fadeStartBoost) * eased;
		this.currentScale = this.fadeStartScale + (this.targetScale - this.fadeStartScale) * eased;
		this.applyVisualState();
		// Once fully faded out, drop out of rendering / raycasts entirely.
		// dimHidden is what the un-dim path checks before re-showing.
		if (this.targetOpacity <= 0 && this.currentOpacity < HIDE_OPACITY_THRESHOLD) {
			if (this.object.visible) {
				this.object.visible = false;
				this.dimHidden = true;
			}
		}
	}

	/**
	 * Apply the lerped factors to the entity's three.js materials.
	 * Default implementation multiplies into a captured per-material
	 * baseline (so authored authored opacity / emissive are preserved
	 * across dim cycles). Subclasses with their own per-frame material
	 * mutation should override and apply the factors as multipliers
	 * inside their own logic.
	 */
	protected applyVisualState(): void {
		// Fast-path: at rest, no traversal. Each material was already
		// restored to its baseline on the previous frame so leaving them
		// alone is correct.
		if (this.isAtRest()) return;

		this.object.scale.setScalar(this.currentScale);
		const opacity = this.currentOpacity;
		const boost = this.currentEmissiveBoost;
		this.object.traverse((child) => {
			const mesh = child as THREE.Mesh;
			const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
			if (!mat) return;
			const list = Array.isArray(mat) ? mat : [mat];
			for (const m of list) {
				const base = this.ensureBaseline(m);
				m.transparent = true;
				m.opacity = base.baseOpacity * opacity;
				const tinted = m as THREE.MeshStandardMaterial;
				if (typeof tinted.emissiveIntensity === 'number') {
					tinted.emissiveIntensity = base.baseEmissive * boost;
				}
			}
		});
	}

	protected isAtRest(): boolean {
		return (
			Math.abs(this.currentOpacity - this.targetOpacity) < SETTLED_EPSILON &&
			Math.abs(this.targetOpacity - 1) < SETTLED_EPSILON &&
			Math.abs(this.currentEmissiveBoost - this.targetEmissiveBoost) < SETTLED_EPSILON &&
			Math.abs(this.targetEmissiveBoost - 1) < SETTLED_EPSILON &&
			Math.abs(this.currentScale - this.targetScale) < SETTLED_EPSILON &&
			Math.abs(this.targetScale - 1) < SETTLED_EPSILON
		);
	}

	protected ensureBaseline(mat: THREE.Material): MaterialBaseline {
		const slot = mat.userData as { __entityBaseline?: MaterialBaseline };
		if (!slot.__entityBaseline) {
			slot.__entityBaseline = {
				baseOpacity: mat.opacity,
				baseEmissive: typeof (mat as THREE.MeshStandardMaterial).emissiveIntensity === 'number'
					? (mat as THREE.MeshStandardMaterial).emissiveIntensity
					: 0,
			};
		}
		return slot.__entityBaseline;
	}

	/**
	 * Drop cached material baselines so the next tick re-captures them.
	 * Call this from a subclass when authored state changes (e.g.
	 * ContainerNode.applyStateTint mutates emissiveIntensity outside
	 * of the dim/focus pipeline and the new value should become the
	 * new baseline).
	 */
	protected resetMaterialBaselines(): void {
		this.object.traverse((child) => {
			const mesh = child as THREE.Mesh;
			const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
			if (!mat) return;
			const list = Array.isArray(mat) ? mat : [mat];
			for (const m of list) {
				delete (m.userData as { __entityBaseline?: MaterialBaseline }).__entityBaseline;
			}
		});
	}

	getWorldAnchor(): THREE.Vector3 {
		this.object.updateMatrixWorld(true);
		this.anchorBox.setFromObject(this.object);
		if (!this.anchorBox.isEmpty()) {
			this.anchorBox.getCenter(this.anchorCenter);
			return this.anchorCenter;
		}
		return this.object.getWorldPosition(this.anchorCenter);
	}

	getTooltipAnchor(out: THREE.Vector3): THREE.Vector3 {
		const box = this.tooltipBox;
		const tmp = this.tooltipTmpBox;
		box.makeEmpty();
		this.object.traverse((child) => {
			const mesh = child as THREE.Mesh;
			if (!mesh.isMesh) return;
			if (mesh.userData?.tooltipIgnore) return;
			const geom = mesh.geometry;
			if (!geom) return;
			if (!geom.boundingBox) geom.computeBoundingBox();
			if (!geom.boundingBox) return;
			mesh.updateWorldMatrix(true, false);
			tmp.copy(geom.boundingBox).applyMatrix4(mesh.matrixWorld);
			box.union(tmp);
		});
		if (box.isEmpty()) box.setFromObject(this.object);
		if (box.isEmpty()) return this.object.getWorldPosition(out);
		out.set(
			(box.min.x + box.max.x) * 0.5,
			box.max.y,
			(box.min.z + box.max.z) * 0.5
		);
		return out;
	}

	abstract dispose(): void;
}
