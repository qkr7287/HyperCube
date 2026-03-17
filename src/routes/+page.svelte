<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { systemStore, containersStore, connect, disconnect } from '$lib/stores/ws-store';
	import LeftSidebar from '$lib/components/LeftSidebar.svelte';
	import RightSidebar from '$lib/components/RightSidebar.svelte';
	import TopologyToolbar from '$lib/components/TopologyToolbar.svelte';
	import RackUtilization from '$lib/components/RackUtilization.svelte';
	import ContainerDetailModal from '$lib/components/ContainerDetailModal.svelte';
	import NetworkDetailModal from '$lib/components/NetworkDetailModal.svelte';
	import LoginDetailModal from '$lib/components/LoginDetailModal.svelte';
	import ProcessDetailModal from '$lib/components/ProcessDetailModal.svelte';
	import CpuDetailModal from '$lib/components/CpuDetailModal.svelte';
	import MemoryDetailModal from '$lib/components/MemoryDetailModal.svelte';
	import DiskDetailModal from '$lib/components/DiskDetailModal.svelte';

	interface Container {
		id: string;
		shortId: string;
		names: string[];
		image: string;
		state: string;
		status: string;
		labels: any;
	}

	interface Project {
		name: string;
		containers: Container[];
		color: string;
		stats: { total: number; running: number; stopped: number; paused: number };
	}

	interface SystemInfo {
		hostname: string;
		os: string;
		cpu: { cores: number; model: string; usage: number };
		memory: { total: string; used: string; free: string; usage: number };
		disk: { total: string; used: string; free: string; usage: number };
		docker: { version: string; containers: number; images: number };
	}

	const projectColors = [
		'#4fc3f7', '#ff7043', '#66bb6a', '#ffa726', '#ab47bc',
		'#26c6da', '#ef5350', '#5c6bc0', '#ffca28', '#ec407a'
	];

	let containers: Container[] = [];
	let projects: Project[] = [];
	let systemInfo: SystemInfo | null = null;
	let selectedProject: string | null = null;
	let graphContainer: HTMLDivElement;
	let graph: any = null;
	let lastUpdate = new Date();
	let unsubSystem: (() => void) | null = null;
	let unsubContainers: (() => void) | null = null;
	let fallbackInterval: ReturnType<typeof setInterval> | null = null;
	let wsDataReceived = false;
	let cameraTransitioning = false;
	let starfieldGroup: any = null;
	let starfieldRotationId: number | null = null;
	let viewMode = 'group';
	let selectedContainer: Container | null = null;
	let cpuModalOpen = false;
	let memoryModalOpen = false;
	let diskModalOpen = false;
	let networkModalOpen = false;
	let loginModalOpen = false;
	let processModalOpen = false;

	function openContainerDetail(container: Container) {
		selectedContainer = container;
		const rawProject = container.labels?.['com.docker.compose.project'] || 'default';
		const projectName = extractProjectPrefix(rawProject);
		updateGraphForProject(projectName);
	}

	function closeContainerDetail() {
		selectedContainer = null;
	}

	// Mock data for demo (used when API is not available)
	const mockContainers: Container[] = [
		{ id: '1', shortId: 'abc1', names: ['/agdreamlog-api-api-1'], image: 'node:20', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '2', shortId: 'abc2', names: ['/agdreamlog-api-db-1'], image: 'postgres:15', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '3', shortId: 'abc3', names: ['/agdreamlog-api-redis-1'], image: 'redis:7', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '4', shortId: 'abc4', names: ['/agdreamlog-api-worker-1'], image: 'node:20', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '5', shortId: 'abc5', names: ['/agdreamlog-api-beat-1'], image: 'node:20', state: 'running', status: 'Up 1 day', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '6', shortId: 'abc6', names: ['/agdreamlog-api-minio-1'], image: 'minio/minio', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '7', shortId: 'def1', names: ['/agdevblog_frontend'], image: 'node:20', state: 'running', status: 'Up 5 days', labels: { 'com.docker.compose.project': 'agdevblog' } },
		{ id: '8', shortId: 'def2', names: ['/agdevblog_backend'], image: 'python:3.11', state: 'running', status: 'Up 5 days', labels: { 'com.docker.compose.project': 'agdevblog' } },
		{ id: '9', shortId: 'def3', names: ['/agdevblog_postgres'], image: 'postgres:15', state: 'running', status: 'Up 5 days', labels: { 'com.docker.compose.project': 'agdevblog' } },
		{ id: '10', shortId: 'def4', names: ['/agdevblog_minio'], image: 'minio/minio', state: 'running', status: 'Up 5 days', labels: { 'com.docker.compose.project': 'agdevblog' } },
		{ id: '11', shortId: 'ghi1', names: ['/agsafecat-backend-backend-1'], image: 'python:3.11', state: 'running', status: 'Up 3 days', labels: { 'com.docker.compose.project': 'agsafecat-backend' } },
		{ id: '12', shortId: 'ghi2', names: ['/agsafecat-backend-celery-1'], image: 'python:3.11', state: 'running', status: 'Up 3 days', labels: { 'com.docker.compose.project': 'agsafecat-backend' } },
		{ id: '13', shortId: 'ghi3', names: ['/agsafecat-backend-db-1'], image: 'postgres:15', state: 'exited', status: 'Exited (0)', labels: { 'com.docker.compose.project': 'agsafecat-backend' } },
		{ id: '14', shortId: 'jkl1', names: ['/ai_translate_frontend'], image: 'node:20', state: 'running', status: 'Up 1 day', labels: { 'com.docker.compose.project': 'aitranslateplatform' } },
		{ id: '15', shortId: 'jkl2', names: ['/ai_translate_backend'], image: 'python:3.11', state: 'running', status: 'Up 1 day', labels: { 'com.docker.compose.project': 'aitranslateplatform' } },
		{ id: '16', shortId: 'jkl3', names: ['/ai_translate_db'], image: 'postgres:15', state: 'running', status: 'Up 1 day', labels: { 'com.docker.compose.project': 'aitranslateplatform' } },
		{ id: '17', shortId: 'mno1', names: ['/3d-widget-web-host-full-three-1'], image: 'node:20', state: 'running', status: 'Up 12 hours', labels: { 'com.docker.compose.project': '3d-widget-web-host' } },
		{ id: '18', shortId: 'mno2', names: ['/3d-widget-web-host-full-babylon-1'], image: 'node:20', state: 'running', status: 'Up 12 hours', labels: { 'com.docker.compose.project': '3d-widget-web-host' } },
		{ id: '19', shortId: 'mno3', names: ['/3d-widget-web-host-webhost-only-three-1'], image: 'node:20', state: 'running', status: 'Up 12 hours', labels: { 'com.docker.compose.project': '3d-widget-web-host' } },
		{ id: '20', shortId: 'mno4', names: ['/3d-widget-web-host-webhost-only-babylon-1'], image: 'node:20', state: 'running', status: 'Up 12 hours', labels: { 'com.docker.compose.project': '3d-widget-web-host' } },
		{ id: '21', shortId: 'pqr1', names: ['/coatervision-web-1'], image: 'node:20', state: 'running', status: 'Up 7 days', labels: { 'com.docker.compose.project': 'coatervision' } },
		{ id: '22', shortId: 'pqr2', names: ['/coatervision-api-1'], image: 'python:3.11', state: 'running', status: 'Up 7 days', labels: { 'com.docker.compose.project': 'coatervision' } },
		{ id: '23', shortId: 'stu1', names: ['/release-notes-frontend-1'], image: 'node:20', state: 'running', status: 'Up 4 days', labels: { 'com.docker.compose.project': 'release-notes' } },
		{ id: '24', shortId: 'stu2', names: ['/release-notes-backend-1'], image: 'python:3.11', state: 'exited', status: 'Exited (1)', labels: { 'com.docker.compose.project': 'release-notes' } },
		{ id: '25', shortId: 'stu3', names: ['/release-notes-db-1'], image: 'postgres:15', state: 'running', status: 'Up 4 days', labels: { 'com.docker.compose.project': 'release-notes' } },
	];

	function extractProjectPrefix(name: string): string {
		const parts = name.split(/[-_]/);
		if (parts.length > 1 && parts[0].length >= 2) return parts[0];
		return name;
	}

	function groupContainers(containerList: Container[]) {
		const projectMap = new Map<string, Container[]>();

		containerList.forEach(container => {
			const rawProject = container.labels?.['com.docker.compose.project'] || 'default';
			const projectName = extractProjectPrefix(rawProject);
			if (!projectMap.has(projectName)) projectMap.set(projectName, []);
			projectMap.get(projectName)!.push(container);
		});

		projects = Array.from(projectMap.entries()).map(([name, ctrs], i) => ({
			name,
			containers: ctrs,
			color: projectColors[i % projectColors.length],
			stats: {
				total: ctrs.length,
				running: ctrs.filter(c => c.state === 'running').length,
				stopped: ctrs.filter(c => c.state === 'exited').length,
				paused: ctrs.filter(c => c.state === 'paused').length,
			}
		})).sort((a, b) => a.name.localeCompare(b.name));
	}

	function getContainerDisplayName(container: Container): string {
		const name = container.names?.[0]?.replace('/', '') || container.shortId;
		return name.replace(/^[a-z0-9]+-/, '').replace(/-1$/, '').replace(/_1$/, '');
	}

	function getNodeColor(container: Container): string {
		const project = projects.find(p => p.containers.some(c => c.id === container.id));
		return project?.color || '#888';
	}

	function getStateColor(state: string): string {
		switch (state) {
			case 'running': return '#00e676';
			case 'exited': return '#ff1744';
			case 'paused': return '#ff9100';
			default: return '#546e7a';
		}
	}

	function getStateEmissive(state: string): string {
		switch (state) {
			case 'running': return '#00ff88';
			case 'exited': return '#ff3333';
			case 'paused': return '#ffaa00';
			default: return '#333333';
		}
	}

	function buildGraphData() {
		const nodes: any[] = [];
		const links: any[] = [];

		containers.forEach(container => {
			const project = projects.find(p => p.containers.some(c => c.id === container.id));
			nodes.push({
				id: container.id,
				name: getContainerDisplayName(container),
				fullName: container.names?.[0]?.replace('/', '') || container.shortId,
				image: container.image,
				state: container.state,
				project: project?.name || 'default',
				color: project?.color || '#888',
				val: container.state === 'running' ? 8 : 4,
				isHub: false,
			});
		});

		projects.forEach(project => {
			const hubId = `hub-${project.name}`;
			nodes.push({
				id: hubId,
				name: project.name,
				state: 'hub',
				project: project.name,
				color: project.color,
				val: 15,
				isHub: true,
			});

			project.containers.forEach(c => {
				links.push({
					source: hubId,
					target: c.id,
					project: project.name,
				});
			});
		});

		return { nodes, links };
	}

	async function initGraph() {
		if (!browser || !graphContainer) return;

		// @ts-ignore
		const ForceGraph3D = (await import('3d-force-graph')).default;
		const THREE = await import('three');

		const data = buildGraphData();

		// @ts-ignore
		graph = ForceGraph3D({
			extraRenderers: []
		})(graphContainer)
			.backgroundColor('#0d1117')
			.width(graphContainer.clientWidth)
			.height(graphContainer.clientHeight)
			.graphData(data)
			.cooldownTicks(100)
			.cooldownTime(3000)
			.d3AlphaDecay(0.05)
			.d3VelocityDecay(0.4)
			.warmupTicks(50)
			.nodeThreeObject((node: any) => {
				if (!node) return new THREE.Object3D();

				const group = new THREE.Group();

				if (node.isHub) {
					const hubSize = 5;
					const geo = new THREE.IcosahedronGeometry(hubSize, 1);
					const mat = new THREE.MeshPhongMaterial({
						color: new THREE.Color(node.color),
						emissive: new THREE.Color(node.color),
						emissiveIntensity: 0.7,
						transparent: true,
						opacity: 0.6,
						shininess: 200,
						wireframe: false,
					});
					group.add(new THREE.Mesh(geo, mat));

					const wireGeo = new THREE.IcosahedronGeometry(hubSize * 1.05, 1);
					const wireMat = new THREE.MeshBasicMaterial({
						color: new THREE.Color(node.color),
						transparent: true,
						opacity: 0.3,
						wireframe: true,
					});
					group.add(new THREE.Mesh(wireGeo, wireMat));

					const glowGeo = new THREE.IcosahedronGeometry(hubSize * 1.6, 1);
					const glowMat = new THREE.MeshBasicMaterial({
						color: new THREE.Color(node.color),
						transparent: true,
						opacity: 0.06,
						side: THREE.BackSide,
					});
					group.add(new THREE.Mesh(glowGeo, glowMat));

					const canvas = document.createElement('canvas');
					const ctx = canvas.getContext('2d')!;
					canvas.width = 512;
					canvas.height = 64;
					ctx.font = 'bold 24px Arial';
					ctx.textAlign = 'center';
					ctx.fillStyle = node.color;
					ctx.fillText(node.name.toUpperCase(), 256, 40);

					const texture = new THREE.CanvasTexture(canvas);
					const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
						map: texture, transparent: true, opacity: 0.9,
					}));
					sprite.scale.set(30, 4, 1);
					sprite.position.set(0, hubSize + 5, 0);
					group.add(sprite);

					return group;
				}

				const isRunning = node.state === 'running';
				const size = isRunning ? 6 : 4;
				const stateColor = getStateColor(node.state);

				const geometry = new THREE.BoxGeometry(size, size, size);
				const material = new THREE.MeshPhongMaterial({
					color: new THREE.Color(stateColor),
					emissive: new THREE.Color(getStateEmissive(node.state)),
					emissiveIntensity: isRunning ? 0.6 : 0.15,
					transparent: true,
					opacity: isRunning ? 0.9 : 0.4,
					shininess: isRunning ? 150 : 30,
				});
				group.add(new THREE.Mesh(geometry, material));

				const wireGeo = new THREE.EdgesGeometry(geometry);
				const wireMat = new THREE.LineBasicMaterial({
					color: new THREE.Color(stateColor),
					transparent: true,
					opacity: isRunning ? 0.8 : 0.3,
				});
				group.add(new THREE.LineSegments(wireGeo, wireMat));

				if (isRunning) {
					const glowGeo = new THREE.BoxGeometry(size * 1.3, size * 1.3, size * 1.3);
					const glowMat = new THREE.MeshBasicMaterial({
						color: new THREE.Color(stateColor),
						transparent: true,
						opacity: 0.08,
						side: THREE.BackSide,
					});
					group.add(new THREE.Mesh(glowGeo, glowMat));
				}

				const canvas = document.createElement('canvas');
				const ctx = canvas.getContext('2d')!;
				canvas.width = 256;
				canvas.height = 64;
				ctx.font = 'bold 18px Arial';
				ctx.textAlign = 'center';
				const label = node.name;
				ctx.fillStyle = stateColor;
				ctx.beginPath();
				ctx.arc(128 - ctx.measureText(label).width / 2 - 10, 36, 4, 0, Math.PI * 2);
				ctx.fill();
				ctx.fillStyle = isRunning ? '#ffffff' : '#888888';
				ctx.fillText(label, 128, 40);

				const texture = new THREE.CanvasTexture(canvas);
				const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
					map: texture, transparent: true, opacity: isRunning ? 0.9 : 0.5,
				}));
				sprite.scale.set(20, 5, 1);
				sprite.position.set(0, size + 4, 0);
				group.add(sprite);

				return group;
			})
			.nodeVal((node: any) => node.val)
			.linkColor((link: any) => {
				const project = projects.find(p => p.name === link.project);
				const c = project?.color || '#4fc3f7';
				return c + '40';
			})
			.linkWidth(1.2)
			.linkOpacity(0.4)
			.linkDirectionalParticles(2)
			.linkDirectionalParticleWidth(1.5)
			.linkDirectionalParticleSpeed(0.004)
			.linkDirectionalParticleColor((link: any) => {
				const project = projects.find(p => p.name === link.project);
				return project?.color || '#4fc3f7';
			})
			.d3Force('charge', null)
			.d3Force('center', null)
			.onNodeHover((node: any) => {
				graphContainer.style.cursor = node ? 'pointer' : 'default';
			})
			.onNodeClick((node: any) => {
				if (!node) return;
				if (node.project) {
					updateGraphForProject(
						selectedProject === node.project ? null : node.project
					);
				}
			})
			.onNodeDrag((node: any) => {
				if (node) graph.d3ReheatSimulation();
				markHullDirty();
			})
			.onNodeDragEnd((node: any) => {
				if (node) {
					node.fx = node.x;
					node.fy = node.y;
					node.fz = node.z;
				}
				const controls = graph.controls();
				if (controls) controls.enabled = true;
			})
			.enableNodeDrag(true)
			.onEngineTick(() => {
				markHullDirty();
			});

		// @ts-ignore
		const d3 = await import('d3-force-3d');
		graph.d3Force('charge', d3.forceManyBody().strength(-120));
		graph.d3Force('center', d3.forceCenter(0, 0, 0).strength(0.05));

		// Bloom post-processing
		try {
			const { UnrealBloomPass } = await import('three/examples/jsm/postprocessing/UnrealBloomPass.js');
			const { EffectComposer } = await import('three/examples/jsm/postprocessing/EffectComposer.js');
			const { RenderPass } = await import('three/examples/jsm/postprocessing/RenderPass.js');

			const renderer = graph.renderer();
			const scene = graph.scene();
			const camera = graph.camera();

			const composer = new EffectComposer(renderer);
			composer.addPass(new RenderPass(scene, camera));

			const bloomPass = new UnrealBloomPass(
				new THREE.Vector2(window.innerWidth, window.innerHeight),
				1.2, 0.4, 0.85
			);
			composer.addPass(bloomPass);
			graph.postProcessingComposer(composer);
		} catch (e) {
			console.warn('Bloom post-processing not available:', e);
		}

		// Lighting
		const scene = graph.scene();
		const ambientLight = new THREE.AmbientLight(0x404060, 0.8);
		scene.add(ambientLight);
		const pointLight = new THREE.PointLight(0x4fc3f7, 1.5, 500);
		pointLight.position.set(0, 100, 0);
		scene.add(pointLight);

		// Starfield
		starfieldGroup = new THREE.Group();

		function addStarLayer(count: number, minR: number, maxR: number, color: number, size: number, opacity: number) {
			const positions = new Float32Array(count * 3);
			for (let i = 0; i < count; i++) {
				const r = minR + Math.random() * (maxR - minR);
				const theta = Math.random() * Math.PI * 2;
				const phi = Math.acos(2 * Math.random() - 1);
				positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
				positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
				positions[i * 3 + 2] = r * Math.cos(phi);
			}
			const geo = new THREE.BufferGeometry();
			geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
			const mat = new THREE.PointsMaterial({
				color, size, transparent: true, opacity, sizeAttenuation: true,
			});
			starfieldGroup.add(new THREE.Points(geo, mat));
		}

		addStarLayer(5000, 500, 1200, 0xaabbcc, 0.8, 0.3);
		addStarLayer(2000, 350, 800, 0xffffff, 1.4, 0.6);
		addStarLayer(150, 300, 600, 0xffffff, 3.0, 0.9);
		addStarLayer(300, 400, 900, 0x4fc3f7, 1.8, 0.4);
		addStarLayer(150, 400, 900, 0xffaa44, 1.5, 0.25);
		addStarLayer(100, 450, 900, 0xbb77ff, 1.6, 0.2);

		const nebulaColors = [0x1a0a3e, 0x0a1a3e, 0x0a2a2a];
		nebulaColors.forEach((color, i) => {
			const nebulaGeo = new THREE.SphereGeometry(600 + i * 150, 16, 16);
			const nebulaMat = new THREE.MeshBasicMaterial({
				color: new THREE.Color(color),
				transparent: true,
				opacity: 0.08 - i * 0.02,
				side: THREE.BackSide,
				depthWrite: false,
			});
			const nebula = new THREE.Mesh(nebulaGeo, nebulaMat);
			nebula.rotation.set(i * 0.5, i * 0.8, i * 0.3);
			starfieldGroup.add(nebula);
		});

		scene.add(starfieldGroup);

		function rotateStarfield() {
			if (starfieldGroup) {
				starfieldGroup.rotation.y += 0.00006;
				starfieldGroup.rotation.x += 0.00002;
			}
			starfieldRotationId = requestAnimationFrame(rotateStarfield);
		}
		rotateStarfield();

		const controls = graph.controls();
		if (controls) {
			controls.rotateSpeed = 1.2;
			controls.zoomSpeed = 0.6;
			controls.panSpeed = 0.05;
			controls.dynamicDampingFactor = 0.25;

			const origOnPointerUp = controls.onPointerUp?.bind(controls);
			if (origOnPointerUp) {
				controls.onPointerUp = function(event: any) {
					try { origOnPointerUp(event); } catch (_) { /* ignore */ }
				};
			}
		}

		// Set initial camera position
		graph.cameraPosition({ x: 0, y: 0, z: 500 }, { x: 0, y: 0, z: 0 });

		graphInitialized = true;

		await ensureHullDeps();
		startHullUpdates();

		if (controls) {
			controls.addEventListener('change', () => {
				if (!selectedProject || !graph || cameraTransitioning) return;
				const cam = graph.camera();
				if (!cam) return;

				const allNodes = graph.graphData().nodes;
				const projectNodes = allNodes.filter((n: any) => n.project === selectedProject && !n.isHub);
				if (projectNodes.length === 0) return;

				const cx = projectNodes.reduce((s: number, n: any) => s + (n.x || 0), 0) / projectNodes.length;
				const cy = projectNodes.reduce((s: number, n: any) => s + (n.y || 0), 0) / projectNodes.length;
				const cz = projectNodes.reduce((s: number, n: any) => s + (n.z || 0), 0) / projectNodes.length;

				const dx = cam.position.x - cx;
				const dy = cam.position.y - cy;
				const dz = cam.position.z - cz;
				const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

				if (dist > 350) {
					gatherNodesToCenter();
				}
			});
		}
	}

	let hullMeshes: Map<string, any> = new Map();
	let cachedConvexGeometry: any = null;
	let cachedTHREE: any = null;

	function removeHull(projectName?: string) {
		if (!graph) return;
		const scene = graph.scene();
		if (projectName) {
			const mesh = hullMeshes.get(projectName);
			if (mesh) {
				scene.remove(mesh);
				mesh.children.forEach((child: any) => { child.geometry?.dispose(); child.material?.dispose(); });
				mesh.geometry?.dispose();
				mesh.material?.dispose();
				hullMeshes.delete(projectName);
			}
		} else {
			hullMeshes.forEach(mesh => {
				scene.remove(mesh);
				mesh.children.forEach((child: any) => { child.geometry?.dispose(); child.material?.dispose(); });
				mesh.geometry?.dispose();
				mesh.material?.dispose();
			});
			hullMeshes.clear();
		}
	}

	async function ensureHullDeps() {
		if (!cachedTHREE) cachedTHREE = await import('three');
		if (!cachedConvexGeometry) {
			// @ts-ignore
			const mod = await import('three/examples/jsm/geometries/ConvexGeometry.js');
			cachedConvexGeometry = mod.ConvexGeometry;
		}
	}

	function rebuildAllHulls() {
		if (!graph) return;
		const THREE = cachedTHREE;
		const ConvexGeometry = cachedConvexGeometry;
		if (!THREE || !ConvexGeometry) return;

		projects.forEach(project => {
			const projectNodes = graph.graphData().nodes.filter(
				(n: any) => n.project === project.name
			);
			if (projectNodes.length < 2) {
				removeHull(project.name);
				return;
			}

			removeHull(project.name);

			try {
				const points: any[] = [];
				const padding = 18;
				projectNodes.forEach((n: any) => {
					const x = n.x || 0, y = n.y || 0, z = n.z || 0;
					points.push(new THREE.Vector3(x + padding, y, z));
					points.push(new THREE.Vector3(x - padding, y, z));
					points.push(new THREE.Vector3(x, y + padding, z));
					points.push(new THREE.Vector3(x, y - padding, z));
					points.push(new THREE.Vector3(x, y, z + padding));
					points.push(new THREE.Vector3(x, y, z - padding));
				});

				const isSelected = project.name === selectedProject;
				const geo = new ConvexGeometry(points);
				const mat = new THREE.MeshBasicMaterial({
					color: new THREE.Color(project.color),
					transparent: true,
					opacity: isSelected ? 0.06 : 0.03,
					side: THREE.DoubleSide,
					depthWrite: false,
				});
				const mesh = new THREE.Mesh(geo, mat);

				const edgeGeo = new THREE.EdgesGeometry(geo);
				const edgeMat = new THREE.LineBasicMaterial({
					color: new THREE.Color(project.color),
					transparent: true,
					opacity: isSelected ? 0.2 : 0.08,
				});
				mesh.add(new THREE.LineSegments(edgeGeo, edgeMat));

				graph.scene().add(mesh);
				hullMeshes.set(project.name, mesh);
			} catch (e) {
				// Hull is cosmetic
			}
		});
	}

	let hullAnimationId: number | null = null;
	let hullDirty = false;

	function stopHullUpdates() {
		if (hullAnimationId) {
			cancelAnimationFrame(hullAnimationId);
			hullAnimationId = null;
		}
		hullDirty = false;
	}

	function markHullDirty() {
		hullDirty = true;
	}

	function startHullUpdates() {
		stopHullUpdates();
		function tick() {
			if (hullDirty) {
				rebuildAllHulls();
				hullDirty = false;
			}
			hullAnimationId = requestAnimationFrame(tick);
		}
		hullDirty = true;
		hullAnimationId = requestAnimationFrame(tick);
	}

	async function updateGraphForProject(projectName: string | null) {
		if (!graph) return;

		selectedProject = projectName;

		if (projectName) {
			cameraTransitioning = true;

			graph.graphData().nodes.forEach((n: any) => {
				n.fx = undefined;
				n.fy = undefined;
				n.fz = undefined;
			});

			const hubNode = graph.graphData().nodes.find((n: any) => n.id === `hub-${projectName}`);
			const anchorX = hubNode?.x || 0;
			const anchorY = hubNode?.y || 0;
			const anchorZ = hubNode?.z || 0;

			const camDist = 150;
			graph.cameraPosition(
				{ x: anchorX + camDist * 0.55, y: anchorY + camDist * 0.35, z: anchorZ + camDist * 0.55 },
				{ x: anchorX, y: anchorY, z: anchorZ },
				1500
			);

			// @ts-ignore
			import('d3-force-3d').then(d3 => {
				graph.d3Force('cluster', d3.forceRadial(35, anchorX, anchorY, anchorZ)
					.strength((node: any) => node.project === projectName ? 0.3 : 0));
				graph.d3Force('scatter', d3.forceManyBody()
					.strength((node: any) => node.project !== projectName ? -150 : 0));
				graph.cooldownTicks(300);
				graph.d3AlphaDecay(0.008);
				graph.d3VelocityDecay(0.6);
				graph.d3ReheatSimulation();
			});

			setTimeout(() => {
				const projectNodes = graph.graphData().nodes.filter((n: any) => n.project === projectName);
				if (projectNodes.length === 0) return;

				const cx = projectNodes.reduce((s: number, n: any) => s + (n.x || 0), 0) / projectNodes.length;
				const cy = projectNodes.reduce((s: number, n: any) => s + (n.y || 0), 0) / projectNodes.length;
				const cz = projectNodes.reduce((s: number, n: any) => s + (n.z || 0), 0) / projectNodes.length;

				let maxDist = 0;
				projectNodes.forEach((n: any) => {
					const d = Math.hypot((n.x || 0) - cx, (n.y || 0) - cy, (n.z || 0) - cz);
					if (d > maxDist) maxDist = d;
				});

				const camera = graph.camera();
				const fov = camera?.fov || 60;
				const halfFovRad = (fov / 2) * (Math.PI / 180);
				const radius = Math.max(maxDist, 30) + 30;
				const fitDist = (radius / Math.tan(halfFovRad)) * 1.6;

				graph.cameraPosition(
					{ x: cx + fitDist * 0.55, y: cy + fitDist * 0.35, z: cz + fitDist * 0.55 },
					{ x: cx, y: cy, z: cz },
					800
				);

				setTimeout(() => { cameraTransitioning = false; }, 1600);
				markHullDirty();
			}, 1000);
		} else {
			gatherNodesToCenter();
		}
	}

	function gatherNodesToCenter() {
		if (!graph) return;

		selectedProject = null;

		graph.graphData().nodes.forEach((n: any) => {
			n.fx = undefined;
			n.fy = undefined;
			n.fz = undefined;
		});

		// @ts-ignore
		import('d3-force-3d').then(d3 => {
			graph.d3Force('scatter', null);
			graph.d3Force('cluster', d3.forceRadial(8, 0, 0, 0).strength(0.25));
			graph.cooldownTicks(300);
			graph.d3AlphaDecay(0.008);
			graph.d3VelocityDecay(0.6);
			graph.d3ReheatSimulation();
		});

		markHullDirty();
	}

	let graphInitialized = false;

	async function fetchData() {
		try {
			const response = await fetch(`${base}/api/containers`);
			const result = await response.json();
			if (result.success) {
				containers = result.data;
				groupContainers(containers);
				lastUpdate = new Date();
				if (graph && graphInitialized) {
					const currentNodes = graph.graphData().nodes;
					currentNodes.forEach((node: any) => {
						const updated = containers.find((c: Container) => c.id === node.id);
						if (updated) {
							node.state = updated.state;
							node.val = updated.state === 'running' ? 8 : 4;
						}
					});
					graph.nodeThreeObject(graph.nodeThreeObject());
				}
				return;
			}
		} catch (e) {
			// API not available, use mock data
		}
		containers = mockContainers;
		groupContainers(containers);
		lastUpdate = new Date();
	}

	async function fetchSystemInfoData() {
		try {
			const response = await fetch(`${base}/api/system`);
			const result = await response.json();
			if (result.success) {
				systemInfo = result.data;
				return;
			}
		} catch (e) {
			// Use mock
		}
		systemInfo = {
			hostname: 'agicsai-desktop',
			os: 'Ubuntu 22.04.3 LTS',
			cpu: { cores: 16, model: 'AMD Ryzen 9 5950X', usage: 23.5 },
			memory: { total: '64.0 GB', used: '28.3 GB', free: '35.7 GB', usage: 44.2 },
			disk: { total: '1.0 TB', used: '456 GB', free: '544 GB', usage: 45.6 },
			docker: { version: '24.0.7', containers: 25, images: 42 },
		};
	}

	// Toolbar actions
	async function handleScreenshot() {
		try {
			const html2canvas = (await import('html2canvas')).default;
			const canvas = await html2canvas(document.body, {
				backgroundColor: '#0d1117',
				scale: 2,
				useCORS: true,
				logging: false,
			});
			const dataUrl = canvas.toDataURL('image/png');
			const link = document.createElement('a');
			link.download = `agics-monitor-${Date.now()}.png`;
			link.href = dataUrl;
			link.click();
		} catch (e) {
			// Fallback: 3D canvas only
			if (!graph) return;
			const renderer = graph.renderer();
			if (!renderer) return;
			renderer.render(graph.scene(), graph.camera());
			const dataUrl = renderer.domElement.toDataURL('image/png');
			const link = document.createElement('a');
			link.download = `topology-${Date.now()}.png`;
			link.href = dataUrl;
			link.click();
		}
	}

	let autoRotating = false;
	let autoRotateId: number | null = null;
	let autoRotatePausedByDrag = false;

	function handleRotate() {
		autoRotating = !autoRotating;
		if (autoRotating) {
			startAutoRotate();
		} else {
			stopAutoRotate();
		}
	}

	function startAutoRotate() {
		stopAutoRotate();
		const controls = graph?.controls();
		if (controls) {
			controls.addEventListener('start', pauseAutoRotateOnDrag);
			controls.addEventListener('end', resumeAutoRotateAfterDrag);
		}
		function tick() {
			if (!graph || !autoRotating || autoRotatePausedByDrag) {
				autoRotateId = requestAnimationFrame(tick);
				return;
			}
			const cam = graph.camera();
			if (cam) {
				const speed = 0.003;
				const x = cam.position.x * Math.cos(speed) - cam.position.z * Math.sin(speed);
				const z = cam.position.x * Math.sin(speed) + cam.position.z * Math.cos(speed);
				cam.position.x = x;
				cam.position.z = z;
				cam.lookAt(0, 0, 0);
			}
			autoRotateId = requestAnimationFrame(tick);
		}
		autoRotateId = requestAnimationFrame(tick);
	}

	function stopAutoRotate() {
		if (autoRotateId) {
			cancelAnimationFrame(autoRotateId);
			autoRotateId = null;
		}
		const controls = graph?.controls();
		if (controls) {
			controls.removeEventListener('start', pauseAutoRotateOnDrag);
			controls.removeEventListener('end', resumeAutoRotateAfterDrag);
		}
		autoRotatePausedByDrag = false;
	}

	function pauseAutoRotateOnDrag() {
		autoRotatePausedByDrag = true;
	}

	function resumeAutoRotateAfterDrag() {
		autoRotatePausedByDrag = false;
	}

	function handleReset() {
		if (!graph) return;

		// Deselect project
		selectedProject = null;

		// Unfix all nodes, gather to center
		gatherNodesToCenter();

		// Reset camera to initial default position
		graph.cameraPosition(
			{ x: 0, y: 0, z: 500 },
			{ x: 0, y: 0, z: 0 },
			800
		);
	}

	onMount(async () => {
		// Initial data fetch (REST fallback for first paint)
		await fetchData();
		await fetchSystemInfoData();
		await initGraph();

		if (graphContainer) {
			graphContainer.addEventListener('pointerleave', () => {
				const controls = graph?.controls();
				if (controls) controls.enabled = true;
			});
		}

		// Connect WebSocket and subscribe to stores
		connect();

		unsubSystem = systemStore.subscribe((data) => {
			if (data) {
				systemInfo = data;
				wsDataReceived = true;
				// WS is working, stop REST fallback
				if (fallbackInterval) { clearInterval(fallbackInterval); fallbackInterval = null; }
			}
		});

		unsubContainers = containersStore.subscribe((data) => {
			if (data && data.length > 0) {
				containers = data;
				groupContainers(containers);
				lastUpdate = new Date();
				if (graph && graphInitialized) {
					const currentNodes = graph.graphData().nodes;
					currentNodes.forEach((node: any) => {
						const updated = containers.find((c: Container) => c.id === node.id);
						if (updated) {
							node.state = updated.state;
							node.val = updated.state === 'running' ? 8 : 4;
						}
					});
					graph.nodeThreeObject(graph.nodeThreeObject());
				}
			}
		});

		// REST fallback: if WS doesn't deliver within 3s, poll via REST
		setTimeout(() => {
			if (!wsDataReceived) {
				fallbackInterval = setInterval(async () => {
					await fetchData();
					await fetchSystemInfoData();
				}, 10000);
			}
		}, 3000);
	});

	onDestroy(() => {
		stopHullUpdates();
		stopAutoRotate();
		if (starfieldRotationId) cancelAnimationFrame(starfieldRotationId);
		if (unsubSystem) unsubSystem();
		if (unsubContainers) unsubContainers();
		if (fallbackInterval) clearInterval(fallbackInterval);
		disconnect();
		if (graph) graph._destructor?.();
	});

	function handleResize() {
		if (graph && graphContainer) {
			graph.width(graphContainer.clientWidth);
			graph.height(graphContainer.clientHeight);
		}
	}
