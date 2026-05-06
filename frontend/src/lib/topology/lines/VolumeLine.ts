import * as THREE from 'three';
import { Connection, VOLUME_ENERGY_PRESETS, type VolumeEnergyStyle } from './Connection';

/**
 * Volume hub connection rendered as a multi-strand energy cable.
 *
 * The inherited primary line acts as a dim guide; the real look comes
 * from extra `strands` whose offsets are computed per-style:
 *   - bundle   phase-shifted sines woven together
 *   - helix    two strands spiralling around the axis
 *   - arc      primary + noisy zigzag sub-lines (plasma crackle)
 *   - tendril  many slow wispy strands at different frequencies
 *
 * Endpoint + tick hooks from the base class drive the updates so the
 * strands always match the live `a → b` of the underlying line.
 */
const SEGMENTS = 18;
const STYLE_STRAND_COUNT: Record<VolumeEnergyStyle, number> = {
	bundle: 3,
	helix: 2,
	arc: 3,
	tendril: 7,
};

type OffsetFn = (
	t: number,
	strandIdx: number,
	strandCount: number,
	pulseTime: number,
	preset: (typeof VOLUME_ENERGY_PRESETS)[VolumeEnergyStyle]
) => { n: number; a: number };

// Deterministic hash-based value noise in [-1, 1].
function noise1D(x: number): number {
	const s = Math.sin(x * 12.9898) * 43758.5453;
	return (s - Math.floor(s)) * 2 - 1;
}

function taper(t: number): number {
	// Sin taper pins offsets to 0 at both endpoints so the strand
	// always touches the line's ends.
	return Math.sin(Math.PI * t);
}

const OFFSET_FNS: Record<VolumeEnergyStyle, OffsetFn> = {
	bundle: (t, strandIdx, strandCount, pulseTime, preset) => {
		const amp = preset.strandAmplitude * taper(t);
		const phase = (strandIdx / strandCount) * Math.PI * 2 + pulseTime * preset.phaseSpeed;
		return {
			n: amp * Math.sin(t * Math.PI * 2 + phase),
			a: amp * Math.cos(t * Math.PI * 2 + phase),
		};
	},
	helix: (t, strandIdx, strandCount, pulseTime, preset) => {
		const amp = preset.strandAmplitude * taper(t);
		const twists = 2.4;
		const phase = (strandIdx / strandCount) * Math.PI * 2 + pulseTime * preset.phaseSpeed;
		return {
			n: amp * Math.cos(t * twists * Math.PI * 2 + phase),
			a: amp * Math.sin(t * twists * Math.PI * 2 + phase),
		};
	},
	arc: (t, strandIdx, _strandCount, pulseTime, preset) => {
		const amp = preset.strandAmplitude * taper(t);
		// Pseudo-random jitter per vertex + strand.
		const seed = strandIdx * 17.3 + t * 32.1 + Math.floor(pulseTime * preset.phaseSpeed);
		const n = noise1D(seed);
		const a = noise1D(seed + 9.27);
		return { n: n * amp, a: a * amp * 0.6 };
	},
	tendril: (t, strandIdx, strandCount, pulseTime, preset) => {
		const amp = preset.strandAmplitude * taper(t);
		const freq = 1.8 + strandIdx * 0.45;
		const phase = strandIdx * 1.37 + pulseTime * (preset.phaseSpeed + strandIdx * 0.08);
		return {
			n: amp * Math.sin(t * freq * Math.PI + phase),
			a: amp * Math.cos(t * freq * Math.PI + phase) * 0.55,
		};
	},
};

export class VolumeLine extends Connection {
	private readonly color: number;
	private style: VolumeEnergyStyle = 'tendril';
	private strands: THREE.Line[] = [];
	private strandMats: THREE.LineBasicMaterial[] = [];
	private readonly lastA = new THREE.Vector3();
	private readonly lastB = new THREE.Vector3();
	private hasEndpoints = false;
	private readonly dir = new THREE.Vector3();
	private readonly normal = new THREE.Vector3();
	private readonly aux = new THREE.Vector3();

	constructor(color: number) {
		super(
			new THREE.LineDashedMaterial({
				color,
				transparent: true,
				opacity: 0,
				dashSize: 14,
				gapSize: 2,
			})
		);
		// The base line was reading as a single stray straight line next
		// to the strand bundle. Strands alone carry the whole effect, so
		// hide the primary material entirely.
		this.material.visible = false;
		this.color = color;
		this.enableEnergyLine();
		this.rebuildStrands();
	}

	override setVolumeEnergyStyle(style: VolumeEnergyStyle): void {
		super.setVolumeEnergyStyle(style);
		if (this.style === style) return;
		this.style = style;
		this.rebuildStrands();
		// If we already know where the line is, redraw immediately so
		// the new strand count has geometry and the scene doesn't
		// flicker empty for a frame.
		if (this.hasEndpoints) this.refreshStrands();
	}

