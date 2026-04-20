import * as THREE from 'three';

export type LinePulseMode = 'glow' | 'flow' | 'stream' | 'tunnel';
export type TunnelStyle = 'mist' | 'ribs' | 'subsea' | 'core';
export type TrafficFxStyle = 'soft' | 'comet' | 'relay' | 'surge';
// Four multi-line energy looks. All render the primary line as a
// thin guide and a bundle of extra strands on top for the woven /
// sinewy / arcing look.
export type VolumeEnergyStyle = 'bundle' | 'helix' | 'arc' | 'tendril';

type TunnelPreset = {
	bodyOpacity: number;
	bodyBoost: number;
	bodyWhiteMix: number; // how much to lerp body colour towards white (0 = pure hue)
	stripeOpacity: number;
	stripeBoost: number;
	stripeWhiteMix: number;
	stripeRepeat: number;
	stripeSpeed: number;
	packetOpacity: number;
	packetCount: number;
	packetSpacing: number;
	packetSizeMul: number;
	radiusMul: number;
	stripeRadiusMul: number; // stripe tube radius relative to base radius
};

type TrafficFxPreset = {
	countMul: number;
	speedMul: number;
	coreSizeMul: number;
	glowSizeMul: number;
	coreOpacityMul: number;
	glowOpacityMul: number;
	spacingMul: number;
};

type VolumeEnergyPreset = {
	// Primary (base) line — kept as a thin guide.
	lineOpacity: number;
	lineBoost: number;
	whiteMix: number;
	dashSize: number;
	gapSize: number;
	dashSpeed: number;
	// Extra strands laid on top.
	strandCount: number;
	strandAmplitude: number;
	strandOpacity: number;
	strandWhiteMix: number;
	phaseSpeed: number;
};

// Four styles intentionally pull apart on different axes so they
// read as distinct rather than "same thing with different numbers":
//   mist   — barely-there body, gentle washy stripes (calm fog)
//   ribs   — dim body, sharp high-density stripes (digital segments)
//   subsea — thickest body, balanced stripe with 2 moving packets (deep-sea tunnel)
//   core   — near-invisible body, fast bright stripes with big packets (energy beam)
// Stripe texture = 1 bar per cycle. `stripeRepeat` maps 1:1 to
// on-screen bar count across the full tube, so these values are
// "how many distinct rings of light do I want on this line".
const TUNNEL_PRESETS: Record<TunnelStyle, TunnelPreset> = {
	mist: {
		bodyOpacity: 0.035,
		bodyBoost: 0.05,
		bodyWhiteMix: 0.85,
		stripeOpacity: 0.38,
		stripeBoost: 0.14,
		stripeWhiteMix: 0.8,
		stripeRepeat: 2,
		stripeSpeed: 0.3,
		packetOpacity: 0,
		packetCount: 0,
		packetSpacing: 0.5,
		packetSizeMul: 1.0,
		radiusMul: 1.15,
		stripeRadiusMul: 1.0,
	},
	ribs: {
		bodyOpacity: 0.05,
		bodyBoost: 0.05,
		bodyWhiteMix: 0.2,
		stripeOpacity: 0.82,
		stripeBoost: 0.22,
		stripeWhiteMix: 0.35,
		stripeRepeat: 6,
		stripeSpeed: 0.9,
		packetOpacity: 0,
		packetCount: 0,
		packetSpacing: 0.5,
		packetSizeMul: 0.9,
		radiusMul: 1.0,
		stripeRadiusMul: 1.0,
	},
	subsea: {
		bodyOpacity: 0.045,
		bodyBoost: 0.045,
		bodyWhiteMix: 0.32,
		stripeOpacity: 0.5,
		stripeBoost: 0.1,
		stripeWhiteMix: 0.36,
		stripeRepeat: 3,
		stripeSpeed: 0.5,
		// Traffic needs to pop against the fuchsia tunnel body, so
		// packets are bigger, more numerous and brighter than before.
		packetOpacity: 0.95,
		packetCount: 3,
		packetSpacing: 0.34,
		packetSizeMul: 1.3,
		radiusMul: 1.08,
		stripeRadiusMul: 1.0,
	},
	core: {
		bodyOpacity: 0.02,
		bodyBoost: 0.03,
		bodyWhiteMix: 0.15,
		stripeOpacity: 0.55,
		stripeBoost: 0.18,
		stripeWhiteMix: 0.2,
		stripeRepeat: 4,
		stripeSpeed: 1.25,
		packetOpacity: 0.88,
		packetCount: 2,
		packetSpacing: 0.36,
		packetSizeMul: 1.55,
		radiusMul: 0.8,
		stripeRadiusMul: 1.0,
	},
};

