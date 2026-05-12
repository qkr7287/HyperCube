import * as THREE from 'three';
import { buildFromTemplate } from '../core/MeshFactory';
import { Hub } from '../entities/Hub';

const FALLBACK_GEOMETRY = new THREE.TorusGeometry(16, 5, 14, 28);
const CROWN_SPIKE_GEOMETRY = new THREE.CylinderGeometry(0.22, 0.72, 8.5, 6, 1, true);
const RIPPLE_RING_GEOMETRY = new THREE.TorusGeometry(8.5, 0.28, 10, 56);
const LATTICE_FRAME_GEOMETRY = new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(8.2, 0));
const LATTICE_NODE_GEOMETRY = new THREE.SphereGeometry(0.85, 10, 10);

// Single fuchsia tone shared by every network hub / line / tunnel —
// "any pink line belongs to a network hub" becomes a one-glance rule.
// Deliberately outside the cyan family so it never collides with the
// stack accent and sits opposite volume orange on the colour wheel.
export type NetworkPaletteMode = 'fuchsia' | 'cyan' | 'emerald' | 'sunset';

const NETWORK_PALETTES: Record<NetworkPaletteMode, number> = {
	fuchsia: 0xe879f9,
	cyan: 0x67e8f9,
	emerald: 0x34d399,
	sunset: 0xfb7185,
};

let currentNetworkPalette: NetworkPaletteMode = 'cyan';

function networkColorFor(_name: string, _sortedNames: readonly string[]): number {
	return NETWORK_PALETTES[currentNetworkPalette];
}

function setNetworkPalette(mode: NetworkPaletteMode): void {
	currentNetworkPalette = mode;
}

export interface NetworkHubData {
	name: string;
	color: number;
}

export type NetworkHubFxMode = 'crown' | 'ripple' | 'lattice';

function isTintableMaterial(mat: THREE.Material): mat is THREE.MeshStandardMaterial {
	return 'emissive' in mat && 'emissiveIntensity' in mat;
}

function cloneMaterialSet(
	src: THREE.Material | THREE.Material[],
	into: THREE.MeshStandardMaterial[]
): THREE.Material | THREE.Material[] {
	if (Array.isArray(src)) {
		return src.map((mat) => {
			const cloned = mat.clone();
			if (isTintableMaterial(cloned)) into.push(cloned);
			return cloned;
		});
	}
	const cloned = src.clone();
	if (isTintableMaterial(cloned)) into.push(cloned);
	return cloned;
}

export class NetworkHub extends Hub {
	private static readonly ANCHOR_HEIGHT_RATIO = 0.13;
	readonly hubType = 'network' as const;
	readonly id: string;
	name: string;
	color: number;

	private readonly coreObject: THREE.Object3D;
	private readonly group: THREE.Group;
	private readonly materials: THREE.MeshStandardMaterial[];
	private readonly usesTemplate: boolean;
	private readonly crownGroup: THREE.Group;
	private readonly crownMats: THREE.MeshBasicMaterial[];
	private readonly crownSpikes: THREE.Mesh[];
	private readonly rippleGroup: THREE.Group;
	private readonly rippleMats: THREE.MeshBasicMaterial[];
	private readonly rippleRings: THREE.Mesh[];
	private readonly latticeGroup: THREE.Group;
	private readonly latticeFrame: THREE.LineSegments;
	private readonly latticeFrameMat: THREE.LineBasicMaterial;
	private readonly latticeNodeMats: THREE.MeshBasicMaterial[];
	private readonly latticeNodes: THREE.Mesh[];
	private fxMode: NetworkHubFxMode = 'crown';
	private targetTrafficLevel = 0;
	private visibleTrafficLevel = 0;
	private pulseTime = 0;
	private readonly baseScale = new THREE.Vector3(1, 1, 1);
	private readonly coreAnchorBox = new THREE.Box3();
	private readonly coreAnchorCenter = new THREE.Vector3();
	private readonly coreAnchorSize = new THREE.Vector3();
	private readonly baseOpacity = 0.9;
	private readonly baseEmissiveIntensity = 0.45;

