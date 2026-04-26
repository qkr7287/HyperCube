import * as THREE from 'three';
import { Entity } from './Entity';

const FRAME_BODY_GEOMETRY = new THREE.CylinderGeometry(7.5, 7.5, 11, 6, 1, true);
const FRAME_CAP_GEOMETRY = new THREE.CylinderGeometry(7.5, 7.5, 1.2, 6);
const FRAME_RING_GEOMETRY = new THREE.TorusGeometry(7.8, 0.45, 10, 6);
const FRAME_STRUT_GEOMETRY = new THREE.BoxGeometry(0.85, 0.85, 10.4);
const PRISM_GEOMETRY = new THREE.CylinderGeometry(7.4, 7.4, 12, 6);
const CAPSULE_BODY_GEOMETRY = new THREE.CylinderGeometry(5.8, 5.8, 8.2, 18, 1, true);
const CAPSULE_CAP_GEOMETRY = new THREE.SphereGeometry(5.8, 18, 14);
const CRATE_CORE_GEOMETRY = new THREE.BoxGeometry(10.8, 10.8, 10.8);
// Edge struts: thinner cross-section so the wireframe reads as an outline
// rather than a chunky cage. Length stays 11.6 so corners still butt cleanly.
const CRATE_EDGE_GEOMETRY_X = new THREE.BoxGeometry(11.6, 0.4, 0.4);
const CRATE_EDGE_GEOMETRY_Y = new THREE.BoxGeometry(0.4, 11.6, 0.4);
const CRATE_EDGE_GEOMETRY_Z = new THREE.BoxGeometry(0.4, 0.4, 11.6);
const OVERLAY_ORB_GEOMETRY = new THREE.IcosahedronGeometry(1, 2);
const OVERLAY_BOX_GEOMETRY = new THREE.BoxGeometry(1, 1, 1);
FRAME_BODY_GEOMETRY.rotateX(Math.PI / 2);
FRAME_CAP_GEOMETRY.rotateX(Math.PI / 2);
FRAME_RING_GEOMETRY.rotateX(Math.PI / 2);
FRAME_STRUT_GEOMETRY.rotateY(Math.PI / 2);
PRISM_GEOMETRY.rotateX(Math.PI / 2);
CAPSULE_BODY_GEOMETRY.rotateX(Math.PI / 2);
CAPSULE_CAP_GEOMETRY.rotateX(Math.PI / 2);

// State overlay — applied as a per-instance emissive tint on top of
// the authored GLB material so the base colour/texture stays intact
// and the state only reads as a subtle glow.
interface StateTint {
	color: number;
	intensity: number;
}
const ACTIVE_TINT: StateTint = { color: 0x30d5c8, intensity: 0.06 };
const INACTIVE_TINT: StateTint = { color: 0xef4444, intensity: 0.1 };

function isTintableMaterial(mat: THREE.Material): mat is THREE.MeshStandardMaterial {
	return 'emissive' in mat && 'emissiveIntensity' in mat;
}

function tintFor(state: string): StateTint {
	return state === 'running' ? ACTIVE_TINT : INACTIVE_TINT;
}

function fitOverlayToObject(
	overlay: THREE.Mesh,
	object: THREE.Object3D,
	style: ContainerGeometryStyle
): void {
	object.updateMatrixWorld(true);
	const box = new THREE.Box3().setFromObject(object);
	const size = new THREE.Vector3();
	const center = new THREE.Vector3();
	box.getSize(size);
	box.getCenter(center);
	const localCenter = object.worldToLocal(center);
	overlay.position.copy(localCenter);
	if (style === 'crate') {
		overlay.scale.set(
			Math.max(size.x * 1.08, 9.8),
			Math.max(size.y * 1.08, 9.8),
			Math.max(size.z * 1.08, 9.8)
		);
		return;
	}
	const radius = Math.max(size.x, size.y, size.z) * 0.62;
	overlay.scale.setScalar(Math.max(radius, 8));
}

export interface ContainerNodeData {
	id: string;
	name: string;
	state: string;
	stack: string;
}

export type ContainerGeometryStyle = 'frame' | 'prism' | 'capsule' | 'crate';

/**
 * A container node is rendered from a GLB template if one is
 * available, otherwise from a fallback cylinder. When a template is
 * supplied we deep-clone it and then clone every material too so the
 * emissive state tint stays local — the authored colour/texture on
 * the base map stays intact.
 */