const TRAFFIC_FX_PRESETS: Record<TrafficFxStyle, TrafficFxPreset> = {
	soft: {
		countMul: 1,
		speedMul: 0.92,
		coreSizeMul: 0.95,
		glowSizeMul: 1.12,
		coreOpacityMul: 0.82,
		glowOpacityMul: 0.28,
		spacingMul: 1,
	},
	comet: {
		countMul: 0.5,
		speedMul: 1.08,
		coreSizeMul: 1.35,
		glowSizeMul: 1.9,
		coreOpacityMul: 1.1,
		glowOpacityMul: 0.56,
		spacingMul: 1.35,
	},
	relay: {
		countMul: 1,
		speedMul: 1,
		coreSizeMul: 1.08,
		glowSizeMul: 1.55,
		coreOpacityMul: 1,
		glowOpacityMul: 0.48,
		spacingMul: 0.92,
	},
	surge: {
		countMul: 1.5,
		speedMul: 1.22,
		coreSizeMul: 0.92,
		glowSizeMul: 1.5,
		coreOpacityMul: 1.06,
		glowOpacityMul: 0.52,
		spacingMul: 0.72,
	},
};

export const VOLUME_ENERGY_PRESETS: Record<VolumeEnergyStyle, VolumeEnergyPreset> = {
	// 3 strands weaving with phase-shifted sines — calm energy bundle.
	bundle: {
		lineOpacity: 0.22,
		lineBoost: 0.05,
		whiteMix: 0.2,
		dashSize: 20,
		gapSize: 1.2,
		dashSpeed: 0.25,
		strandCount: 3,
		strandAmplitude: 3.8,
		strandOpacity: 0.75,
		strandWhiteMix: 0.3,
		phaseSpeed: 0.85,
	},
	// 2 strands coiled around the axis — clean sci-fi double helix.
	helix: {
		lineOpacity: 0.28,
		lineBoost: 0.08,
		whiteMix: 0.25,
		dashSize: 20,
		gapSize: 1.2,
		dashSpeed: 0.2,
		strandCount: 2,
		strandAmplitude: 3.2,
		strandOpacity: 0.9,
		strandWhiteMix: 0.4,
		phaseSpeed: 0.9,
	},
	// Primary line + zigzag arcs — crackling plasma.
	arc: {
		lineOpacity: 0.32,
		lineBoost: 0.1,
		whiteMix: 0.3,
		dashSize: 9,
		gapSize: 4,
		dashSpeed: 0.6,
		strandCount: 3,
		strandAmplitude: 5.5,
		strandOpacity: 0.82,
		strandWhiteMix: 0.55,
		phaseSpeed: 5.5, // noise churn rate
	},
	// Many thin strands drifting like sea-grass — tighter bundle.
	tendril: {
		lineOpacity: 0.18,
		lineBoost: 0.04,
		whiteMix: 0.15,
		dashSize: 20,
		gapSize: 1.2,
		dashSpeed: 0.18,
		strandCount: 7,
		strandAmplitude: 1.6,
		strandOpacity: 0.55,
		strandWhiteMix: 0.2,
		phaseSpeed: 0.6,
	},
};

const WHITE = new THREE.Color(0xffffff);

function makeStripeTexture(): THREE.CanvasTexture {
	// Single chunky bar per texture cycle with soft edges.
	// Result: each tile = one clearly-readable stripe with generous
	// empty gap, so at any sensible `repeat` (3..9) we get a handful
	// of distinct bars rather than a fuzz of thin lines.
	const canvas = document.createElement('canvas');
	canvas.width = 128;
	canvas.height = 32;
	const ctx = canvas.getContext('2d');
	if (!ctx) {
		const fallback = new THREE.CanvasTexture(canvas);
		fallback.wrapS = THREE.RepeatWrapping;
		fallback.wrapT = THREE.RepeatWrapping;
		return fallback;
	}

	ctx.clearRect(0, 0, canvas.width, canvas.height);
	// Centre-heavy bar with a feather of half-opacity on each edge.
	// Bar spans ~28px inside a 128px cycle → gap:bar ≈ 3.6:1.
	const barCentre = 64; // centre of 128
	const barHalf = 14;
	const feather = 6;
	const g = ctx.createLinearGradient(barCentre - barHalf - feather, 0, barCentre + barHalf + feather, 0);
	g.addColorStop(0.0, 'rgba(255,255,255,0)');
	g.addColorStop(feather / (barHalf * 2 + feather * 2), 'rgba(255,255,255,0.98)');
	g.addColorStop(1 - feather / (barHalf * 2 + feather * 2), 'rgba(255,255,255,0.98)');
	g.addColorStop(1.0, 'rgba(255,255,255,0)');
	ctx.fillStyle = g;
	ctx.fillRect(barCentre - barHalf - feather, 0, (barHalf + feather) * 2, canvas.height);

	const texture = new THREE.CanvasTexture(canvas);
	texture.wrapS = THREE.RepeatWrapping;
	texture.wrapT = THREE.RepeatWrapping;
	texture.repeat.set(4, 1);
	return texture;
}