	constructor(data: NetworkHubData, template: THREE.Object3D | null = null) {
		const params: THREE.MeshStandardMaterialParameters = {
			color: data.color,
			emissive: data.color,
			emissiveIntensity: 0.45,
			roughness: 0.3,
			metalness: 0.4,
			transparent: true,
			opacity: 0.9,
		};

		let object: THREE.Object3D;
		let materials: THREE.MeshStandardMaterial[];
		if (template) {
			const built = buildFromTemplate(template);
			object = built.object;
			materials = [];
			object.traverse((child) => {
				const mesh = child as THREE.Mesh;
				if (!mesh.isMesh) return;
				mesh.material = cloneMaterialSet(mesh.material, materials);
			});
			// At rest, the hub renders in the OPAQUE pass (same as
			// StackHub / VolumeHub). Earlier this stayed in the transparent
			// pass at all times because tick() unconditionally set
			// `transparent = true`, and that pass sorts by camera distance —
			// the GroupMesh membrane (also transparent, depthWrite:false)
			// then "won" the sort whenever the hub sat behind it, so the
			// hub appeared to layer ON TOP of the membrane regardless of z.
			// Forcing opaque + depthWrite here puts the hub firmly into the
			// opaque pass; tick() flips back to transparent only while the
			// dim/focus fade or traffic FX is actively modulating opacity.
			for (const mat of materials) {
				mat.transparent = false;
				mat.opacity = 1;
				mat.depthTest = true;
				mat.depthWrite = true;
				mat.needsUpdate = true;
			}
		} else {
			const mat = new THREE.MeshStandardMaterial(params);
			object = new THREE.Mesh(FALLBACK_GEOMETRY, mat);
			materials = [mat];
		}

		const crownGroup = new THREE.Group();
		crownGroup.renderOrder = 9;
		const crownMats: THREE.MeshBasicMaterial[] = [];
		const crownSpikes: THREE.Mesh[] = [];
		for (let i = 0; i < 8; i += 1) {
			const mat = new THREE.MeshBasicMaterial({
				color: data.color,
				transparent: true,
				opacity: 0.18,
				blending: THREE.AdditiveBlending,
				depthTest: false,
				depthWrite: false,
				toneMapped: false,
				side: THREE.DoubleSide,
			});
			const spike = new THREE.Mesh(CROWN_SPIKE_GEOMETRY, mat);
			const angle = (i / 8) * Math.PI * 2;
			spike.position.set(Math.cos(angle) * 9.5, 2.5, Math.sin(angle) * 9.5);
			spike.lookAt(Math.cos(angle) * 18, 9, Math.sin(angle) * 18);
			spike.rotateX(Math.PI / 2);
			spike.renderOrder = 9;
			crownGroup.add(spike);
			crownMats.push(mat);
			crownSpikes.push(spike);
		}

		const rippleGroup = new THREE.Group();
		rippleGroup.renderOrder = 9;
		const rippleMats: THREE.MeshBasicMaterial[] = [];
		const rippleRings: THREE.Mesh[] = [];
		for (let i = 0; i < 3; i += 1) {
			const mat = new THREE.MeshBasicMaterial({
				color: data.color,
				transparent: true,
				opacity: 0.16,
				blending: THREE.AdditiveBlending,
				depthTest: false,
				depthWrite: false,
				toneMapped: false,
			});
			const ring = new THREE.Mesh(RIPPLE_RING_GEOMETRY, mat);
			ring.rotation.x = Math.PI / 2;
			ring.position.y = -1.4 + i * 1.5;
			ring.scale.setScalar(0.88 + i * 0.1);
			ring.renderOrder = 9;
			rippleGroup.add(ring);
			rippleMats.push(mat);
			rippleRings.push(ring);
		}

		const latticeGroup = new THREE.Group();
		latticeGroup.renderOrder = 9;
		const latticeFrameMat = new THREE.LineBasicMaterial({
			color: data.color,
			transparent: true,
			opacity: 0.2,
			depthTest: false,
			depthWrite: false,
			blending: THREE.AdditiveBlending,
			toneMapped: false,
		});
		const latticeFrame = new THREE.LineSegments(LATTICE_FRAME_GEOMETRY, latticeFrameMat);
		latticeFrame.renderOrder = 9;
		latticeGroup.add(latticeFrame);
		const latticeNodePositions = [
			new THREE.Vector3(0, 0, 9.2),
			new THREE.Vector3(0, 0, -9.2),
			new THREE.Vector3(9.2, 0, 0),
			new THREE.Vector3(-9.2, 0, 0),
			new THREE.Vector3(0, 9.2, 0),
			new THREE.Vector3(0, -9.2, 0),
		];
		const latticeNodeMats: THREE.MeshBasicMaterial[] = [];
		const latticeNodes: THREE.Mesh[] = [];
		for (const pos of latticeNodePositions) {
			const mat = new THREE.MeshBasicMaterial({
				color: data.color,
				transparent: true,
				opacity: 0.22,
				blending: THREE.AdditiveBlending,
				depthTest: false,
				depthWrite: false,
				toneMapped: false,
			});
			const node = new THREE.Mesh(LATTICE_NODE_GEOMETRY, mat);
			node.position.copy(pos);
			node.renderOrder = 10;
			latticeGroup.add(node);
			latticeNodeMats.push(mat);
			latticeNodes.push(node);
		}

		const group = new THREE.Group();
		group.add(object);
		group.add(crownGroup);
		group.add(rippleGroup);
		group.add(latticeGroup);
		// (renderOrder is set by Entity ctor; explicit assignment here is
		// redundant and was misleading — see traverse comment above.)

		super(group);
		this.id = `network:${data.name}`;
		this.name = data.name;
		this.color = data.color;
		this.coreObject = object;
		this.group = group;
		this.materials = materials;
		this.usesTemplate = template !== null;
		this.crownGroup = crownGroup;
		this.crownMats = crownMats;
		this.crownSpikes = crownSpikes;
		this.rippleGroup = rippleGroup;
		this.rippleMats = rippleMats;
		this.rippleRings = rippleRings;
		this.latticeGroup = latticeGroup;
		this.latticeFrame = latticeFrame;
		this.latticeFrameMat = latticeFrameMat;
		this.latticeNodeMats = latticeNodeMats;
		this.latticeNodes = latticeNodes;
		this.update(data);
		this.applyFxMode();
	}