export class ContainerNode extends Entity {
	readonly kind = 'container' as const;
	readonly id: string;
	name: string;
	state: string;
	stack: string;

	// Per-instance materials — cloned from the template so emissive
	// tweaks don't bleed across container nodes.
	private readonly materials: THREE.MeshStandardMaterial[];
	private readonly overlayMaterial: THREE.MeshBasicMaterial;
	private readonly tooltipAnchorObject: THREE.Object3D;
	private readonly tooltipAnchorBox = new THREE.Box3();

	constructor(
		data: ContainerNodeData,
		template: THREE.Object3D | null = null,
		style: ContainerGeometryStyle = 'crate'
	) {
		const materials: THREE.MeshStandardMaterial[] = [];
		void template;
		const object = new THREE.Group();
		const bodyMat = new THREE.MeshStandardMaterial({
			color: 0x1b4b5a,
			emissive: 0x000000,
			emissiveIntensity: 0,
			roughness: 0.42,
			metalness: 0.22,
			transparent: true,
			opacity: 0.96,
		});
		const capMat = new THREE.MeshStandardMaterial({
			color: 0x3b6174,
			emissive: 0x000000,
			emissiveIntensity: 0,
			roughness: 0.28,
			metalness: 0.42,
		});
		const ringMat = new THREE.MeshStandardMaterial({
			color: 0x8bc5d1,
			emissive: 0x000000,
			emissiveIntensity: 0,
			roughness: 0.18,
			metalness: 0.74,
		});
		const strutMat = new THREE.MeshStandardMaterial({
			color: 0xb4dbe4,
			emissive: 0x000000,
			emissiveIntensity: 0,
			roughness: 0.24,
			metalness: 0.58,
		});
		materials.push(bodyMat, capMat, ringMat, strutMat);
		const tooltipAnchorObject = buildGeometryStyle(
			object,
			style,
			bodyMat,
			capMat,
			ringMat,
			strutMat
		);

		const overlayMaterial = new THREE.MeshBasicMaterial({
			color: 0x30d5c8,
			transparent: true,
			opacity: 0.16,
			// depthTest enabled so hubs / other models occlude the
			// halo when the container is behind them. DoubleSide
			// keeps the halo visible on the bit that extends past
			// the container body (BackSide would get hidden behind
			// the body itself once depthTest is on).
			depthTest: true,
			depthWrite: false,
			side: THREE.DoubleSide,
		});
		const overlay = new THREE.Mesh(
			style === 'crate' ? OVERLAY_BOX_GEOMETRY : OVERLAY_ORB_GEOMETRY,
			overlayMaterial
		);
		overlay.renderOrder = 14;
		// Halo is ~1.08x the body, so it would inflate any bounding box
		// computed from this object and push the tooltip anchor up. Mark
		// it so Topology's tooltip math can skip it.
		overlay.userData.tooltipIgnore = true;
		fitOverlayToObject(overlay, object, style);
		object.add(overlay);

		super(object);
		this.id = data.id;
		this.name = data.name;
		this.state = data.state;
		this.stack = data.stack;
		this.materials = materials;
		this.overlayMaterial = overlayMaterial;
		this.tooltipAnchorObject = tooltipAnchorObject;
		this.applyStateTint();
	}

	update(data: ContainerNodeData): void {
		this.name = data.name;
		this.stack = data.stack;
		if (data.state !== this.state) {
			this.state = data.state;
			this.applyStateTint();
		}
	}
	dispose(): void {
		// Cloned materials are per-instance; geometry and textures are
		// still shared with the template and must not be disposed here.
		for (const mat of this.materials) mat.dispose();
		this.overlayMaterial.dispose();
	}

	private applyStateTint(): void {
		const tint = tintFor(this.state);
		for (const mat of this.materials) {
			if (isTintableMaterial(mat)) {
				mat.emissive.setHex(tint.color);
				mat.emissiveIntensity = tint.intensity;
			}
			mat.needsUpdate = true;
		}
		this.overlayMaterial.color.setHex(tint.color);
		this.overlayMaterial.opacity = this.state === 'running' ? 0.16 : 0.22;
	}