function makeCapsuleTexture(): THREE.CanvasTexture {
	// Short pill shape with a tight halo. Tinted at draw time by
	// SpriteMaterial.color so one shared texture covers every packet.
	// Oriented along +x so `SpriteMaterial.rotation = screen-space tangent
	// angle` lines the capsule up with the underlying line direction.
	const canvas = document.createElement('canvas');
	canvas.width = 64;
	canvas.height = 32;
	const ctx = canvas.getContext('2d');
	if (!ctx) {
		return new THREE.CanvasTexture(canvas);
	}

	ctx.clearRect(0, 0, 64, 32);

	// Tight halo — small radius and low alpha so the capsule doesn't
	// bleed into the tunnel body (previous halo was twice as wide and
	// ~2x brighter, which looked hazy).
	const halo = ctx.createRadialGradient(32, 16, 2, 32, 16, 12);
	halo.addColorStop(0, 'rgba(255,255,255,0.12)');
	halo.addColorStop(0.5, 'rgba(255,255,255,0.026)');
	halo.addColorStop(1, 'rgba(255,255,255,0)');
	ctx.fillStyle = halo;
	ctx.fillRect(0, 0, 64, 32);

	// Body — shorter pill: straight section between two rounded caps.
	const x = 24;
	const y = 10;
	const w = 16;
	const h = 12;
	const r = 6;
	ctx.beginPath();
	ctx.moveTo(x + r, y);
	ctx.arcTo(x + w, y, x + w, y + h, r);
	ctx.arcTo(x + w, y + h, x, y + h, r);
	ctx.arcTo(x, y + h, x, y, r);
	ctx.arcTo(x, y, x + w, y, r);
	ctx.closePath();

	const body = ctx.createLinearGradient(0, y, 0, y + h);
	body.addColorStop(0, 'rgba(255,255,255,0.95)');
	body.addColorStop(0.5, 'rgba(255,255,255,1)');
	body.addColorStop(1, 'rgba(255,255,255,0.95)');
	ctx.fillStyle = body;
	ctx.fill();

	const texture = new THREE.CanvasTexture(canvas);
	texture.needsUpdate = true;
	return texture;
}

/**
 * Base single-segment line between a hub and a container. Subclasses
 * choose the material style; this base class keeps the line readable
 * above the membrane and hub meshes.
 */
export abstract class Connection {
	readonly object: THREE.Line;
	protected readonly geometry: THREE.BufferGeometry;
	protected readonly material: THREE.LineBasicMaterial | THREE.LineDashedMaterial;
	protected readonly baseOpacity: number;
	protected readonly baseColor: THREE.Color;
	private curved = false;
	private targetTrafficLevel = 0;
	private visibleTrafficLevel = 0;
	private pulseTime = 0;
	private pulseMode: LinePulseMode = 'tunnel';
	private tunnelStyle: TunnelStyle = 'subsea';
	private trafficFxStyle: TrafficFxStyle = 'soft';
	private packetGlowStrength = 1;
	protected volumeEnergyStyle: VolumeEnergyStyle = 'tendril';
	private curveSeed = 0;
	// Capsule sprites (B1). Each sprite's SpriteMaterial.rotation is
	// recomputed per-render from the screen-space tangent so the capsule
	// lies along the line direction instead of being axis-aligned.
	private readonly packets: THREE.Sprite[] = [];
	private readonly packetMats: THREE.SpriteMaterial[] = [];
	private readonly packetTangents: THREE.Vector3[] = [];
	private readonly packetGlows: THREE.Sprite[] = [];
	private readonly packetGlowMats: THREE.SpriteMaterial[] = [];
	private packetSpeed = 0.25;
	private packetTravelDistance = 0;
	private packetBaseSize = 8;
	private tunnelEnabled = false;
	private energyLineEnabled = false;
	private tunnelRadius = 2.4;
	private tunnelThicknessMul = 1;
	private tunnelMesh: THREE.Mesh | null = null;
	private tunnelMat: THREE.MeshBasicMaterial | null = null;
	private stripeMesh: THREE.Mesh | null = null;
	private stripeMat: THREE.MeshBasicMaterial | null = null;
	private stripeTexture: THREE.CanvasTexture | null = null;
	private tunnelGeometry: THREE.TubeGeometry | null = null;
	private stripeGeometry: THREE.TubeGeometry | null = null;
	// Track last endpoints used to rebuild the tube so we can skip the
	// rebuild while the line is essentially stationary. TubeGeometry is
	// an immutable build; rebuilding every frame (74 network lines x 2
	// tubes x 60fps) was the main source of jitter + GC churn.
	private readonly lastTunnelA = new THREE.Vector3();
	private readonly lastTunnelB = new THREE.Vector3();
	private tunnelGeometryDirty = true;
	private static readonly TUNNEL_REBUILD_THRESHOLD_SQ = 0.14 * 0.14;
	private readonly temp = {
		dir: new THREE.Vector3(),
		normal: new THREE.Vector3(),
		aux: new THREE.Vector3(),
		point: new THREE.Vector3(),
		curvePoints: [] as THREE.Vector3[],
	};
	private static readonly SEGMENTS = 18;
	private static readonly PACKET_TEXTURE = makeCapsuleTexture();
	// Scratch vectors reused by every sprite's onBeforeRender to avoid
	// allocating per frame.
	private static readonly PACKET_SCRATCH_A = new THREE.Vector3();
	private static readonly PACKET_SCRATCH_B = new THREE.Vector3();