	override getWorldAnchor(): THREE.Vector3 {
		this.coreObject.updateMatrixWorld(true);
		this.coreAnchorBox.setFromObject(this.coreObject);
		if (!this.coreAnchorBox.isEmpty()) {
			this.coreAnchorBox.getSize(this.coreAnchorSize);
			this.coreAnchorCenter.set(
				(this.coreAnchorBox.min.x + this.coreAnchorBox.max.x) * 0.5,
				this.coreAnchorBox.min.y + this.coreAnchorSize.y * NetworkHub.ANCHOR_HEIGHT_RATIO,
				(this.coreAnchorBox.min.z + this.coreAnchorBox.max.z) * 0.5
			);
			return this.coreAnchorCenter;
		}
		return this.coreObject.getWorldPosition(this.coreAnchorCenter);
	}

	setFxMode(mode: NetworkHubFxMode): void {
		this.fxMode = mode;
		this.applyFxMode();
	}

	setTrafficLevel(level: number): void {
		this.targetTrafficLevel = THREE.MathUtils.clamp(level, 0, 1);
		if (this.targetTrafficLevel <= 0 && this.visibleTrafficLevel <= 0.001) {
			this.group.scale.copy(this.baseScale);
			for (const mat of this.materials) {
				mat.opacity = this.baseOpacity;
				mat.emissiveIntensity = this.baseEmissiveIntensity;
			}
		}
	}

	// Network hubs already mutate opacity / emissive / scale per-frame
	// for the traffic FX. Disable the base Entity.applyVisualState()
	// (which would fight us) and weave the dim / focus factors directly
	// into our own math below.
	protected override applyVisualState(): void {}

	tick(dt: number): void {
		// Run base lerp first so currentOpacity / currentEmissiveBoost /
		// currentScale reflect this frame; applyVisualState above is a
		// no-op so it doesn't touch our materials.
		super.tick(dt);

		this.pulseTime += dt;
		const smoothing = 1 - Math.exp(-dt * 5.5);
		this.visibleTrafficLevel = THREE.MathUtils.lerp(
			this.visibleTrafficLevel,
			this.targetTrafficLevel,
			smoothing
		);
		const displayLevel = this.visibleTrafficLevel > 0.001
			? Math.max(this.visibleTrafficLevel, this.targetTrafficLevel > 0 ? 0.2 : 0)
			: 0;

		const pulse = (Math.sin(this.pulseTime * 5.4) + 1) * 0.5;
		const scaleBoost = displayLevel * (0.04 + pulse * 0.045);
		this.group.scale.setScalar((1 + scaleBoost) * this.currentScale);

		const dim = this.currentOpacity;
		const boost = this.currentEmissiveBoost;
		// Only flip into the transparent pass when something is actually
		// modulating the hub's opacity (dim fade or traffic-driven brighten).
		// Otherwise leave the GLB materials in the opaque pass so the depth
		// buffer correctly orders them against the GroupMesh membrane.
		const needsAlpha = dim < 0.999 || displayLevel > 0.001 || !this.usesTemplate;
		const targetOpacity = needsAlpha
			? THREE.MathUtils.clamp(this.baseOpacity + displayLevel * 0.06, 0.25, 1) * dim
			: 1;
		for (const mat of this.materials) {
			const wantTransparent = needsAlpha;
			if (mat.transparent !== wantTransparent) {
				mat.transparent = wantTransparent;
				mat.needsUpdate = true;
			}
			mat.opacity = targetOpacity;
			if (!this.usesTemplate) {
				mat.emissiveIntensity =
					(this.baseEmissiveIntensity + displayLevel * 0.62 + pulse * displayLevel * 0.28) *
					boost;
			}
		}

		this.tickCrown(displayLevel, pulse, dt);
		this.tickRipple(displayLevel, pulse, dt);
		this.tickLattice(displayLevel, pulse, dt);

		// Apply dim factor to the FX layer materials too (they were just
		// written by tickCrown/Ripple/Lattice). At full opacity (dim=1)
		// this is a no-op multiplication.
		if (Math.abs(dim - 1) > 0.001) {
			for (const mat of this.crownMats) mat.opacity *= dim;
			for (const mat of this.rippleMats) mat.opacity *= dim;
			this.latticeFrameMat.opacity *= dim;
			for (const mat of this.latticeNodeMats) mat.opacity *= dim;
		}
	}