</script>

<svelte:window on:resize={handleResize} />

<svelte:head>
	<title>AGICS Container Monitor</title>
</svelte:head>

<div class="layout">
	<!-- Left Sidebar: Server Info -->
	<LeftSidebar
		{systemInfo}
		totalContainers={containers.length}
		onOpenCpu={() => { cpuModalOpen = true; }}
		onOpenMemory={() => { memoryModalOpen = true; }}
		onOpenDisk={() => { diskModalOpen = true; }}
		onOpenNetwork={() => { networkModalOpen = true; }}
		onOpenLogin={() => { loginModalOpen = true; }}
		onOpenProcess={() => { processModalOpen = true; }}
	/>

	<!-- Center: 3D Topology -->
	<main class="topology-area">
		<div class="topology-header">
			<span class="topology-title">SYSTEM TOPOLOGY</span>
			<div class="live-indicator">
				<span class="live-dot"></span>
				<span class="live-text">LIVE RENDER</span>
			</div>
		</div>

		<div class="graph-wrapper">
			<div class="graph-container" bind:this={graphContainer}></div>
			<RackUtilization {systemInfo} />
			<TopologyToolbar
				onScreenshot={handleScreenshot}
				onRotate={handleRotate}
				onReset={handleReset}
				isRotating={autoRotating}
			/>
		</div>
	</main>

	<!-- Right Sidebar: Container Info -->
	<RightSidebar
		{projects}
		{containers}
		{selectedProject}
		onSelectProject={updateGraphForProject}
		onSelectContainer={openContainerDetail}
		{viewMode}
		onViewModeChange={(mode) => {
			viewMode = mode;
			setTimeout(() => handleResize(), 350);
		}}
	/>