	protected constructor(material: THREE.LineBasicMaterial | THREE.LineDashedMaterial) {
		this.geometry = new THREE.BufferGeometry();
		this.geometry.setAttribute(
			'position',
			new THREE.BufferAttribute(new Float32Array((Connection.SEGMENTS + 1) * 3), 3)
		);
		this.material = material;
		this.material.linewidth = 2;
		this.material.toneMapped = false;
		this.material.blending = THREE.AdditiveBlending;
		// depthTest=true so hub and container geometry naturally
		// occlude the portion of the line that's behind them.
		this.material.depthTest = true;
		this.material.depthWrite = false;
		this.baseOpacity = material.opacity;
		this.baseColor = material.color.clone();
		this.object = new THREE.Line(this.geometry, material);
		this.object.renderOrder = 16;
		this.object.raycast = () => {};
		this.object.frustumCulled = false;
	}

	protected enablePackets(color: number, size: number = 10, speed: number = 0.25, count: number = 2): void {
		this.packetBaseSize = size;
		// Short pill: width:height ≈ 1.7:1. Roughly 1/4 of the previous
		// elongated streak so packets read as individual capsules rather
		// than long bars.
		const coreW = size * 0.16;
		const coreH = size * 0.18;
		const glowW = size * 0.22;
		const glowH = size * 0.26;
		for (let i = 0; i < count; i += 1) {
			const mat = new THREE.SpriteMaterial({
				color,
				map: Connection.PACKET_TEXTURE,
				transparent: true,
				opacity: 0,
				depthTest: false,
				depthWrite: false,
				blending: THREE.AdditiveBlending,
				toneMapped: false,
				rotation: 0,
			});
			const sprite = new THREE.Sprite(mat);
			sprite.scale.set(coreW, coreH, 1);
			sprite.renderOrder = 18;
			sprite.raycast = () => {};
			sprite.visible = false;
			sprite.frustumCulled = false;
			const tangent = new THREE.Vector3(1, 0, 0);
			sprite.onBeforeRender = (_renderer, _scene, camera) => {
				if (!sprite.visible) return;
				const a = Connection.PACKET_SCRATCH_A.copy(sprite.position);
				const b = Connection.PACKET_SCRATCH_B.copy(sprite.position).add(tangent);
				a.project(camera);
				b.project(camera);
				mat.rotation = Math.atan2(b.y - a.y, b.x - a.x);
			};
			this.object.add(sprite);
			this.packets.push(sprite);
			this.packetMats.push(mat);
			this.packetTangents.push(tangent);

			const glowMat = new THREE.SpriteMaterial({
				color,
				map: Connection.PACKET_TEXTURE,
				transparent: true,
				opacity: 0,
				depthTest: false,
				depthWrite: false,
				blending: THREE.AdditiveBlending,
				toneMapped: false,
				rotation: 0,
			});
			const glowSprite = new THREE.Sprite(glowMat);
			glowSprite.scale.set(glowW, glowH, 1);
			glowSprite.renderOrder = 17;
			glowSprite.raycast = () => {};
			glowSprite.visible = false;
			glowSprite.frustumCulled = false;
			glowSprite.onBeforeRender = (_renderer, _scene, camera) => {
				if (!glowSprite.visible) return;
				const a = Connection.PACKET_SCRATCH_A.copy(glowSprite.position);
				const b = Connection.PACKET_SCRATCH_B.copy(glowSprite.position).add(tangent);
				a.project(camera);
				b.project(camera);
				glowMat.rotation = Math.atan2(b.y - a.y, b.x - a.x);
			};
			this.object.add(glowSprite);
			this.packetGlows.push(glowSprite);
			this.packetGlowMats.push(glowMat);
		}
		this.packetSpeed = speed;
	}

	protected enableTunnelVisual(color: number, radius: number = 2.4): void {
		this.tunnelEnabled = true;
		this.tunnelRadius = radius;

		this.tunnelMat = new THREE.MeshBasicMaterial({
			color,
			transparent: true,
			opacity: 0.12,
			depthTest: true,
			depthWrite: false,
			blending: THREE.AdditiveBlending,
			toneMapped: false,
			side: THREE.DoubleSide,
		});
		this.tunnelMesh = new THREE.Mesh(new THREE.BufferGeometry(), this.tunnelMat);
		this.tunnelMesh.renderOrder = 14;
		this.tunnelMesh.raycast = () => {};
		this.tunnelMesh.frustumCulled = false;
		this.object.add(this.tunnelMesh);

		this.stripeTexture = makeStripeTexture();
		this.stripeMat = new THREE.MeshBasicMaterial({
			color,
			transparent: true,
			opacity: 0.45,
			depthTest: true,
			depthWrite: false,
			blending: THREE.AdditiveBlending,
			toneMapped: false,
			side: THREE.DoubleSide,
			map: this.stripeTexture,
			alphaMap: this.stripeTexture,
		});
		this.stripeMesh = new THREE.Mesh(new THREE.BufferGeometry(), this.stripeMat);
		this.stripeMesh.renderOrder = 17;
		this.stripeMesh.raycast = () => {};
		this.stripeMesh.visible = false;
		this.stripeMesh.frustumCulled = false;
		this.object.add(this.stripeMesh);
	}

	setPulseMode(mode: LinePulseMode): void {
		this.pulseMode = mode;
	}