	override getTooltipAnchor(out: THREE.Vector3): THREE.Vector3 {
		this.tooltipAnchorObject.updateWorldMatrix(true, false);
		this.tooltipAnchorBox.setFromObject(this.tooltipAnchorObject);
		if (this.tooltipAnchorBox.isEmpty()) return super.getTooltipAnchor(out);
		out.set(
			(this.tooltipAnchorBox.min.x + this.tooltipAnchorBox.max.x) * 0.5,
			this.tooltipAnchorBox.max.y,
			(this.tooltipAnchorBox.min.z + this.tooltipAnchorBox.max.z) * 0.5
		);
		return out;
	}

}

function buildGeometryStyle(
	object: THREE.Group,
	style: ContainerGeometryStyle,
	bodyMat: THREE.MeshStandardMaterial,
	capMat: THREE.MeshStandardMaterial,
	ringMat: THREE.MeshStandardMaterial,
	strutMat: THREE.MeshStandardMaterial
): THREE.Object3D {
	if (style === 'prism') {
		const prism = new THREE.Mesh(PRISM_GEOMETRY, bodyMat);
		object.add(prism);
		const topRing = new THREE.Mesh(FRAME_RING_GEOMETRY, ringMat);
		const bottomRing = new THREE.Mesh(FRAME_RING_GEOMETRY, ringMat);
		topRing.scale.setScalar(0.9);
		bottomRing.scale.setScalar(0.9);
		topRing.position.z = 4.5;
		bottomRing.position.z = -4.5;
		object.add(topRing, bottomRing);
		return prism;
	}

	if (style === 'capsule') {
		const body = new THREE.Mesh(CAPSULE_BODY_GEOMETRY, bodyMat);
		const capFront = new THREE.Mesh(CAPSULE_CAP_GEOMETRY, capMat);
		const capBack = new THREE.Mesh(CAPSULE_CAP_GEOMETRY, capMat);
		capFront.position.z = 4.1;
		capBack.position.z = -4.1;
		object.add(body, capFront, capBack);
		const belt = new THREE.Mesh(FRAME_RING_GEOMETRY, ringMat);
		belt.scale.setScalar(0.82);
		object.add(belt);
		return body;
	}

	if (style === 'crate') {
		const core = new THREE.Mesh(CRATE_CORE_GEOMETRY, bodyMat);
		core.scale.setScalar(0.9);
		object.add(core);
		const corners = [-5.3, 5.3];
		for (const y of corners) {
			for (const z of corners) {
				const edge = new THREE.Mesh(CRATE_EDGE_GEOMETRY_X, strutMat);
				edge.position.set(0, y, z);
				object.add(edge);
			}
		}
		for (const x of corners) {
			for (const z of corners) {
				const edge = new THREE.Mesh(CRATE_EDGE_GEOMETRY_Y, strutMat);
				edge.position.set(x, 0, z);
				object.add(edge);
			}
		}
		for (const x of corners) {
			for (const y of corners) {
				const edge = new THREE.Mesh(CRATE_EDGE_GEOMETRY_Z, strutMat);
				edge.position.set(x, y, 0);
				object.add(edge);
			}
		}
		return core;
	}

	const body = new THREE.Mesh(FRAME_BODY_GEOMETRY, bodyMat);
	const capFront = new THREE.Mesh(FRAME_CAP_GEOMETRY, capMat);
	const capBack = new THREE.Mesh(FRAME_CAP_GEOMETRY, capMat);
	capFront.position.z = 5.55;
	capBack.position.z = -5.55;
	const ringFront = new THREE.Mesh(FRAME_RING_GEOMETRY, ringMat);
	const ringBack = new THREE.Mesh(FRAME_RING_GEOMETRY, ringMat);
	ringFront.position.z = 4.65;
	ringBack.position.z = -4.65;
	object.add(body, capFront, capBack, ringFront, ringBack);

	const strutOffsets = [
		new THREE.Vector3(5.7, 0, 0),
		new THREE.Vector3(-5.7, 0, 0),
		new THREE.Vector3(0, 5.2, 0),
		new THREE.Vector3(0, -5.2, 0),
	];
	for (const offset of strutOffsets) {
		const strut = new THREE.Mesh(FRAME_STRUT_GEOMETRY, strutMat);
		strut.position.copy(offset);
		object.add(strut);
	}
	return body;
}