	update(data: NetworkHubData): void {
		this.name = data.name;
		if (data.color !== this.color) {
			this.color = data.color;
			for (const mat of this.materials) {
				if (this.usesTemplate) continue;
				mat.color.setHex(data.color);
				mat.emissive.setHex(data.color);
			}
			for (const mat of this.crownMats) mat.color.setHex(data.color);
			for (const mat of this.rippleMats) mat.color.setHex(data.color);
			this.latticeFrameMat.color.setHex(data.color);
			for (const mat of this.latticeNodeMats) mat.color.setHex(data.color);
		}
	}

	dispose(): void {
		for (const mat of this.materials) mat.dispose();
		for (const mat of this.crownMats) mat.dispose();
		for (const mat of this.rippleMats) mat.dispose();
		this.latticeFrameMat.dispose();
		for (const mat of this.latticeNodeMats) mat.dispose();
		this.latticeFrame.geometry.dispose();
		for (const node of this.latticeNodes) node.geometry.dispose();
	}

	private tickCrown(displayLevel: number, pulse: number, dt: number): void {
		this.crownGroup.rotation.y += dt * (0.18 + displayLevel * 0.32);
		for (let i = 0; i < this.crownSpikes.length; i += 1) {
			const phase = pulse + i * 0.13;
			const lift = displayLevel * (0.6 + Math.sin(this.pulseTime * 4.2 + i) * 0.45);
			this.crownSpikes[i].scale.set(1, 1 + lift * 0.38, 1);
			this.crownMats[i].opacity = THREE.MathUtils.clamp(
				0.18 + displayLevel * 0.2 + Math.sin(phase * Math.PI * 2) * 0.06,
				0.08,
				0.52
			);
		}
	}

	private tickRipple(displayLevel: number, pulse: number, dt: number): void {
		this.rippleGroup.visible = this.fxMode === 'ripple' && displayLevel > 0.02;
		if (!this.rippleGroup.visible) return;
		this.rippleGroup.rotation.y -= dt * (0.08 + displayLevel * 0.18);
		for (let i = 0; i < this.rippleRings.length; i += 1) {
			const phase = (this.pulseTime * 0.9 + i * 0.22) % 1;
			const scale = 0.9 + phase * 0.55 + displayLevel * 0.08;
			this.rippleRings[i].scale.setScalar(scale);
			this.rippleRings[i].position.y =
				-1.2 + i * 1.5 + Math.sin(this.pulseTime * 2.5 + i) * 0.25;
			this.rippleMats[i].opacity = THREE.MathUtils.clamp(
				0.1 + displayLevel * 0.16 + (1 - phase) * 0.12 + pulse * 0.04,
				0.06,
				0.42
			);
		}
	}

	private tickLattice(displayLevel: number, pulse: number, dt: number): void {
		this.latticeGroup.rotation.x += dt * (0.12 + displayLevel * 0.22);
		this.latticeGroup.rotation.y -= dt * (0.15 + displayLevel * 0.28);
		this.latticeFrameMat.opacity = THREE.MathUtils.clamp(0.14 + displayLevel * 0.18 + pulse * 0.06, 0.08, 0.44);
		for (let i = 0; i < this.latticeNodes.length; i += 1) {
			const phase = pulse + i * 0.18;
			this.latticeNodes[i].scale.setScalar(1 + displayLevel * (0.16 + Math.sin(phase * Math.PI * 2) * 0.08));
			this.latticeNodeMats[i].opacity = THREE.MathUtils.clamp(
				0.18 + displayLevel * 0.22 + Math.sin(phase * Math.PI * 2) * 0.05,
				0.08,
				0.52
			);
		}
	}

	private applyFxMode(): void {
		this.crownGroup.visible = this.fxMode === 'crown';
		this.rippleGroup.visible = false;
		this.latticeGroup.visible = this.fxMode === 'lattice';
	}
}

export { networkColorFor, setNetworkPalette };