	setTunnelStyle(style: TunnelStyle): void {
		this.tunnelStyle = style;
		this.tunnelGeometryDirty = true;
		this.rebuildTunnelGeometry();
	}

	setTunnelThickness(multiplier: number): void {
		this.tunnelThicknessMul = THREE.MathUtils.clamp(multiplier, 0.45, 1.4);
		this.tunnelGeometryDirty = true;
		this.rebuildTunnelGeometry();
	}

	setTrafficFxStyle(style: TrafficFxStyle): void {
		this.trafficFxStyle = style;
	}

	setColor(color: number, packetColor?: number): void {
		this.baseColor.setHex(color);
		this.material.color.setHex(color);
		this.tunnelMat?.color.setHex(color);
		this.stripeMat?.color.setHex(color);
		const trafficColor = packetColor ?? color;
		for (const mat of this.packetMats) mat.color.setHex(trafficColor);
		for (const mat of this.packetGlowMats) mat.color.setHex(trafficColor);
	}

	setPacketGlowStrength(strength: number): void {
		this.packetGlowStrength = strength;
	}

	setVolumeEnergyStyle(style: VolumeEnergyStyle): void {
		this.volumeEnergyStyle = style;
	}

	setCurveSeed(seed: number): void {
		this.curveSeed = seed;
	}

	protected enableEnergyLine(): void {
		this.energyLineEnabled = true;
	}

	setTrafficLevel(level: number): void {
		this.targetTrafficLevel = THREE.MathUtils.clamp(level, 0, 1);
		if (this.targetTrafficLevel <= 0 && this.visibleTrafficLevel <= 0.001) {
			this.material.opacity = this.baseOpacity;
			this.material.color.copy(this.baseColor);
			this.hidePackets();
			this.updateTunnelStyle(0, 0);
		}
	}

	setCurved(enabled: boolean): void {
		this.curved = enabled;
	}

	tick(dt: number): void {
		this.pulseTime += dt;
		const smoothing = 1 - Math.exp(-dt * (this.targetTrafficLevel > this.visibleTrafficLevel ? 6 : 1.75));
		this.visibleTrafficLevel = THREE.MathUtils.lerp(
			this.visibleTrafficLevel,
			this.targetTrafficLevel,
			smoothing
		);
		const displayLevel = this.visibleTrafficLevel > 0.001
			? Math.max(this.visibleTrafficLevel, this.targetTrafficLevel > 0 ? 0.2 : 0)
			: 0;

		const pulse = (Math.sin(this.pulseTime * 6.4) + 1) * 0.5;
		if (displayLevel <= 0) {
			this.material.opacity = this.baseOpacity;
			this.material.color.copy(this.baseColor);
			if (this.material instanceof THREE.LineDashedMaterial) {
				this.material.dashOffset = 0;
			}
			this.hidePackets();
			this.updateTunnelStyle(0, pulse);
			this.onTick(0, pulse, dt);
			return;
		}

		// Tunnel pulse is a network-line-only effect. Stack / Volume
		// lines share the same pulseMode setting but have no tunnel
		// geometry, so fall back to 'flow' for them — otherwise the
		// tunnel branch dims their material by 0.4x and they vanish.
		const effectiveMode: LinePulseMode =
			this.pulseMode === 'tunnel' && !this.tunnelEnabled ? 'flow' : this.pulseMode;
		switch (effectiveMode) {
			case 'glow': {
				const glow = displayLevel * (0.22 + pulse * 0.14);
				this.material.opacity = THREE.MathUtils.clamp(this.baseOpacity + glow, 0.18, 0.86);
				this.material.color.copy(this.baseColor).lerp(WHITE, glow * 0.24);
				if (this.material instanceof THREE.LineDashedMaterial) {
					this.material.dashOffset = -this.pulseTime * (0.16 + displayLevel * 0.46);
				}
				this.hidePackets();
				this.updateTunnelStyle(0, pulse);
				break;
			}
			case 'stream': {
				const glow = displayLevel * (0.3 + pulse * 0.16);
				this.material.opacity = THREE.MathUtils.clamp(this.baseOpacity + glow, 0.22, 0.95);
				this.material.color.copy(this.baseColor).lerp(WHITE, glow * 0.38);
				if (this.material instanceof THREE.LineDashedMaterial) {
					this.material.dashOffset = -this.pulseTime * (0.45 + displayLevel * 0.95);
				}
				this.updatePackets(displayLevel, 2, 0.42, dt);
				this.updateTunnelStyle(0, pulse);
				break;
			}
			case 'tunnel': {
				const glow = displayLevel * (0.16 + pulse * 0.06);
				this.material.opacity = THREE.MathUtils.clamp(this.baseOpacity * 0.4 + glow, 0.14, 0.42);
				this.material.color.copy(this.baseColor).lerp(WHITE, glow * 0.16);
				if (this.material instanceof THREE.LineDashedMaterial) {
					this.material.dashOffset = -this.pulseTime * (0.1 + displayLevel * 0.22);
				}
				this.updatePackets(
					displayLevel,
					TUNNEL_PRESETS[this.tunnelStyle].packetCount,
					TUNNEL_PRESETS[this.tunnelStyle].packetSpacing,
					dt
				);
				this.updateTunnelStyle(displayLevel, pulse);
				break;
			}
			case 'flow':
			default: {
				if (this.energyLineEnabled) {
					const preset = VOLUME_ENERGY_PRESETS[this.volumeEnergyStyle];
					const glow = displayLevel * (0.18 + pulse * 0.07);
					this.material.opacity = THREE.MathUtils.clamp(
						preset.lineOpacity + displayLevel * preset.lineBoost + glow,
						0.32,
						1
					);
					this.material.color.copy(this.baseColor).lerp(WHITE, preset.whiteMix);
					if (this.material instanceof THREE.LineDashedMaterial) {
						this.material.dashSize = preset.dashSize;
						this.material.gapSize = preset.gapSize;
						this.material.dashOffset = -this.pulseTime * (preset.dashSpeed + displayLevel * 0.34);
					}
					this.hidePackets();
					this.updateTunnelStyle(0, pulse);
					break;
				}
				const glow = displayLevel * (0.38 + pulse * 0.2);
				this.material.opacity = THREE.MathUtils.clamp(this.baseOpacity + glow, 0.24, 1);
				this.material.color.copy(this.baseColor).lerp(WHITE, glow * 0.46);
				if (this.material instanceof THREE.LineDashedMaterial) {
					this.material.dashOffset = -this.pulseTime * (0.62 + displayLevel * 1.35);
				}
				this.updatePackets(displayLevel, 1, 0.5, dt);
				this.updateTunnelStyle(0, pulse);
				break;
			}
		}
		this.onTick(displayLevel, pulse, dt);
	}

