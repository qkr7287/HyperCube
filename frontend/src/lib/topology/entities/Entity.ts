import * as THREE from 'three';

export type EntityKind = 'container' | 'hub';

// Per-frame lerp speed for dim / focus / scale animations. exp(-dt*k)
// gives ~95% completion in (3/k) seconds → with k=6 that's ~500ms.
// Slower than the snappier k=8 we started with — the exp decay is
// front-loaded (most movement in the first 100ms) so a faster k makes
// the fade feel more like an instant cut. k=6 leaves more time at the
// tail of the curve where the eye is sensitive to motion.
const STATE_LERP_K = 6;

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

	// Animated visual state. target is what we're lerping toward;
	// current is where we are right now (driven by tick(dt)).
	private targetOpacity = FOCUSED_OPACITY;
	protected currentOpacity = FOCUSED_OPACITY;
	private targetEmissiveBoost = 1;
	protected currentEmissiveBoost = 1;
	private targetScale = 1;
	protected currentScale = 1;
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
		this.targetEmissiveBoost = focused ? FOCUSED_EMISSIVE_BOOST : 1;
		this.targetScale = focused ? FOCUSED_SCALE : 1;
	}

	/** Per-frame visual state animation. */
	tick(dt: number): void {
		const safeDt = Number.isFinite(dt) && dt > 0 ? Math.min(dt, 0.1) : 0;
		const k = 1 - Math.exp(-safeDt * STATE_LERP_K);
		this.currentOpacity += (this.targetOpacity - this.currentOpacity) * k;
		this.currentEmissiveBoost += (this.targetEmissiveBoost - this.currentEmissiveBoost) * k;
		this.currentScale += (this.targetScale - this.currentScale) * k;
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