	private rebuildStrands(): void {
		for (const line of this.strands) {
			this.object.remove(line);
			line.geometry.dispose();
		}
		for (const mat of this.strandMats) mat.dispose();
		this.strands = [];
		this.strandMats = [];

		const preset = VOLUME_ENERGY_PRESETS[this.style];
		const count = STYLE_STRAND_COUNT[this.style];
		const strandColor = new THREE.Color(this.color).lerp(new THREE.Color(0xffffff), preset.strandWhiteMix);

		for (let i = 0; i < count; i += 1) {
			const geom = new THREE.BufferGeometry();
			geom.setAttribute(
				'position',
				new THREE.BufferAttribute(new Float32Array((SEGMENTS + 1) * 3), 3)
			);
			const mat = new THREE.LineBasicMaterial({
				color: strandColor.clone(),
				transparent: true,
				opacity: preset.strandOpacity,
				depthTest: true,
				depthWrite: false,
				blending: THREE.AdditiveBlending,
				toneMapped: false,
			});
			const line = new THREE.Line(geom, mat);
			line.renderOrder = 17;
			line.raycast = () => {};
			line.frustumCulled = false;
			this.object.add(line);
			this.strands.push(line);
			this.strandMats.push(mat);
		}
	}

	protected override onEndpointsUpdated(a: THREE.Vector3, b: THREE.Vector3): void {
		this.lastA.copy(a);
		this.lastB.copy(b);
		this.hasEndpoints = true;
		this.refreshStrands();
	}

	protected override onTick(displayLevel: number, _pulse: number, _dt: number): void {
		// Arc style churns the per-vertex noise seed each frame, so it
		// needs the strands redrawn every tick. The other styles are
		// phase-driven so they also benefit from a refresh (cheap at
		// strand counts <= 5).
		if (this.hasEndpoints) this.refreshStrands();

		// Fade strands with traffic so idle lines stay quiet, then
		// multiply in the click-focus dim so the strands fade out with
		// the rest of the line instead of popping off when visible=false
		// flips at the bottom of the base lerp.
		const preset = VOLUME_ENERGY_PRESETS[this.style];
		const alpha = THREE.MathUtils.clamp(
			preset.strandOpacity * (0.55 + displayLevel * 0.5),
			0.1,
			1
		);
		const dim = this.currentDim;
		for (const mat of this.strandMats) mat.opacity = alpha * dim;
	}

	private refreshStrands(): void {
		if (this.strands.length === 0) return;

		const a = this.lastA;
		const b = this.lastB;
		this.dir.subVectors(b, a);
		const length = this.dir.length();
		if (length < 1e-3) {
			for (const strand of this.strands) {
				const posAttr = strand.geometry.attributes.position as THREE.BufferAttribute;
				for (let i = 0; i <= SEGMENTS; i += 1) posAttr.setXYZ(i, a.x, a.y, a.z);
				posAttr.needsUpdate = true;
			}
			return;
		}
		this.dir.divideScalar(length);
		this.normal.crossVectors(this.dir, UP);
		if (this.normal.lengthSq() < 1e-4) {
			this.normal.crossVectors(this.dir, RIGHT);
		}
		this.normal.normalize();
		this.aux.crossVectors(this.dir, this.normal).normalize();

		const preset = VOLUME_ENERGY_PRESETS[this.style];
		const count = this.strands.length;
		const offsetFn = OFFSET_FNS[this.style];
		// pulseTime is private in base — reconstruct a monotonically
		// increasing clock from perf.now() instead of reaching in.
		const pulseTime = performance.now() * 0.001;
		// Spine comes from the base Connection geometry so the strands
		// follow the same gentle arc that stack / network lines use when
		// curvedLines is enabled. Fallback to straight a→b when the base
		// buffer hasn't been populated yet.
		const baseAttr = this.geometry.attributes.position as THREE.BufferAttribute;
		const spineReady = baseAttr && baseAttr.count >= SEGMENTS + 1;

		for (let s = 0; s < count; s += 1) {
			const strand = this.strands[s];
			const posAttr = strand.geometry.attributes.position as THREE.BufferAttribute;
			for (let i = 0; i <= SEGMENTS; i += 1) {
				const t = i / SEGMENTS;
				let baseX: number;
				let baseY: number;
				let baseZ: number;
				if (spineReady) {
					baseX = baseAttr.getX(i);
					baseY = baseAttr.getY(i);
					baseZ = baseAttr.getZ(i);
				} else {
					baseX = a.x + (b.x - a.x) * t;
					baseY = a.y + (b.y - a.y) * t;
					baseZ = a.z + (b.z - a.z) * t;
				}
				const { n, a: aOff } = offsetFn(t, s, count, pulseTime, preset);
				posAttr.setXYZ(
					i,
					baseX + this.normal.x * n + this.aux.x * aOff,
					baseY + this.normal.y * n + this.aux.y * aOff,
					baseZ + this.normal.z * n + this.aux.z * aOff
				);
			}
			posAttr.needsUpdate = true;
		}
	}

	override dispose(): void {
		for (const line of this.strands) line.geometry.dispose();
		for (const mat of this.strandMats) mat.dispose();
		super.dispose();
	}
}

const UP = new THREE.Vector3(0, 1, 0);
const RIGHT = new THREE.Vector3(1, 0, 0);