	private updatePackets(displayLevel: number, count: number, spacing: number, dt: number): void {
		if (this.packets.length === 0) return;
		const preset = TUNNEL_PRESETS[this.tunnelStyle];
		const fxPreset = TRAFFIC_FX_PRESETS[this.trafficFxStyle];
		const pos = this.geometry.attributes.position as THREE.BufferAttribute;
		if (!pos || pos.count < 2) {
			this.hidePackets();
			return;
		}

		const distances = new Float32Array(pos.count);
		let totalLength = 0;
		for (let i = 1; i < pos.count; i += 1) {
			const dx = pos.getX(i) - pos.getX(i - 1);
			const dy = pos.getY(i) - pos.getY(i - 1);
			const dz = pos.getZ(i) - pos.getZ(i - 1);
			totalLength += Math.hypot(dx, dy, dz);
			distances[i] = totalLength;
		}
		if (totalLength <= 1e-3) {
			this.hidePackets();
			return;
		}
		const trafficDensity = THREE.MathUtils.clamp(displayLevel, 0, 1);
		const lengthFactor = THREE.MathUtils.clamp(totalLength / 120, 0.8, 2.2);
		const activeCount = Math.min(
			this.packets.length,
			count <= 0
				? 0
				: Math.max(
					1,
					Math.round(
						THREE.MathUtils.lerp(1, count, 0.25 + trafficDensity * 0.95) *
						fxPreset.countMul *
						lengthFactor
					)
				)
		);
		const effectiveSpacing =
			spacing *
			fxPreset.spacingMul *
			THREE.MathUtils.lerp(1.22, 0.72, trafficDensity) /
			Math.max(1, lengthFactor * 0.9);
		const speedUnitsPerSec =
			THREE.MathUtils.lerp(26, 96, trafficDensity) * fxPreset.speedMul;
		this.packetTravelDistance =
			(this.packetTravelDistance + dt * this.packetSpeed * speedUnitsPerSec) % totalLength;
		for (let packetIndex = 0; packetIndex < this.packets.length; packetIndex += 1) {
			const packet = this.packets[packetIndex];
			const packetMat = this.packetMats[packetIndex];
			const packetGlow = this.packetGlows[packetIndex];
			const packetGlowMat = this.packetGlowMats[packetIndex];
			if (packetIndex >= activeCount) {
				packet.visible = false;
				packetMat.opacity = 0;
				packetGlow.visible = false;
				packetGlowMat.opacity = 0;
				continue;
			}

			const distanceAlong =
				(this.packetTravelDistance + packetIndex * effectiveSpacing * totalLength) % totalLength;
			let idx = 0;
			while (idx < distances.length - 2 && distances[idx + 1] < distanceAlong) idx += 1;
			const segmentStart = distances[idx];
			const segmentLength = Math.max(1e-6, distances[idx + 1] - segmentStart);
			const f = (distanceAlong - segmentStart) / segmentLength;
			const ax = pos.getX(idx);
			const ay = pos.getY(idx);
			const az = pos.getZ(idx);
			const bx = pos.getX(idx + 1);
			const by = pos.getY(idx + 1);
			const bz = pos.getZ(idx + 1);
			const px = ax + (bx - ax) * f;
			const py = ay + (by - ay) * f;
			const pz = az + (bz - az) * f;
			packet.position.set(px, py, pz);
			packetGlow.position.set(px, py, pz);
			// Capsule orientation reference (shared between core + glow).
			const tangent = this.packetTangents[packetIndex];
			const tdx = bx - ax;
			const tdy = by - ay;
			const tdz = bz - az;
			const tLen = Math.hypot(tdx, tdy, tdz);
			if (tLen > 1e-6) {
				tangent.set(tdx / tLen, tdy / tLen, tdz / tLen);
			}
			const pulseGlow =
				0.72 + Math.sin(this.pulseTime * 7.2 + packetIndex * 1.4) * 0.12 + displayLevel * 0.22;
			const coreSizeScale =
				preset.packetSizeMul * fxPreset.coreSizeMul * (1 + displayLevel * 0.16);
			packet.scale.set(
				this.packetBaseSize * 0.16 * coreSizeScale,
				this.packetBaseSize * 0.18 * coreSizeScale,
				1
			);
			packetMat.opacity = THREE.MathUtils.clamp(
				(preset.packetOpacity + displayLevel * 0.14) * pulseGlow * fxPreset.coreOpacityMul,
				0,
				0.92
			);
			const glowSizeScale =
				preset.packetSizeMul *
				fxPreset.glowSizeMul *
				this.packetGlowStrength *
				(1 + displayLevel * 0.22);
			packetGlow.scale.set(
				this.packetBaseSize * 0.22 * glowSizeScale,
				this.packetBaseSize * 0.26 * glowSizeScale,
				1
			);
			// Max halo opacity halved (0.24 → 0.12) — was contributing to
			// the hazy look; the tighter texture halo already provides
			// enough bleed.
			packetGlowMat.opacity = THREE.MathUtils.clamp(
				(preset.packetOpacity * 0.42 + displayLevel * 0.08) *
					(0.92 + pulseGlow * 0.16) *
					fxPreset.glowOpacityMul *
					this.packetGlowStrength,
				0,
				0.07
			);
			packet.visible = true;
			packetGlow.visible = true;
		}
	}

