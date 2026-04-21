import * as THREE from 'three';
// @ts-ignore ??three.js addon typings are resolved at runtime
import { ConvexGeometry } from 'three/addons/geometries/ConvexGeometry.js';

/**
 * Convex hull membrane wrapping the members of a stack group.
 *
 * The key fix here is that the hull no longer samples a guessed
 * constant radius around each member centre. Instead it samples the
 * padded world-space bounding box of each live object, which keeps the
 * membrane outside the actual GLB silhouettes.
 */

const HULL_PADDING = 9;
const MIN_MEMBERS = 2;
const CONTOUR_SEGMENTS = 48;
const AURA_POINTS = 96;

export type GroupVisualMode = 'wire' | 'soft' | 'contour' | 'aura' | 'hybrid';

export interface GroupMember {
	readonly position: THREE.Vector3;
	readonly object: THREE.Object3D;
}

export class GroupMesh {
	readonly object: THREE.Group;

	private readonly surface: THREE.Mesh;
	private readonly wire: THREE.LineSegments;
	private readonly contourGroup: THREE.Group;
	private readonly contourMats: THREE.LineBasicMaterial[];
	private readonly aura: THREE.Points;
	private readonly auraMat: THREE.PointsMaterial;
	private readonly surfaceMat: THREE.MeshBasicMaterial;
	private readonly wireMat: THREE.LineBasicMaterial;
	private readonly boundsBox = new THREE.Box3();

	private members: readonly GroupMember[] = [];
	private currentGeometry: THREE.BufferGeometry | null = null;
	private currentWireGeometry: THREE.BufferGeometry | null = null;
	private mode: GroupVisualMode = 'soft';
	private highlighted = false;
	private readonly contourGeometries: THREE.BufferGeometry[] = [];
	private currentCenter = new THREE.Vector3();
	private currentRadius = 0;
	private readonly lastMemberPositions: Map<string, THREE.Vector3> = new Map();
	private geometryDirty = true;
	private refreshCooldown = 0;

	private static readonly REFRESH_INTERVAL = 5;
	private static readonly MOVEMENT_THRESHOLD_SQ = 1.25 * 1.25;

	constructor(color: number) {
		// depthTest=true on every membrane layer so normal z-buffer
		// ordering takes over — hubs / containers / lines that sit
		// closer to the camera naturally occlude the membrane, the
		// membrane only fills the empty space behind them. depthWrite
		// stays false so the membrane doesn't punch through other
		// transparent passes.
		this.surfaceMat = new THREE.MeshBasicMaterial({
			color,
			transparent: true,
			opacity: 0.03,
			side: THREE.DoubleSide,
			depthTest: true,
			depthWrite: false,
			toneMapped: false,
		});
		this.wireMat = new THREE.LineBasicMaterial({
			color,
			transparent: true,
			opacity: 0.12,
			depthTest: true,
			depthWrite: false,
			toneMapped: false,
		});

		this.surface = new THREE.Mesh(new THREE.BufferGeometry(), this.surfaceMat);
		this.wire = new THREE.LineSegments(new THREE.BufferGeometry(), this.wireMat);
		this.surface.renderOrder = 0;
		this.wire.renderOrder = 0;
		this.contourMats = [0.03, 0.045, 0.065].map(
			(opacity) =>
				new THREE.LineBasicMaterial({
					color,
					transparent: true,
					opacity,
					depthTest: true,
					depthWrite: false,
					toneMapped: false,
				})
		);
		this.contourGroup = new THREE.Group();
		this.contourGroup.renderOrder = 0;
		for (const mat of this.contourMats) {
			const geometry = new THREE.BufferGeometry();
			this.contourGeometries.push(geometry);
			const ring = new THREE.LineLoop(geometry, mat);
			ring.renderOrder = 0;
			this.contourGroup.add(ring);
		}
		this.auraMat = new THREE.PointsMaterial({
			color,
			size: 5,
			transparent: true,
			opacity: 0.028,
			depthTest: true,
			depthWrite: false,
			sizeAttenuation: true,
			toneMapped: false,
		});
		this.aura = new THREE.Points(new THREE.BufferGeometry(), this.auraMat);
		this.aura.renderOrder = 0;

		this.object = new THREE.Group();
		this.object.renderOrder = 0;
		this.object.add(this.surface);
		this.object.add(this.wire);
		this.object.add(this.contourGroup);
		this.object.add(this.aura);
		this.object.visible = false;
	}

	setMembers(members: readonly GroupMember[]): void {
		if (members.length !== this.members.length) {
			this.geometryDirty = true;
		}
		this.members = members;
	}

	setColor(color: number): void {
		this.surfaceMat.color.setHex(color);
		this.wireMat.color.setHex(color);
		for (const mat of this.contourMats) mat.color.setHex(color);
		this.auraMat.color.setHex(color);
	}

	setMode(mode: GroupVisualMode): void {
		this.mode = mode;
		this.applyModeVisibility();
	}

	setHighlighted(enabled: boolean): void {
		this.highlighted = enabled;
		this.applyModeVisibility();
	}

