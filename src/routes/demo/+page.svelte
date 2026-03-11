<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';

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
	let refreshInterval: ReturnType<typeof setInterval>;
	let lastUpdate = new Date();
	let cameraTransitioning = false;

	// Mock data for demo (used when API is not available)
	const mockContainers: Container[] = [
		// agdreamlog project
		{ id: '1', shortId: 'abc1', names: ['/agdreamlog-api-api-1'], image: 'node:20', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '2', shortId: 'abc2', names: ['/agdreamlog-api-db-1'], image: 'postgres:15', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '3', shortId: 'abc3', names: ['/agdreamlog-api-redis-1'], image: 'redis:7', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '4', shortId: 'abc4', names: ['/agdreamlog-api-worker-1'], image: 'node:20', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '5', shortId: 'abc5', names: ['/agdreamlog-api-beat-1'], image: 'node:20', state: 'running', status: 'Up 1 day', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		{ id: '6', shortId: 'abc6', names: ['/agdreamlog-api-minio-1'], image: 'minio/minio', state: 'running', status: 'Up 2 days', labels: { 'com.docker.compose.project': 'agdreamlog-api' } },
		// agdevblog project
		{ id: '7', shortId: 'def1', names: ['/agdevblog_frontend'], image: 'node:20', state: 'running', status: 'Up 5 days', labels: { 'com.docker.compose.project': 'agdevblog' } },
		{ id: '8', shortId: 'def2', names: ['/agdevblog_backend'], image: 'python:3.11', state: 'running', status: 'Up 5 days', labels: { 'com.docker.compose.project': 'agdevblog' } },
		{ id: '9', shortId: 'def3', names: ['/agdevblog_postgres'], image: 'postgres:15', state: 'running', status: 'Up 5 days', labels: { 'com.docker.compose.project': 'agdevblog' } },
		{ id: '10', shortId: 'def4', names: ['/agdevblog_minio'], image: 'minio/minio', state: 'running', status: 'Up 5 days', labels: { 'com.docker.compose.project': 'agdevblog' } },
		// agsafecat project
		{ id: '11', shortId: 'ghi1', names: ['/agsafecat-backend-backend-1'], image: 'python:3.11', state: 'running', status: 'Up 3 days', labels: { 'com.docker.compose.project': 'agsafecat-backend' } },
		{ id: '12', shortId: 'ghi2', names: ['/agsafecat-backend-celery-1'], image: 'python:3.11', state: 'running', status: 'Up 3 days', labels: { 'com.docker.compose.project': 'agsafecat-backend' } },
		{ id: '13', shortId: 'ghi3', names: ['/agsafecat-backend-db-1'], image: 'postgres:15', state: 'exited', status: 'Exited (0)', labels: { 'com.docker.compose.project': 'agsafecat-backend' } },
		// aitranslate project
		{ id: '14', shortId: 'jkl1', names: ['/ai_translate_frontend'], image: 'node:20', state: 'running', status: 'Up 1 day', labels: { 'com.docker.compose.project': 'aitranslateplatform' } },
		{ id: '15', shortId: 'jkl2', names: ['/ai_translate_backend'], image: 'python:3.11', state: 'running', status: 'Up 1 day', labels: { 'com.docker.compose.project': 'aitranslateplatform' } },
		{ id: '16', shortId: 'jkl3', names: ['/ai_translate_db'], image: 'postgres:15', state: 'running', status: 'Up 1 day', labels: { 'com.docker.compose.project': 'aitranslateplatform' } },
		// 3d-widget project
		{ id: '17', shortId: 'mno1', names: ['/3d-widget-web-host-full-three-1'], image: 'node:20', state: 'running', status: 'Up 12 hours', labels: { 'com.docker.compose.project': '3d-widget-web-host' } },
		{ id: '18', shortId: 'mno2', names: ['/3d-widget-web-host-full-babylon-1'], image: 'node:20', state: 'running', status: 'Up 12 hours', labels: { 'com.docker.compose.project': '3d-widget-web-host' } },
		{ id: '19', shortId: 'mno3', names: ['/3d-widget-web-host-webhost-only-three-1'], image: 'node:20', state: 'running', status: 'Up 12 hours', labels: { 'com.docker.compose.project': '3d-widget-web-host' } },
		{ id: '20', shortId: 'mno4', names: ['/3d-widget-web-host-webhost-only-babylon-1'], image: 'node:20', state: 'running', status: 'Up 12 hours', labels: { 'com.docker.compose.project': '3d-widget-web-host' } },
		// coatervision project
		{ id: '21', shortId: 'pqr1', names: ['/coatervision-web-1'], image: 'node:20', state: 'running', status: 'Up 7 days', labels: { 'com.docker.compose.project': 'coatervision' } },
		{ id: '22', shortId: 'pqr2', names: ['/coatervision-api-1'], image: 'python:3.11', state: 'running', status: 'Up 7 days', labels: { 'com.docker.compose.project': 'coatervision' } },
		// release-notes project
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
		// Shorten: remove project prefix and trailing -1
		return name.replace(/^[a-z0-9]+-/, '').replace(/-1$/, '').replace(/_1$/, '');
	}

	function getNodeColor(container: Container): string {
		const project = projects.find(p => p.containers.some(c => c.id === container.id));
		return project?.color || '#888';
	}

	function getStateColor(state: string): string {
		switch (state) {
			case 'running': return '#00e676';  // bright green
			case 'exited': return '#ff1744';   // bright red
			case 'paused': return '#ff9100';   // orange
			default: return '#546e7a';         // grey
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

		// Create container nodes
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

		// Add hub node + links for every project
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

		// @ts-ignore - 3d-force-graph types are incompatible with dynamic import
		const ForceGraph3D = (await import('3d-force-graph')).default;
		const THREE = await import('three');

		const data = buildGraphData();

		// @ts-ignore
		graph = ForceGraph3D({
			extraRenderers: []
		})(graphContainer)
			.backgroundColor('#0a0e27')
			.width(graphContainer.clientWidth)
			.height(graphContainer.clientHeight)
			.graphData(data)
			// Force simulation - stabilize quickly then stop
			.cooldownTicks(100)
			.cooldownTime(3000)
			.d3AlphaDecay(0.05)
			.d3VelocityDecay(0.4)
			.warmupTicks(50)
			// Node rendering - glowing boxes
			.nodeThreeObject((node: any) => {
				if (!node) return new THREE.Object3D();

				const group = new THREE.Group();

				// ── Hub node (project center) ──
				if (node.isHub) {
					const hubSize = 5;
					// Icosahedron = gem-like sphere
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

					// Wireframe overlay
					const wireGeo = new THREE.IcosahedronGeometry(hubSize * 1.05, 1);
					const wireMat = new THREE.MeshBasicMaterial({
						color: new THREE.Color(node.color),
						transparent: true,
						opacity: 0.3,
						wireframe: true,
					});
					group.add(new THREE.Mesh(wireGeo, wireMat));

					// Outer glow
					const glowGeo = new THREE.IcosahedronGeometry(hubSize * 1.6, 1);
					const glowMat = new THREE.MeshBasicMaterial({
						color: new THREE.Color(node.color),
						transparent: true,
						opacity: 0.06,
						side: THREE.BackSide,
					});
					group.add(new THREE.Mesh(glowGeo, glowMat));

					// Hub label
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

				// ── Container node (box) ──
				const isRunning = node.state === 'running';
				const size = isRunning ? 6 : 4;
				const stateColor = getStateColor(node.state);

				// Main box
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

				// Wireframe overlay
				const wireGeo = new THREE.EdgesGeometry(geometry);
				const wireMat = new THREE.LineBasicMaterial({
					color: new THREE.Color(stateColor),
					transparent: true,
					opacity: isRunning ? 0.8 : 0.3,
				});
				group.add(new THREE.LineSegments(wireGeo, wireMat));

				// Outer glow for running
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

				// Text label with state dot
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
			// Link rendering - soft lines from hub to containers
			.linkColor((link: any) => {
				const project = projects.find(p => p.name === link.project);
				const c = project?.color || '#4fc3f7';
				return c + '40'; // 25% opacity hex
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
			// Force configuration
			.d3Force('charge', null)
			.d3Force('center', null)
			.onNodeHover((node: any) => {
				graphContainer.style.cursor = node ? 'pointer' : 'default';
			})
			.onNodeClick((node: any) => {
				if (!node) return;
				// Hub click or container click -> select that project
				if (node.project) {
					updateGraphForProject(
						selectedProject === node.project ? null : node.project
					);
				}
			})
			.onNodeDrag((node: any) => {
				// Keep simulation cool during drag to prevent jumps
				if (node) graph.d3ReheatSimulation();
				markHullDirty();
			})
			.onNodeDragEnd((node: any) => {
				// Fix node position after drag
				if (node) {
					node.fx = node.x;
					node.fy = node.y;
					node.fz = node.z;
				}
				// Re-enable orbit controls (can get stuck disabled after drag)
				const controls = graph.controls();
				if (controls) controls.enabled = true;
			})
			.enableNodeDrag(true)
			.onEngineTick(() => {
				// Mark hull for rebuild every simulation tick (real-time follow)
				markHullDirty();
			});

		// Add custom forces
		// @ts-ignore - d3-force-3d has no type declarations
		const d3 = await import('d3-force-3d');

		// Repulsion force
		graph.d3Force('charge', d3.forceManyBody().strength(-120));

		// Cluster force - pull nodes toward their project center when selected
		graph.d3Force('center', d3.forceCenter(0, 0, 0).strength(0.05));

		// Add bloom post-processing
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
				1.2,   // strength
				0.4,   // radius
				0.85   // threshold
			);
			composer.addPass(bloomPass);

			// Override render loop
			graph.postProcessingComposer(composer);
		} catch (e) {
			console.warn('Bloom post-processing not available:', e);
		}

		// Add ambient light
		const scene = graph.scene();
		const ambientLight = new THREE.AmbientLight(0x404060, 0.8);
		scene.add(ambientLight);
		const pointLight = new THREE.PointLight(0x4fc3f7, 1.5, 500);
		pointLight.position.set(0, 100, 0);
		scene.add(pointLight);

		// Add grid floor
		const gridHelper = new THREE.GridHelper(400, 40, 0x1a2a5e, 0x0d1a3a);
		gridHelper.position.y = -60;
		scene.add(gridHelper);

		// Reduce camera sensitivity
		const controls = graph.controls();
		if (controls) {
			controls.rotateSpeed = 1.2;
			controls.zoomSpeed = 0.6;
			controls.panSpeed = 0.05;
			controls.dynamicDampingFactor = 0.25;

			// Patch: wrap onPointerUp to prevent crash when pointer is untracked
			const origOnPointerUp = controls.onPointerUp?.bind(controls);
			if (origOnPointerUp) {
				controls.onPointerUp = function(event: any) {
					try { origOnPointerUp(event); } catch (_) { /* ignore untracked pointer */ }
				};
			}
		}

		graphInitialized = true;

		// Load hull deps and start hull updates for all projects from the beginning
		await ensureHullDeps();
		startHullUpdates();

		// When camera zooms out far, smoothly gather nodes back to center
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

			// Remove old hull for this project
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
				// Silently fail - hull is cosmetic
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

			// Release ALL fixed positions so every node can move
			graph.graphData().nodes.forEach((n: any) => {
				n.fx = undefined;
				n.fy = undefined;
				n.fz = undefined;
			});

			// Get current hub position as cluster center
			const hubNode = graph.graphData().nodes.find((n: any) => n.id === `hub-${projectName}`);
			const anchorX = hubNode?.x || 0;
			const anchorY = hubNode?.y || 0;
			const anchorZ = hubNode?.z || 0;

			// Immediately move camera toward hub position (instant response)
			const camDist = 150;
			graph.cameraPosition(
				{ x: anchorX + camDist * 0.55, y: anchorY + camDist * 0.35, z: anchorZ + camDist * 0.55 },
				{ x: anchorX, y: anchorY, z: anchorZ },
				1500
			);

			// Apply forces: selected gathers slowly, others scatter outward slowly
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

			// After nodes settle, refine camera to fit all project nodes precisely
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

				// Allow zoom-out detection after camera transition finishes
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

		// Release all fixed positions so force simulation can move them
		graph.graphData().nodes.forEach((n: any) => {
			n.fx = undefined;
			n.fy = undefined;
			n.fz = undefined;
		});

		// Remove scatter, slowly pull all nodes back toward center
		// @ts-ignore
		import('d3-force-3d').then(d3 => {
			graph.d3Force('scatter', null);
			graph.d3Force('cluster', d3.forceRadial(30, 0, 0, 0).strength(0.08));
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
			const response = await fetch('/api/containers');
			const result = await response.json();
			if (result.success) {
				containers = result.data;
				groupContainers(containers);
				lastUpdate = new Date();
				if (graph && graphInitialized) {
					// Update node states without resetting force simulation
					const currentNodes = graph.graphData().nodes;
					currentNodes.forEach((node: any) => {
						const updated = containers.find((c: Container) => c.id === node.id);
						if (updated) {
							node.state = updated.state;
							node.val = updated.state === 'running' ? 8 : 4;
						}
					});
					graph.nodeThreeObject(graph.nodeThreeObject()); // refresh visuals only
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
			const response = await fetch('/api/system');
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

	onMount(async () => {
		await fetchData();
		await fetchSystemInfoData();
		await initGraph();

		// Re-enable orbit controls when pointer leaves or drag ends unexpectedly
		if (graphContainer) {
			graphContainer.addEventListener('pointerleave', () => {
				const controls = graph?.controls();
				if (controls) controls.enabled = true;
			});
		}

		refreshInterval = setInterval(async () => {
			await fetchData();
			await fetchSystemInfoData();
		}, 10000);
	});

	onDestroy(() => {
		stopHullUpdates();
		if (refreshInterval) clearInterval(refreshInterval);
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
	<title>AGICS Container Monitor - 3D Demo</title>
</svelte:head>

<div class="layout">
	<!-- Left Panel: System Info -->
	<aside class="panel left-panel">
		<div class="panel-header">
			<h2>System</h2>
			<span class="update-time">{lastUpdate.toLocaleTimeString('ko-KR')}</span>
		</div>

		{#if systemInfo}
			<div class="info-section">
				<div class="info-label">Host</div>
				<div class="info-value">{systemInfo.hostname}</div>
			</div>
			<div class="info-section">
				<div class="info-label">OS</div>
				<div class="info-value small">{systemInfo.os}</div>
			</div>

			<div class="metric-card">
				<div class="metric-header">
					<span class="metric-label">CPU</span>
					<span class="metric-value">{systemInfo.cpu.usage.toFixed(1)}%</span>
				</div>
				<div class="metric-bar">
					<div class="metric-fill" style="width: {systemInfo.cpu.usage}%; background: {systemInfo.cpu.usage > 80 ? '#ef5350' : systemInfo.cpu.usage > 50 ? '#ffa726' : '#66bb6a'}"></div>
				</div>
				<div class="metric-detail">{systemInfo.cpu.cores} cores - {systemInfo.cpu.model}</div>
			</div>

			<div class="metric-card">
				<div class="metric-header">
					<span class="metric-label">Memory</span>
					<span class="metric-value">{systemInfo.memory.usage.toFixed(1)}%</span>
				</div>
				<div class="metric-bar">
					<div class="metric-fill" style="width: {systemInfo.memory.usage}%; background: {systemInfo.memory.usage > 80 ? '#ef5350' : systemInfo.memory.usage > 50 ? '#ffa726' : '#66bb6a'}"></div>
				</div>
				<div class="metric-detail">{systemInfo.memory.used} / {systemInfo.memory.total}</div>
			</div>

			<div class="metric-card">
				<div class="metric-header">
					<span class="metric-label">Disk</span>
					<span class="metric-value">{systemInfo.disk.usage.toFixed(1)}%</span>
				</div>
				<div class="metric-bar">
					<div class="metric-fill" style="width: {systemInfo.disk.usage}%; background: {systemInfo.disk.usage > 80 ? '#ef5350' : systemInfo.disk.usage > 50 ? '#ffa726' : '#66bb6a'}"></div>
				</div>
				<div class="metric-detail">{systemInfo.disk.used} / {systemInfo.disk.total}</div>
			</div>

			<div class="docker-info">
				<div class="info-label">Docker</div>
				<div class="docker-stats">
					<span>v{systemInfo.docker.version}</span>
					<span>{systemInfo.docker.containers} containers</span>
					<span>{systemInfo.docker.images} images</span>
				</div>
			</div>
		{:else}
			<div class="loading-text">Loading...</div>
		{/if}

		<!-- Container Stats Summary -->
		<div class="stats-summary">
			<div class="stat-item running">
				<span class="stat-count">{containers.filter(c => c.state === 'running').length}</span>
				<span class="stat-label">Running</span>
			</div>
			<div class="stat-item stopped">
				<span class="stat-count">{containers.filter(c => c.state === 'exited').length}</span>
				<span class="stat-label">Stopped</span>
			</div>
			<div class="stat-item total">
				<span class="stat-count">{containers.length}</span>
				<span class="stat-label">Total</span>
			</div>
		</div>
	</aside>

	<!-- Center: 3D Graph -->
	<main class="graph-area">
		<div class="graph-overlay-top">
			<h1>AGICS Container Monitor</h1>
			<p>3D Interactive Dashboard</p>
		</div>
		<div class="graph-container" bind:this={graphContainer}></div>
		<div class="graph-overlay-bottom">
			<span class="hint">Click a node to focus | Scroll to zoom | Drag to rotate</span>
			{#if selectedProject}
				<button class="reset-btn" on:click={() => updateGraphForProject(null)}>
					Reset View
				</button>
			{/if}
		</div>
	</main>

	<!-- Right Panel: Projects -->
	<aside class="panel right-panel">
		<div class="panel-header">
			<h2>Projects</h2>
			<span class="project-count">{projects.length}</span>
		</div>

		<div class="project-list">
			{#each projects as project}
				<button
					class="project-card {selectedProject === project.name ? 'selected' : ''}"
					on:click={() => updateGraphForProject(selectedProject === project.name ? null : project.name)}
				>
					<div class="project-header">
						<span class="project-dot" style="background: {project.color}"></span>
						<span class="project-name">{project.name}</span>
						<span class="project-badge">{project.stats.total}</span>
					</div>
					<div class="container-list">
						{#each project.containers as container}
							<div class="container-item">
								<span class="state-dot {container.state}"></span>
								<span class="container-name">{getContainerDisplayName(container)}</span>
							</div>
						{/each}
					</div>
					<div class="project-stats-bar">
						{#if project.stats.running > 0}
							<div class="bar-segment running" style="width: {(project.stats.running / project.stats.total) * 100}%"></div>
						{/if}
						{#if project.stats.stopped > 0}
							<div class="bar-segment stopped" style="width: {(project.stats.stopped / project.stats.total) * 100}%"></div>
						{/if}
						{#if project.stats.paused > 0}
							<div class="bar-segment paused" style="width: {(project.stats.paused / project.stats.total) * 100}%"></div>
						{/if}
					</div>
				</button>
			{/each}
		</div>
	</aside>
</div>

<style>
	:global(body) {
		margin: 0;
		padding: 0;
		overflow: hidden;
		background: #0a0e27;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
		color: #e0e6ed;
	}

	.layout {
		display: flex;
		height: 100vh;
		width: 100vw;
	}

	/* Panels */
	.panel {
		width: 280px;
		min-width: 280px;
		background: rgba(12, 16, 40, 0.95);
		border: 1px solid rgba(79, 195, 247, 0.1);
		padding: 16px;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.panel::-webkit-scrollbar {
		width: 4px;
	}

	.panel::-webkit-scrollbar-thumb {
		background: rgba(79, 195, 247, 0.3);
		border-radius: 2px;
	}

	.left-panel {
		border-right: 1px solid rgba(79, 195, 247, 0.15);
	}

	.right-panel {
		border-left: 1px solid rgba(79, 195, 247, 0.15);
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-bottom: 12px;
		border-bottom: 1px solid rgba(79, 195, 247, 0.15);
	}

	.panel-header h2 {
		font-size: 14px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 1.5px;
		color: #4fc3f7;
	}

	.update-time {
		font-size: 11px;
		color: #546e8a;
	}

	.project-count {
		background: rgba(79, 195, 247, 0.15);
		color: #4fc3f7;
		padding: 2px 8px;
		border-radius: 10px;
		font-size: 11px;
		font-weight: 600;
	}

	/* System Info */
	.info-section {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.info-label {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 1px;
		color: #546e8a;
	}

	.info-value {
		font-size: 13px;
		font-weight: 500;
		color: #b8c6db;
	}

	.info-value.small {
		font-size: 11px;
	}

	.metric-card {
		background: rgba(20, 28, 58, 0.6);
		border-radius: 8px;
		padding: 10px 12px;
		border: 1px solid rgba(79, 195, 247, 0.08);
	}

	.metric-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 6px;
	}

	.metric-label {
		font-size: 12px;
		font-weight: 600;
		color: #8899aa;
	}

	.metric-value {
		font-size: 14px;
		font-weight: 700;
		color: #e0e6ed;
	}

	.metric-bar {
		height: 4px;
		background: rgba(255, 255, 255, 0.06);
		border-radius: 2px;
		overflow: hidden;
		margin-bottom: 4px;
	}

	.metric-fill {
		height: 100%;
		border-radius: 2px;
		transition: width 0.5s ease;
	}

	.metric-detail {
		font-size: 10px;
		color: #546e8a;
	}

	.docker-info {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.docker-stats {
		display: flex;
		gap: 8px;
		font-size: 11px;
		color: #6e8098;
	}

	.stats-summary {
		display: flex;
		gap: 8px;
		margin-top: auto;
		padding-top: 12px;
		border-top: 1px solid rgba(79, 195, 247, 0.1);
	}

	.stat-item {
		flex: 1;
		text-align: center;
		padding: 8px 4px;
		border-radius: 6px;
		background: rgba(20, 28, 58, 0.6);
	}

	.stat-count {
		display: block;
		font-size: 18px;
		font-weight: 700;
	}

	.stat-label {
		display: block;
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: #546e8a;
		margin-top: 2px;
	}

	.stat-item.running .stat-count { color: #66bb6a; }
	.stat-item.stopped .stat-count { color: #ef5350; }
	.stat-item.total .stat-count { color: #4fc3f7; }

	.loading-text {
		color: #546e8a;
		font-size: 12px;
		text-align: center;
		padding: 20px;
	}

	/* 3D Graph Area */
	.graph-area {
		flex: 1;
		position: relative;
		overflow: hidden;
	}

	.graph-container {
		width: 100%;
		height: 100%;
	}

	.graph-overlay-top {
		position: absolute;
		top: 16px;
		left: 50%;
		transform: translateX(-50%);
		text-align: center;
		z-index: 10;
		pointer-events: none;
	}

	.graph-overlay-top h1 {
		font-size: 16px;
		font-weight: 600;
		color: rgba(224, 230, 237, 0.7);
		letter-spacing: 2px;
		text-transform: uppercase;
	}

	.graph-overlay-top p {
		font-size: 11px;
		color: rgba(79, 195, 247, 0.5);
		letter-spacing: 1px;
	}

	.graph-overlay-bottom {
		position: absolute;
		bottom: 16px;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		align-items: center;
		gap: 16px;
		z-index: 10;
	}

	.hint {
		font-size: 11px;
		color: rgba(134, 158, 182, 0.5);
		letter-spacing: 0.5px;
	}

	.reset-btn {
		background: rgba(79, 195, 247, 0.15);
		border: 1px solid rgba(79, 195, 247, 0.3);
		color: #4fc3f7;
		padding: 6px 16px;
		border-radius: 4px;
		font-size: 11px;
		cursor: pointer;
		transition: all 0.2s;
	}

	.reset-btn:hover {
		background: rgba(79, 195, 247, 0.25);
	}

	/* Project List */
	.project-list {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.project-card {
		width: 100%;
		text-align: left;
		background: rgba(20, 28, 58, 0.4);
		border: 1px solid rgba(79, 195, 247, 0.06);
		border-radius: 8px;
		padding: 10px 12px;
		cursor: pointer;
		transition: all 0.25s ease;
		color: inherit;
		font-family: inherit;
	}

	.project-card:hover {
		background: rgba(20, 28, 58, 0.7);
		border-color: rgba(79, 195, 247, 0.2);
	}

	.project-card.selected {
		background: rgba(79, 195, 247, 0.08);
		border-color: rgba(79, 195, 247, 0.4);
		box-shadow: 0 0 20px rgba(79, 195, 247, 0.1);
	}

	.project-header {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 6px;
	}

	.project-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.project-name {
		font-size: 12px;
		font-weight: 600;
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.project-badge {
		background: rgba(255, 255, 255, 0.06);
		padding: 1px 6px;
		border-radius: 8px;
		font-size: 10px;
		color: #6e8098;
	}

	.container-list {
		display: flex;
		flex-direction: column;
		gap: 3px;
		margin-bottom: 6px;
	}

	.container-item {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 2px 0;
	}

	.state-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.state-dot.running { background: #66bb6a; box-shadow: 0 0 4px #66bb6a; }
	.state-dot.exited { background: #ef5350; }
	.state-dot.paused { background: #ffa726; }
	.state-dot.created { background: #29b6f6; }

	.container-name {
		font-size: 11px;
		color: #8899aa;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.project-stats-bar {
		height: 3px;
		border-radius: 2px;
		background: rgba(255, 255, 255, 0.04);
		display: flex;
		overflow: hidden;
	}

	.bar-segment {
		height: 100%;
		transition: width 0.3s ease;
	}

	.bar-segment.running { background: #66bb6a; }
	.bar-segment.stopped { background: #ef5350; }
	.bar-segment.paused { background: #ffa726; }
</style>