	private updateTunnelStyle(displayLevel: number, pulse: number): void {
		if (!this.tunnelEnabled || !this.tunnelMat || !this.stripeMat || !this.stripeTexture || !this.tunnelMesh || !this.stripeMesh) {
			return;
		}

		const preset = TUNNEL_PRESETS[this.tunnelStyle];
		const visible = this.pulseMode === 'tunnel';
		this.tunnelMesh.visible = visible;
		this.stripeMesh.visible = false;
		if (!visible) {
			this.tunnelMat.opacity = 0;
			this.stripeMat.opacity = 0;
			return;
		}

		// Keep tunnel geometry itself aligned to the curve. Non-uniform
		// mesh scaling in object space was causing the tube to drift away
		// from the underlying line depending on camera angle / path direction.
		this.tunnelMesh.scale.setScalar(1);
		this.stripeMesh.scale.setScalar(1);

		// body — opaque drop per user direction. Clamp tightly so no
		// style bleeds into the others' brightness range.
		this.tunnelMat.opacity = THREE.MathUtils.clamp(
			preset.bodyOpacity + displayLevel * preset.bodyBoost,
			0.015,
			0.22
		);
		this.tunnelMat.color.copy(this.baseColor).lerp(WHITE, preset.bodyWhiteMix);

		// stripe — the dominant cue. Allow it to reach near-full opacity
		// on ribs, stay subtle on mist.
		this.stripeMat.opacity = 0;
		this.stripeMat.color.copy(this.baseColor).lerp(WHITE, preset.stripeWhiteMix);
		this.stripeTexture.repeat.set(preset.stripeRepeat, 1);
		// Stripes are stationary rings on the tube — only packets move.
		this.stripeTexture.offset.x = 0;
	}

	private hidePackets(): void {
		for (let i = 0; i < this.packets.length; i += 1) {
			this.packets[i].visible = false;
			this.packetMats[i].opacity = 0;
			this.packetGlows[i].visible = false;
			this.packetGlowMats[i].opacity = 0;
		}
	}

	/**
	 * Subclasses override to react to endpoint updates (e.g. rebuild
	 * extra strand geometry). Called after the primary position buffer
	 * is updated. Default is no-op.
	 */
	protected onEndpointsUpdated(_a: THREE.Vector3, _b: THREE.Vector3): void {
		/* no-op */
	}

	/**
	 * Subclasses override to animate effects that depend on the live
	 * pulse clock (e.g. strand phase). Called every tick. Default no-op.
	 */
	protected onTick(_displayLevel: number, _pulse: number, _dt: number): void {
		/* no-op */
	}