	update(): void {
		if (this.members.length < MIN_MEMBERS) {
			this.hideAll();
			return;
		}
		if (!this.shouldRebuild()) {
			this.applyModeVisibility();
			return;
		}

		const points = this.sampleAroundMembers(this.members);
		if (points.length < 4) {
			this.hideAll();
			return;
		}

		let hull: THREE.BufferGeometry | null = null;
		try {
			hull = new ConvexGeometry(points);
		} catch {
			hull = null;
		}

		if (!hull) {
			this.hideAll();
			return;
		}

		if (this.currentGeometry) this.currentGeometry.dispose();
		if (this.currentWireGeometry) this.currentWireGeometry.dispose();

		this.currentGeometry = hull;
		this.currentWireGeometry = new THREE.EdgesGeometry(hull);
		this.surface.geometry = this.currentGeometry;
		this.wire.geometry = this.currentWireGeometry;
		this.boundsBox.makeEmpty();
		for (const point of points) this.boundsBox.expandByPoint(point);
		this.boundsBox.getCenter(this.currentCenter);
		const size = new THREE.Vector3();
		this.boundsBox.getSize(size);
		this.currentRadius = Math.max(size.x, size.y, size.z) * 0.5;
		this.updateContours(this.currentCenter, this.currentRadius);
		this.updateAura(this.currentCenter, this.currentRadius);
		this.captureMemberPositions();
		this.refreshCooldown = GroupMesh.REFRESH_INTERVAL;
		this.geometryDirty = false;
		this.applyModeVisibility();
	}

	dispose(): void {
		this.surfaceMat.dispose();
		this.wireMat.dispose();
		for (const mat of this.contourMats) mat.dispose();
		for (const geometry of this.contourGeometries) geometry.dispose();
		this.auraMat.dispose();
		this.aura.geometry.dispose();
		if (this.currentGeometry) this.currentGeometry.dispose();
		if (this.currentWireGeometry) this.currentWireGeometry.dispose();
	}

	private applyModeVisibility(): void {
		const visible = this.object.visible;
		const effectiveMode =
			this.mode === 'hybrid' ? (this.highlighted ? 'soft' : 'wire') : this.mode;
		this.surface.visible = visible && effectiveMode === 'soft';
		this.wire.visible = visible && (effectiveMode === 'wire' || effectiveMode === 'soft');
		this.contourGroup.visible = visible && effectiveMode === 'contour';
		this.aura.visible = visible && effectiveMode === 'aura';
	}

	private updateContours(center: THREE.Vector3, radius: number): void {
		const scales = [0.9, 1.05, 1.2];
		for (let ringIndex = 0; ringIndex < this.contourGeometries.length; ringIndex += 1) {
			const ringRadius = Math.max(radius * scales[ringIndex], 18);
			const axis = ringIndex % 3;
			const points: number[] = [];
			for (let i = 0; i < CONTOUR_SEGMENTS; i += 1) {
				const t = (i / CONTOUR_SEGMENTS) * Math.PI * 2;
				const x = Math.cos(t) * ringRadius;
				const y = Math.sin(t) * ringRadius;
				if (axis === 0) points.push(center.x + x, center.y + y, center.z);
				if (axis === 1) points.push(center.x, center.y + x, center.z + y);
				if (axis === 2) points.push(center.x + x, center.y, center.z + y);
			}
			this.contourGeometries[ringIndex].setAttribute(
				'position',
				new THREE.Float32BufferAttribute(points, 3)
			);
		}
	}

	private updateAura(center: THREE.Vector3, radius: number): void {
		const points: number[] = [];
		const safeRadius = Math.max(radius, 18);
		for (let i = 0; i < AURA_POINTS; i += 1) {
			const phi = Math.acos(1 - 2 * ((i + 0.5) / AURA_POINTS));
			const theta = Math.PI * (1 + Math.sqrt(5)) * (i + 0.5);
			const r = safeRadius * (0.82 + (i % 7) * 0.045);
			points.push(
				center.x + Math.cos(theta) * Math.sin(phi) * r,
				center.y + Math.sin(theta) * Math.sin(phi) * r,
				center.z + Math.cos(phi) * r
			);
		}
		this.aura.geometry.dispose();
		this.aura.geometry = new THREE.BufferGeometry();
		this.aura.geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
	}

	private hideAll(): void {
		this.surface.visible = false;
		this.wire.visible = false;
		this.contourGroup.visible = false;
		this.aura.visible = false;
	}

	private shouldRebuild(): boolean {
		if (this.geometryDirty) return true;
		for (const member of this.members) {
			const prev = this.lastMemberPositions.get(member.object.uuid);
			if (!prev || prev.distanceToSquared(member.position) > GroupMesh.MOVEMENT_THRESHOLD_SQ) {
				return true;
			}
		}
		if (this.refreshCooldown > 0) {
			this.refreshCooldown -= 1;
			return false;
		}
		return true;
	}

	private captureMemberPositions(): void {
		const live = new Set<string>();
		for (const member of this.members) {
			live.add(member.object.uuid);
			const cached = this.lastMemberPositions.get(member.object.uuid);
			if (cached) cached.copy(member.position);
			else this.lastMemberPositions.set(member.object.uuid, member.position.clone());
		}
		for (const key of this.lastMemberPositions.keys()) {
			if (!live.has(key)) this.lastMemberPositions.delete(key);
		}
	}

	private sampleAroundMembers(members: readonly GroupMember[]): THREE.Vector3[] {
		const out: THREE.Vector3[] = [];
		for (const member of members) {
			member.object.updateMatrixWorld(true);
			this.boundsBox.setFromObject(member.object);
			if (this.boundsBox.isEmpty()) continue;
			this.boundsBox.expandByScalar(HULL_PADDING);

			const { min, max } = this.boundsBox;
			out.push(
				new THREE.Vector3(min.x, min.y, min.z),
				new THREE.Vector3(min.x, min.y, max.z),
				new THREE.Vector3(min.x, max.y, min.z),
				new THREE.Vector3(min.x, max.y, max.z),
				new THREE.Vector3(max.x, min.y, min.z),
				new THREE.Vector3(max.x, min.y, max.z),
				new THREE.Vector3(max.x, max.y, min.z),
				new THREE.Vector3(max.x, max.y, max.z)
			);
		}
		return out;
	}
}