</div>

<ContainerDetailModal
	container={selectedContainer}
	onClose={closeContainerDetail}
	onStateChange={fetchData}
/>

<CpuDetailModal
	open={cpuModalOpen}
	{systemInfo}
	onClose={() => { cpuModalOpen = false; }}
/>

<MemoryDetailModal
	open={memoryModalOpen}
	{systemInfo}
	onClose={() => { memoryModalOpen = false; }}
/>

<DiskDetailModal
	open={diskModalOpen}
	{systemInfo}
	onClose={() => { diskModalOpen = false; }}
/>

<NetworkDetailModal
	open={networkModalOpen}
	onClose={() => { networkModalOpen = false; }}
/>

<LoginDetailModal
	open={loginModalOpen}
	onClose={() => { loginModalOpen = false; }}
/>

<ProcessDetailModal
	open={processModalOpen}
	onClose={() => { processModalOpen = false; }}
/>

<style>
	.layout {
		display: flex;
		height: 100vh;
		width: 100vw;
		background: var(--bg-base);
	}

	.topology-area {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		background: var(--bg-base);
	}

	.topology-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 24px;
		flex-shrink: 0;
	}

	.topology-title {
		font-size: 13px;
		font-weight: 700;
		color: var(--text-secondary);
		letter-spacing: -0.01em;
	}

	.live-indicator {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.live-dot {
		width: 6px;
		height: 6px;
		border-radius: var(--radius-full);
		background: var(--accent);
		animation: pulse 2s ease-in-out infinite;
	}

	.live-text {
		font-size: 13px;
		font-weight: 700;
		color: var(--accent);
		letter-spacing: -0.01em;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.4; }
	}

	.graph-wrapper {
		flex: 1;
		position: relative;
		overflow: hidden;
	}

	.graph-container {
		width: 100%;
		height: 100%;
	}
</style>