	setEndpoints(a: THREE.Vector3, b: THREE.Vector3): void {
		const pos = this.geometry.attributes.position as THREE.BufferAttribute;
		if (!this.curved) {
			for (let i = 0; i <= Connection.SEGMENTS; i++) {
				const t = i / Connection.SEGMENTS;
				pos.setXYZ(
					i,
					THREE.MathUtils.lerp(a.x, b.x, t),
					THREE.MathUtils.lerp(a.y, b.y, t),
					THREE.MathUtils.lerp(a.z, b.z, t)
				);
			}
			pos.needsUpdate = true;
			if (this.material instanceof THREE.LineDashedMaterial) {
				this.object.computeLineDistances();
			}
			this.maybeRebuildTunnelGeometry(a, b);
			this.onEndpointsUpdated(a, b);
			return;
		}

		const { dir, normal, aux, point } = this.temp;
		dir.subVectors(b, a);
		const length = dir.length();
		if (length < 1e-3) {
			for (let i = 0; i <= Connection.SEGMENTS; i++) pos.setXYZ(i, a.x, a.y, a.z);
			pos.needsUpdate = true;
			this.maybeRebuildTunnelGeometry(a, b);
			this.onEndpointsUpdated(a, b);
			return;
		}
		dir.normalize();
		normal.crossVectors(dir, new THREE.Vector3(0, 1, 0));
		if (normal.lengthSq() < 1e-4) {
			normal.crossVectors(dir, new THREE.Vector3(1, 0, 0));
		}
		normal.normalize();
		aux.crossVectors(dir, normal).normalize();
		const seed01 = ((Math.sin(this.curveSeed * 12.9898) * 43758.5453) % 1 + 1) % 1;
		const amplitude = Math.min(Math.max(length * 0.1, 10), 28) * (0.86 + seed01 * 0.42);
		const wobble = amplitude * (0.18 + seed01 * 0.18);
		const normalSign = seed01 > 0.5 ? 1 : -1;
		const wobblePhase = seed01 * Math.PI * 2;

		for (let i = 0; i <= Connection.SEGMENTS; i++) {
			const t = i / Connection.SEGMENTS;
			point.set(
				THREE.MathUtils.lerp(a.x, b.x, t),
				THREE.MathUtils.lerp(a.y, b.y, t),
				THREE.MathUtils.lerp(a.z, b.z, t)
			);
			point.addScaledVector(normal, Math.sin(Math.PI * t) * amplitude * normalSign);
			point.addScaledVector(aux, Math.sin(Math.PI * 2 * t + wobblePhase) * wobble);
			pos.setXYZ(i, point.x, point.y, point.z);
		}
		pos.needsUpdate = true;
		if (this.material instanceof THREE.LineDashedMaterial) {
			this.object.computeLineDistances();
		}
		this.maybeRebuildTunnelGeometry(a, b);
		this.onEndpointsUpdated(a, b);
	}

	/**
	 * Only rebuild the tube when endpoints moved meaningfully. Avoids
	 * disposing + re-creating two TubeGeometries per line per frame
	 * (4000+ geometries/sec across the scene), which manifested as
	 * position jitter and GC stalls.
	 */
	private maybeRebuildTunnelGeometry(a: THREE.Vector3, b: THREE.Vector3): void {
		if (!this.tunnelEnabled) return;
		const aMoved = this.lastTunnelA.distanceToSquared(a) > Connection.TUNNEL_REBUILD_THRESHOLD_SQ;
		const bMoved = this.lastTunnelB.distanceToSquared(b) > Connection.TUNNEL_REBUILD_THRESHOLD_SQ;
		if (!this.tunnelGeometryDirty && !aMoved && !bMoved) return;
		this.lastTunnelA.copy(a);
		this.lastTunnelB.copy(b);
		this.tunnelGeometryDirty = false;
		this.rebuildTunnelGeometry();
	}

	private rebuildTunnelGeometry(): void {
		if (!this.tunnelEnabled || !this.tunnelMesh || !this.stripeMesh) return;
		const pos = this.geometry.attributes.position as THREE.BufferAttribute;
		const points = this.temp.curvePoints;
		points.length = 0;
		for (let i = 0; i < pos.count; i += 1) {
			points.push(new THREE.Vector3(pos.getX(i), pos.getY(i), pos.getZ(i)));
		}
		if (points.length < 2) return;

		const curve = new THREE.CatmullRomCurve3(points, false, 'centripetal');
		const preset = TUNNEL_PRESETS[this.tunnelStyle];
		const radius = this.tunnelRadius * this.tunnelThicknessMul * preset.radiusMul;
		// Body and stripe share one tube so the two layers sit on
		// exactly the same curve at exactly the same radius. The old
		// "stripe 4% larger" shell looked misaligned from the side.
		// Render order + additive blending handles the z ordering.
		if (this.tunnelGeometry) this.tunnelGeometry.dispose();
		this.tunnelGeometry = new THREE.TubeGeometry(curve, 48, radius, 10, false);
		this.stripeGeometry = this.tunnelGeometry;
		this.tunnelMesh.geometry = this.tunnelGeometry;
		this.stripeMesh.geometry = this.tunnelGeometry;
	}

	dispose(): void {
		this.geometry.dispose();
		this.material.dispose();
		// THREE.Sprite shares a module-level quad geometry — don't dispose
		// it. Only the per-sprite SpriteMaterial is owned by this line.
		for (let i = 0; i < this.packetMats.length; i += 1) {
			this.packetMats[i].dispose();
			this.packetGlowMats[i].dispose();
		}
		// stripeGeometry is the same reference as tunnelGeometry — dispose once.
		this.tunnelGeometry?.dispose();
		this.tunnelMat?.dispose();
		this.stripeMat?.dispose();
		this.stripeTexture?.dispose();
	}
}
