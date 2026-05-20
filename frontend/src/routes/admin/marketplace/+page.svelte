<script lang="ts">
	type CategoryKey = 'llm' | 'multimodal' | 'mcp' | 'media' | 'voice';
	type ServiceStatus = 'connected' | 'available' | 'beta';
	type Source = 'official' | 'community';
	type SortKey = 'name' | 'category' | 'connection' | 'status';

	interface Service {
		id: string;
		name: string;
		vendor: string;
		category: CategoryKey;
		connection: string;
		status: ServiceStatus;
		source: Source;
		summary: string;
		description: string;
		steps: string[];
		command?: string;
		tags: string[];
		docsUrl: string;
		consoleUrl: string;
		consoleLabel: string;
	}

	const CATEGORIES: Record<CategoryKey, { label: string; tint: string }> = {
		llm: { label: 'LLM', tint: '#4dbfb3' },
		multimodal: { label: '멀티모달', tint: '#a78bfa' },
		mcp: { label: 'MCP 커넥터', tint: '#60a5fa' },
		media: { label: '이미지·영상', tint: '#f6b352' },
		voice: { label: '음성', tint: '#f472b6' },
	};
	const CATEGORY_ORDER: CategoryKey[] = ['llm', 'multimodal', 'mcp', 'media', 'voice'];

	const STATUS_META: Record<ServiceStatus, { label: string; color: string }> = {
		connected: { label: '연결됨', color: '#34d399' },
		available: { label: '연동 가능', color: '#60a5fa' },
		beta: { label: '베타', color: '#f6b352' },
	};
	const STATUS_ORDER: ServiceStatus[] = ['connected', 'available', 'beta'];

	// 더미 데이터 — 실제 운용 전 컨셉 시연용.
	//  · official  : 외부 공급사 카탈로그
	//  · community : 사용자가 컨테이너에 AI 를 올리고 직접 등록한 시스템
	const SERVICES: Service[] = [
		{
			id: 'openai-gpt',
			name: 'GPT-4o',
			vendor: 'OpenAI',
			category: 'llm',
			connection: 'API Key',
			status: 'connected',
			source: 'official',
			summary: '범용 대화형 LLM. 코드 생성·문서 요약·데이터 분석 전반.',
			description:
				'OpenAI 의 플래그십 멀티모달 모델. 워크스페이스에서 텍스트·이미지 입력을 받아 코드, 분석 리포트, 운영 자동화 스크립트를 생성합니다.',
			steps: [
				'OpenAI 플랫폼 콘솔에서 API Key 발급',
				'마켓플레이스 > 연결 화면에 키와 사용량 한도 입력',
				'워크스페이스 환경변수로 키 주입 (OPENAI_API_KEY)',
				'컨테이너 내 SDK 또는 HTTP 호출로 사용',
			],
			command: 'export OPENAI_API_KEY=sk-...\npip install openai',
			tags: ['텍스트', '함수 호출', '128K 컨텍스트'],
			docsUrl: 'https://platform.openai.com/docs',
			consoleUrl: 'https://platform.openai.com/api-keys',
			consoleLabel: 'API Key 콘솔',
		},
		{
			id: 'anthropic-claude',
			name: 'Claude Opus 4',
			vendor: 'Anthropic',
			category: 'llm',
			connection: 'API Key',
			status: 'available',
			source: 'official',
			summary: '장문 추론·코드 리뷰에 강한 LLM. 긴 컨텍스트 처리.',
			description:
				'Anthropic Claude 계열 모델. 대규모 코드베이스 리뷰, 운영 로그 분석, 에이전트 워크플로 오케스트레이션에 적합합니다.',
			steps: [
				'Anthropic 콘솔에서 API Key 발급',
				'마켓플레이스 연결 화면에 키 등록',
				'워크스페이스 환경변수 주입 (ANTHROPIC_API_KEY)',
				'Messages API 로 호출',
			],
			command: 'export ANTHROPIC_API_KEY=sk-ant-...\npip install anthropic',
			tags: ['텍스트', '200K 컨텍스트', '에이전트'],
			docsUrl: 'https://docs.anthropic.com',
			consoleUrl: 'https://console.anthropic.com/settings/keys',
			consoleLabel: 'API Key 콘솔',
		},
		{
			id: 'google-gemini',
			name: 'Gemini 2.0',
			vendor: 'Google',
			category: 'multimodal',
			connection: 'API Key',
			status: 'available',
			source: 'official',
			summary: '텍스트·이미지·영상·오디오를 한 모델에서 처리.',
			description:
				'Google 의 네이티브 멀티모달 모델. 영상 프레임 분석, 차트 OCR, 멀티모달 RAG 파이프라인에 활용합니다.',
			steps: [
				'Google AI Studio 에서 API Key 발급',
				'마켓플레이스 연결 화면에 키 등록',
				'워크스페이스 환경변수 주입 (GEMINI_API_KEY)',
				'generateContent 엔드포인트로 호출',
			],
			tags: ['멀티모달', '영상 입력', '1M 컨텍스트'],
			docsUrl: 'https://ai.google.dev/docs',
			consoleUrl: 'https://aistudio.google.com/app/apikey',
			consoleLabel: 'AI Studio',
		},
		{
			id: 'llama-selfhost',
			name: 'Llama 3 (Self-host)',
			vendor: 'Meta',
			category: 'llm',
			connection: 'Endpoint URL',
			status: 'available',
			source: 'official',
			summary: '온프레미스 GPU 서버에 직접 띄우는 오픈 LLM.',
			description:
				'사내 GPU 노드에 vLLM/Ollama 로 서빙하는 오픈웨이트 모델. 데이터를 외부로 보내지 않아 보안 등급이 높은 워크로드에 적합합니다.',
			steps: [
				'GPU 서버에 vLLM 또는 Ollama 로 모델 서빙',
				'OpenAI 호환 엔드포인트 URL 확인',
				'마켓플레이스 연결 화면에 엔드포인트 등록',
				'워크스페이스에서 base_url 지정 후 호출',
			],
			command: 'ollama run llama3\n# http://gpu-node:11434/v1',
			tags: ['온프레미스', '오픈웨이트', 'GPU'],
			docsUrl: 'https://docs.vllm.ai',
			consoleUrl: 'https://ollama.com/library/llama3',
			consoleLabel: '모델 카탈로그',
		},
		{
			id: 'dalle',
			name: 'DALL·E 3',
			vendor: 'OpenAI',
			category: 'media',
			connection: 'API Key',
			status: 'available',
			source: 'official',
			summary: '프롬프트 기반 고해상도 이미지 생성.',
			description:
				'텍스트 프롬프트로 마케팅 에셋, 다이어그램 초안, UI 목업 이미지를 생성합니다. OpenAI API Key 를 공유해 사용합니다.',
			steps: [
				'OpenAI API Key 발급 (GPT-4o 와 공유 가능)',
				'마켓플레이스 연결 화면에서 이미지 권한 활성화',
				'images/generations 엔드포인트 호출',
				'생성 결과를 워크스페이스 스토리지에 저장',
			],
			tags: ['이미지 생성', '1024px+', '프롬프트'],
			docsUrl: 'https://platform.openai.com/docs/guides/images',
			consoleUrl: 'https://platform.openai.com/api-keys',
			consoleLabel: 'API Key 콘솔',
		},
		{
			id: 'runway',
			name: 'Runway Gen-3',
			vendor: 'Runway',
			category: 'media',
			connection: 'API Key',
			status: 'beta',
			source: 'official',
			summary: '텍스트·이미지에서 짧은 영상 클립 생성.',
			description:
				'프롬프트 또는 시드 이미지로 수 초 길이의 영상을 생성합니다. 베타 단계로, 워크스페이스당 호출 쿼터가 제한됩니다.',
			steps: [
				'Runway 콘솔에서 API 액세스 신청',
				'발급된 키를 마켓플레이스에 등록',
				'영상 생성 작업(job) 비동기 제출',
				'완료 웹훅 수신 후 결과 다운로드',
			],
			tags: ['영상 생성', '비동기 잡', '베타 쿼터'],
			docsUrl: 'https://docs.dev.runwayml.com',
			consoleUrl: 'https://app.runwayml.com',
			consoleLabel: 'Runway 콘솔',
		},
		{
			id: 'whisper',
			name: 'Whisper',
			vendor: 'OpenAI',
			category: 'voice',
			connection: 'API Key',
			status: 'available',
			source: 'official',
			summary: '음성 파일을 텍스트로 변환 (STT).',
			description:
				'회의 녹음, 운영 콜 로그 등을 텍스트로 전사합니다. 다국어 인식과 타임스탬프 분할을 지원합니다.',
			steps: [
				'OpenAI API Key 발급',
				'마켓플레이스 연결 화면에서 음성 권한 활성화',
				'audio/transcriptions 엔드포인트로 파일 업로드',
				'전사 결과를 워크스페이스에 저장',
			],
			tags: ['STT', '다국어', '타임스탬프'],
			docsUrl: 'https://platform.openai.com/docs/guides/speech-to-text',
			consoleUrl: 'https://platform.openai.com/api-keys',
			consoleLabel: 'API Key 콘솔',
		},
		{
			id: 'mcp-blender',
			name: 'Blender MCP',
			vendor: 'Community',
			category: 'mcp',
			connection: 'MCP Server',
			status: 'available',
			source: 'official',
			summary: 'AI 가 Blender 씬을 직접 조작하는 MCP 커넥터.',
			description:
				'Model Context Protocol 서버로, LLM 이 Blender 의 오브젝트 생성·렌더링·머티리얼 편집을 도구 호출로 수행합니다. 3D 에셋 자동 생성 워크플로에 사용합니다.',
			steps: [
				'워크스페이스 노드에 Blender + MCP 애드온 설치',
				'MCP 서버를 npx 로 기동',
				'에이전트 mcp.json 에 blender 서버 등록',
				'LLM 워크플로에서 도구 호출로 씬 제어',
			],
			command: 'npx blender-mcp\n# mcp.json: { "blender": { "command": "npx", "args": ["blender-mcp"] } }',
			tags: ['MCP', '3D', '도구 호출'],
			docsUrl: 'https://modelcontextprotocol.io/docs',
			consoleUrl: 'https://github.com/ahujasid/blender-mcp',
			consoleLabel: 'GitHub 저장소',
		},
		{
			id: 'mcp-figma',
			name: 'Figma MCP',
			vendor: 'Figma',
			category: 'mcp',
			connection: 'MCP Server',
			status: 'connected',
			source: 'official',
			summary: '디자인 파일을 읽어 코드·토큰으로 변환하는 커넥터.',
			description:
				'Figma 파일의 프레임·컴포넌트·디자인 토큰을 MCP 도구로 노출합니다. 디자인-투-코드 파이프라인에서 LLM 이 디자인 스펙을 직접 참조합니다.',
			steps: [
				'Figma 개인 액세스 토큰 발급',
				'Figma MCP 서버를 npx 로 기동',
				'에이전트 mcp.json 에 figma 서버 등록',
				'파일 키를 전달해 프레임/토큰 조회',
			],
			command: 'npx figma-developer-mcp --figma-api-key=...',
			tags: ['MCP', '디자인', '토큰 추출'],
			docsUrl: 'https://modelcontextprotocol.io/docs',
			consoleUrl: 'https://www.figma.com/developers/api',
			consoleLabel: 'Figma 개발자',
		},
		{
			id: 'mcp-github',
			name: 'GitHub MCP',
			vendor: 'GitHub',
			category: 'mcp',
			connection: 'MCP Server',
			status: 'available',
			source: 'official',
			summary: '저장소·이슈·PR 을 도구로 노출하는 커넥터.',
			description:
				'GitHub 저장소의 코드 검색, 이슈/PR 생성, 커밋 조회를 MCP 도구로 제공합니다. 코드 리뷰 자동화와 릴리스 워크플로에 활용합니다.',
			steps: [
				'GitHub PAT(Personal Access Token) 발급',
				'GitHub MCP 서버 기동',
				'에이전트 mcp.json 에 github 서버 등록',
				'LLM 워크플로에서 이슈/PR 도구 호출',
			],
			command: 'npx @modelcontextprotocol/server-github',
			tags: ['MCP', '저장소', 'PR 자동화'],
			docsUrl: 'https://modelcontextprotocol.io/docs',
			consoleUrl: 'https://github.com/settings/tokens',
			consoleLabel: '토큰 발급',
		},
		{
			id: 'mcp-notion',
			name: 'Notion MCP',
			vendor: 'Notion',
			category: 'mcp',
			connection: 'MCP Server',
			status: 'available',
			source: 'official',
			summary: '문서·DB 를 읽고 쓰는 지식베이스 커넥터.',
			description:
				'Notion 워크스페이스의 페이지와 데이터베이스를 MCP 도구로 노출합니다. 운영 런북 검색, 회의록 자동 정리에 사용합니다.',
			steps: [
				'Notion 인티그레이션 생성 후 시크릿 발급',
				'대상 페이지에 인티그레이션 연결',
				'Notion MCP 서버 기동 및 mcp.json 등록',
				'LLM 워크플로에서 페이지/DB 도구 호출',
			],
			command: 'npx @notionhq/notion-mcp-server',
			tags: ['MCP', '지식베이스', '문서 동기화'],
			docsUrl: 'https://modelcontextprotocol.io/docs',
			consoleUrl: 'https://www.notion.so/my-integrations',
			consoleLabel: '인티그레이션',
		},

		/* ── 커뮤니티 등록: 사용자가 컨테이너에 직접 올린 AI ── */
		{
			id: 'comm-wiki-rag',
			name: '사내 위키 RAG 봇',
			vendor: '김도현 · 데이터플랫폼팀',
			category: 'llm',
			connection: 'Endpoint URL',
			status: 'connected',
			source: 'community',
			summary: '사내 위키·런북을 학습한 검색형 챗봇. 출처 문서와 함께 답변.',
			description:
				'HyperCube 컨테이너에 배포된 RAG 파이프라인. pgvector 임베딩과 사내 위키 인덱스를 사용하며 OpenAI 호환 엔드포인트로 노출됩니다. 배포자가 직접 마켓플레이스에 등록했습니다.',
			steps: [
				'배포자가 컨테이너에 모델을 올리고 마켓플레이스에 등록',
				'노출된 엔드포인트 URL과 액세스 토큰 확인',
				'워크스페이스 환경변수에 엔드포인트 주입',
				'OpenAI 호환 클라이언트로 호출',
			],
			command: '# OpenAI 호환 엔드포인트\nbase_url=http://hc-wiki-rag.workspace:8080/v1',
			tags: ['RAG', '사내문서', '컨테이너 배포'],
			docsUrl: 'https://hypercube.example/guide/wiki-rag',
			consoleUrl: 'https://hypercube.example/workspace/hc-wiki-rag',
			consoleLabel: '엔드포인트 열기',
		},
		{
			id: 'comm-defect-vision',
			name: '라인 결함 비전 분류기',
			vendor: '이수민 · 품질기술팀',
			category: 'multimodal',
			connection: 'Endpoint URL',
			status: 'available',
			source: 'community',
			summary: '제조 라인 불량 이미지를 판별하는 비전 모델. 결함 유형까지 분류.',
			description:
				'생산 라인 카메라 이미지를 입력받아 정상/불량과 결함 유형을 반환합니다. GPU 컨테이너에 배포돼 REST 엔드포인트로 호출합니다.',
			steps: [
				'배포자가 GPU 컨테이너에 비전 모델 배포',
				'추론 엔드포인트 URL과 토큰 발급',
				'마켓플레이스 연결 화면에 엔드포인트 등록',
				'이미지 multipart 업로드로 추론 호출',
			],
			command: 'curl -F image=@frame.jpg \\\n  http://hc-defect-cv.workspace:9000/predict',
			tags: ['비전', '품질검사', '컨테이너 배포'],
			docsUrl: 'https://hypercube.example/guide/defect-vision',
			consoleUrl: 'https://hypercube.example/workspace/hc-defect-cv',
			consoleLabel: '엔드포인트 열기',
		},
		{
			id: 'comm-meeting-sum',
			name: '회의록 요약 파이프라인',
			vendor: '박지훈 · HR기술팀',
			category: 'voice',
			connection: 'Endpoint URL',
			status: 'available',
			source: 'community',
			summary: '회의 녹음을 전사하고 핵심 안건·액션아이템을 요약.',
			description:
				'STT 와 요약 LLM 을 묶은 파이프라인. 오디오 파일을 올리면 전사문, 안건별 요약, 액션아이템 목록을 반환합니다. 컨테이너에 배포돼 운영 중입니다.',
			steps: [
				'배포자가 컨테이너에 STT+요약 파이프라인 배포',
				'잡 제출 엔드포인트 URL 확인',
				'마켓플레이스 연결 화면에 엔드포인트 등록',
				'오디오 업로드 후 잡 완료 시 결과 수신',
			],
			tags: ['STT', '요약', '컨테이너 배포'],
			docsUrl: 'https://hypercube.example/guide/meeting-sum',
			consoleUrl: 'https://hypercube.example/workspace/hc-meeting-sum',
			consoleLabel: '엔드포인트 열기',
		},
		{
			id: 'comm-code-review',
			name: '코드 컨벤션 리뷰 에이전트',
			vendor: '정민재 · 플랫폼개발팀',
			category: 'llm',
			connection: 'MCP Server',
			status: 'beta',
			source: 'community',
			summary: '사내 코드 컨벤션을 학습한 PR 리뷰 봇. MCP 도구로 노출.',
			description:
				'사내 스타일 가이드를 학습한 리뷰 에이전트를 MCP 서버로 패키징했습니다. LLM 워크플로에서 diff 를 전달하면 컨벤션 위반과 개선 제안을 반환합니다. 베타 단계입니다.',
			steps: [
				'배포자가 리뷰 에이전트를 MCP 서버로 컨테이너에 배포',
				'MCP 서버 주소를 마켓플레이스에 등록',
				'에이전트 mcp.json 에 code-review 서버 추가',
				'워크플로에서 diff 전달해 리뷰 도구 호출',
			],
			command: '# mcp.json\n"code-review": { "url": "http://hc-code-review.workspace:7400/mcp" }',
			tags: ['MCP', '코드리뷰', '컨테이너 배포'],
			docsUrl: 'https://hypercube.example/guide/code-review',
			consoleUrl: 'https://hypercube.example/workspace/hc-code-review',
			consoleLabel: 'MCP 서버 정보',
		},
		{
			id: 'comm-3d-mockup',
			name: '제품 3D 목업 생성기',
			vendor: '최유나 · 디자인시스템팀',
			category: 'media',
			connection: 'MCP Server',
			status: 'available',
			source: 'community',
			summary: '텍스트 설명으로 제품 3D 목업을 생성. Blender 렌더 연동.',
			description:
				'프롬프트를 받아 Blender 로 제품 목업을 생성·렌더링하는 파이프라인을 MCP 서버로 노출했습니다. 컨테이너의 GPU 렌더 노드를 사용합니다.',
			steps: [
				'배포자가 Blender 렌더 파이프라인을 컨테이너에 배포',
				'MCP 서버 주소를 마켓플레이스에 등록',
				'에이전트 mcp.json 에 mockup-3d 서버 추가',
				'프롬프트 전달해 3D 목업 생성 도구 호출',
			],
			command: '# mcp.json\n"mockup-3d": { "url": "http://hc-mockup-3d.workspace:7600/mcp" }',
			tags: ['MCP', '3D', '컨테이너 배포'],
			docsUrl: 'https://hypercube.example/guide/mockup-3d',
			consoleUrl: 'https://hypercube.example/workspace/hc-mockup-3d',
			consoleLabel: 'MCP 서버 정보',
		},
	];

	const ALL_CONNECTIONS = [...new Set(SERVICES.map((s) => s.connection))].sort();
	const ALL_TAGS = [...new Set(SERVICES.flatMap((s) => s.tags))].sort((a, b) =>
		a.localeCompare(b, 'ko'),
	);

	// 검색 + 드롭다운 필터 + 정렬
	let search = $state('');
	let fCategory = $state<'all' | CategoryKey>('all');
	let fConnection = $state<string>('all');
	let fTag = $state<string>('all');
	let fStatus = $state<'all' | ServiceStatus>('all');
	let sortKey = $state<SortKey | null>(null);
	let sortDir = $state<'asc' | 'desc'>('asc');
	let expandedId = $state<string | null>(null);

	const hasFilter = $derived(
		!!search.trim() ||
			fCategory !== 'all' ||
			fConnection !== 'all' ||
			fTag !== 'all' ||
			fStatus !== 'all' ||
			sortKey !== null,
	);

	const filtered = $derived(
		SERVICES.filter((s) => {
			const q = search.trim().toLowerCase();
			if (q) {
				const haystack =
					`${s.name} ${s.vendor} ${s.summary} ${s.description} ${s.tags.join(' ')}`.toLowerCase();
				if (!haystack.includes(q)) return false;
			}
			if (fCategory !== 'all' && s.category !== fCategory) return false;
			if (fConnection !== 'all' && s.connection !== fConnection) return false;
			if (fTag !== 'all' && !s.tags.includes(fTag)) return false;
			if (fStatus !== 'all' && s.status !== fStatus) return false;
			return true;
		}),
	);

	const rows = $derived.by(() => {
		const arr = [...filtered];
		if (!sortKey) return arr;
		const dir = sortDir === 'asc' ? 1 : -1;
		arr.sort((a, b) => {
			if (sortKey === 'name') return a.name.localeCompare(b.name, 'ko') * dir;
			if (sortKey === 'connection') return a.connection.localeCompare(b.connection) * dir;
			if (sortKey === 'category')
				return (CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category)) * dir;
			return (STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status)) * dir;
		});
		return arr;
	});

	const stats = $derived({
		total: SERVICES.length,
		official: SERVICES.filter((s) => s.source === 'official').length,
		community: SERVICES.filter((s) => s.source === 'community').length,
		connected: SERVICES.filter((s) => s.status === 'connected').length,
	});

	// 카테고리 분포 — 균등 KPI 카드 대신 실제 구성을 보여주는 바 차트용
	const categoryDist = $derived(
		CATEGORY_ORDER.map((key) => ({
			key,
			label: CATEGORIES[key].label,
			tint: CATEGORIES[key].tint,
			count: SERVICES.filter((s) => s.category === key).length,
		})),
	);
	const maxCatCount = $derived(Math.max(1, ...categoryDist.map((c) => c.count)));

	function toggle(id: string) {
		expandedId = expandedId === id ? null : id;
	}

	function onRowKey(e: KeyboardEvent, id: string) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			toggle(id);
		}
	}

	function sortBy(key: SortKey) {
		if (sortKey === key) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortKey = key;
			sortDir = 'asc';
		}
	}

	function resetFilters() {
		search = '';
		fCategory = 'all';
		fConnection = 'all';
		fTag = 'all';
		fStatus = 'all';
		sortKey = null;
		sortDir = 'asc';
	}
</script>

<svelte:head>
	<title>마켓플레이스 - HyperCube</title>
</svelte:head>

<!-- 카테고리 아이콘 — 좌측 타일에 들어가 행의 종류를 한눈에 보이게 함 -->
{#snippet catIcon(key: CategoryKey)}
	{#if key === 'llm'}
		<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
	{:else if key === 'multimodal'}
		<path d="M12 2 2 7l10 5 10-5-10-5z" /><path d="m2 17 10 5 10-5" /><path d="m2 12 10 5 10-5" />
	{:else if key === 'mcp'}
		<circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
		<line x1="8.6" y1="13.5" x2="15.4" y2="17.5" /><line x1="15.4" y1="6.5" x2="8.6" y2="10.5" />
	{:else if key === 'media'}
		<rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.6" />
		<path d="m21 15-5-5L5 21" />
	{:else}
		<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
		<path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" />
	{/if}
{/snippet}

<div class="page">
	<div class="shell">
		<header class="page-header">
			<div>
				<h1>마켓플레이스</h1>
				<p class="subtitle">
					워크스페이스에서 연결해 사용할 수 있는 AI 시스템 카탈로그입니다. 외부 공급사 서비스와, 사용자가
					컨테이너에 직접 올려 등록한 시스템을 함께 제공합니다.
				</p>
			</div>
			<span class="preview-tag">컨셉 미리보기 · 더미 데이터</span>
		</header>

		<section class="summary">
			<div class="sum-totals">
				<span class="sum-cap">등록된 AI 시스템</span>
				<div class="sum-total">
					<strong>{stats.total}</strong><span>개</span>
				</div>
				<div
					class="src-bar"
					role="img"
					aria-label="공식 {stats.official}개, 커뮤니티 {stats.community}개"
				>
					<span class="src-seg" style="--c:#4dbfb3; flex:{stats.official}"></span>
					<span class="src-seg" style="--c:#a78bfa; flex:{stats.community}"></span>
				</div>
				<ul class="sum-breakdown">
					<li>
						<span class="sum-dot" style="--c:#4dbfb3"></span>
						<span class="sum-name">공식 카탈로그</span>
						<b>{stats.official}</b>
					</li>
					<li>
						<span class="sum-dot" style="--c:#a78bfa"></span>
						<span class="sum-name">커뮤니티 등록</span>
						<b>{stats.community}</b>
					</li>
					<li>
						<span class="sum-dot" style="--c:#34d399"></span>
						<span class="sum-name">연결됨</span>
						<b>{stats.connected}</b>
					</li>
				</ul>
			</div>

			<div class="sum-div" aria-hidden="true"></div>

			<div class="sum-dist">
				<div class="sum-dist-head">
					<span class="sum-cap">카테고리 분포</span>
					<span class="sum-dist-note">{categoryDist.length}개 분야 · 총 {stats.total}개</span>
				</div>
				<ul class="dist-rows">
					{#each categoryDist as c (c.key)}
						<li class="dist-row">
							<span class="dist-row-label">
								<span class="sum-dot" style="--c:{c.tint}"></span>{c.label}
							</span>
							<span class="dist-row-track">
								<span
									class="dist-row-fill"
									style="--c:{c.tint}; width:{(c.count / maxCatCount) * 100}%"
								></span>
							</span>
							<span class="dist-row-val">{c.count}</span>
						</li>
					{/each}
				</ul>
			</div>
		</section>

		<div class="toolbar">
			<div class="search-box">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
				</svg>
				<input type="search" placeholder="시스템 명, 설명, 태그로 검색" bind:value={search} />
			</div>
			<div class="filters">
				<label class="select-wrap">
					<span class="select-cap">카테고리</span>
					<select bind:value={fCategory}>
						<option value="all">전체</option>
						{#each Object.entries(CATEGORIES) as [key, c] (key)}
							<option value={key}>{c.label}</option>
						{/each}
					</select>
				</label>
				<label class="select-wrap">
					<span class="select-cap">연동 방식</span>
					<select bind:value={fConnection}>
						<option value="all">전체</option>
						{#each ALL_CONNECTIONS as conn (conn)}
							<option value={conn}>{conn}</option>
						{/each}
					</select>
				</label>
				<label class="select-wrap">
					<span class="select-cap">태그</span>
					<select bind:value={fTag}>
						<option value="all">전체</option>
						{#each ALL_TAGS as tag (tag)}
							<option value={tag}>{tag}</option>
						{/each}
					</select>
				</label>
				<label class="select-wrap">
					<span class="select-cap">상태</span>
					<select bind:value={fStatus}>
						<option value="all">전체</option>
						{#each Object.entries(STATUS_META) as [key, s] (key)}
							<option value={key}>{s.label}</option>
						{/each}
					</select>
				</label>
				<button type="button" class="reset-btn" onclick={resetFilters} disabled={!hasFilter}>
					초기화
				</button>
			</div>
		</div>

		<p class="result-line">
			전체 <b>{SERVICES.length}</b>개 중 <b>{rows.length}</b>개 표시
		</p>

		<div class="table-card">
			<table>
				<thead>
					<tr>
						<th class="col-name">
							<button type="button" class="sort-th" class:on={sortKey === 'name'} onclick={() => sortBy('name')}>
								시스템 명
								<span class="sort-ico">{sortKey === 'name' ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}</span>
							</button>
						</th>
						<th class="col-desc">시스템 설명</th>
						<th class="col-cat">
							<button type="button" class="sort-th" class:on={sortKey === 'category'} onclick={() => sortBy('category')}>
								카테고리
								<span class="sort-ico">{sortKey === 'category' ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}</span>
							</button>
						</th>
						<th class="col-conn">
							<button type="button" class="sort-th" class:on={sortKey === 'connection'} onclick={() => sortBy('connection')}>
								연동 방식
								<span class="sort-ico">{sortKey === 'connection' ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}</span>
							</button>
						</th>
						<th class="col-tags">태그</th>
						<th class="col-status">
							<button type="button" class="sort-th" class:on={sortKey === 'status'} onclick={() => sortBy('status')}>
								상태
								<span class="sort-ico">{sortKey === 'status' ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}</span>
							</button>
						</th>
						<th class="col-chev" aria-label="펼치기"></th>
					</tr>
				</thead>
				<tbody>
					{#each rows as svc (svc.id)}
						{@const cat = CATEGORIES[svc.category]}
						{@const st = STATUS_META[svc.status]}
						<tr
						class="svc-row"
						class:expanded={expandedId === svc.id}
						tabindex="0"
						aria-expanded={expandedId === svc.id}
						onclick={() => toggle(svc.id)}
						onkeydown={(e) => onRowKey(e, svc.id)}
					>
							<td class="col-name">
								<div class="svc-cell">
									<span class="svc-logo" style="--tint:{cat.tint}">
										<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
											{@render catIcon(svc.category)}
										</svg>
									</span>
									<span class="svc-meta">
										<span class="svc-name-row">
											<span class="svc-name">{svc.name}</span>
											<span class="src-badge {svc.source}">
												{svc.source === 'official' ? '공식' : '커뮤니티'}
											</span>
										</span>
										<span class="svc-vendor">{svc.vendor}</span>
									</span>
								</div>
							</td>
							<td class="col-desc"><p class="svc-desc">{svc.summary}</p></td>
							<td class="col-cat">
								<span class="chip" style="--tint:{cat.tint}">{cat.label}</span>
							</td>
							<td class="col-conn"><span class="conn">{svc.connection}</span></td>
							<td class="col-tags">
								<div class="tag-row">
									{#each svc.tags as t (t)}
										<span class="tag">{t}</span>
									{/each}
								</div>
							</td>
							<td class="col-status">
								<span class="status" style="--c:{st.color}">
									<span class="dot"></span>{st.label}
								</span>
							</td>
							<td class="col-chev">
								<span class="chev" class:open={expandedId === svc.id}>⌄</span>
							</td>
						</tr>
						{#if expandedId === svc.id}
							<tr class="detail-row">
								<td colspan="7">
									<div class="detail">
										<div class="detail-grid">
											<div class="detail-info">
												<div class="info-block">
													<span class="info-label">한 줄 요약</span>
													<p class="detail-summary">{svc.summary}</p>
												</div>
												<div class="info-block info-block-desc">
													<span class="info-label">상세 설명</span>
													<p class="detail-desc">{svc.description}</p>
												</div>
											</div>
											<div class="detail-side">
												<span class="detail-side-title">연결 방법</span>
												<ol class="steps">
													{#each svc.steps as step, i (i)}
														<li><span class="step-num">{i + 1}</span>{step}</li>
													{/each}
												</ol>
												{#if svc.command}
													<pre class="cmd">{svc.command}</pre>
												{/if}
											</div>
										</div>
										<div class="detail-actions">
											<a class="link-btn primary" href={svc.docsUrl} target="_blank" rel="noopener noreferrer">
												연동 가이드
												<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
													<path d="M7 17 17 7" /><path d="M8 7h9v9" />
												</svg>
											</a>
											<a class="link-btn" href={svc.consoleUrl} target="_blank" rel="noopener noreferrer">
												{svc.consoleLabel}
												<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
													<path d="M7 17 17 7" /><path d="M8 7h9v9" />
												</svg>
											</a>
										</div>
									</div>
								</td>
							</tr>
						{/if}
					{:else}
						<tr class="empty-row">
							<td colspan="7">
								<div class="empty">
									<span class="empty-icon">🔍</span>
									<span>조건에 맞는 시스템이 없습니다. 필터를 조정해 보세요.</span>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</div>

<style>
	/* 디자인 원칙: 컨텐츠 max-width 로 밀도 확보 · 큰 글씨 · 6px 살짝 둥근 · 1px 헤어라인 */
	.page {
		--box-radius: 6px;
		--hairline: 1px solid var(--border);
		--divider: 1px solid rgba(148, 163, 184, 0.1);
		padding: 30px 32px 48px;
	}
	.shell {
		max-width: 1380px;
		margin: 0 auto;
	}

	.page-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 24px;
		flex-wrap: wrap;
		margin-bottom: 22px;
	}
	.page-header h1 {
		margin: 0 0 8px;
		font-size: 25px;
		font-weight: 850;
		color: var(--text-primary);
	}
	.subtitle {
		margin: 0;
		font-size: 14px;
		line-height: 1.6;
		color: var(--text-muted);
		white-space: nowrap;
	}
	.preview-tag {
		flex-shrink: 0;
		padding: 7px 13px;
		font-size: 12.5px;
		font-weight: 800;
		color: #ddd6fe;
		background: rgba(167, 139, 250, 0.12);
		border: 1px solid rgba(167, 139, 250, 0.32);
		border-radius: var(--box-radius);
	}

	/* summary — 균등 KPI 카드 대신 구성/분포를 보여주는 단일 패널 */
	.summary {
		display: flex;
		gap: 36px;
		padding: 22px 26px;
		margin-bottom: 22px;
		background: var(--bg-card);
		border: var(--hairline);
		border-radius: var(--box-radius);
	}
	.sum-cap {
		display: block;
		font-size: 11.5px;
		font-weight: 800;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-muted);
	}

	.sum-totals {
		flex: 0 0 252px;
		display: flex;
		flex-direction: column;
	}
	.sum-total {
		display: flex;
		align-items: baseline;
		gap: 5px;
		margin-top: 7px;
	}
	.sum-total strong {
		font-size: 42px;
		font-weight: 850;
		line-height: 1;
		color: var(--text-primary);
	}
	.sum-total span {
		font-size: 15px;
		font-weight: 700;
		color: var(--text-muted);
	}
	/* 공식/커뮤니티 비율 바 — 좌우 패널을 시각적으로 묶어줌 */
	.src-bar {
		display: flex;
		gap: 3px;
		height: 8px;
		margin: 14px 0 16px;
	}
	.src-seg {
		border-radius: 3px;
		background: var(--c);
		animation: seg-grow 0.8s cubic-bezier(0.22, 1, 0.36, 1) both;
	}
	@keyframes seg-grow {
		from {
			flex-grow: 0;
		}
	}
	.sum-breakdown {
		margin: auto 0 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.sum-breakdown li {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 13.5px;
		color: var(--text-secondary);
	}
	.sum-dot {
		width: 9px;
		height: 9px;
		flex-shrink: 0;
		border-radius: 50%;
		background: var(--c);
		box-shadow: 0 0 6px color-mix(in srgb, var(--c) 55%, transparent);
	}
	.sum-name {
		font-weight: 650;
	}
	.sum-breakdown b {
		margin-left: auto;
		font-size: 15.5px;
		font-weight: 850;
		color: var(--text-primary);
	}

	.sum-div {
		width: 1px;
		flex-shrink: 0;
		background: var(--border);
	}

	/* 카테고리 분포 — 수평 바 차트 */
	.sum-dist {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}
	.sum-dist-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 12px;
	}
	.sum-dist-note {
		font-size: 12px;
		font-weight: 700;
		color: var(--text-muted);
	}
	.dist-rows {
		margin: 16px 0 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		flex: 1;
		gap: 12px;
	}
	.dist-row {
		display: flex;
		align-items: center;
		gap: 14px;
	}
	.dist-row-label {
		display: flex;
		align-items: center;
		gap: 9px;
		width: 124px;
		flex-shrink: 0;
		font-size: 13.5px;
		font-weight: 650;
		color: var(--text-secondary);
	}
	.dist-row-track {
		flex: 1;
		height: 10px;
		background: rgba(148, 163, 184, 0.12);
		border-radius: var(--radius-full);
		overflow: hidden;
	}
	.dist-row-fill {
		display: block;
		height: 100%;
		min-width: 6px;
		border-radius: var(--radius-full);
		background: linear-gradient(
			90deg,
			color-mix(in srgb, var(--c) 70%, transparent),
			var(--c)
		);
		animation: fill-grow 0.8s cubic-bezier(0.22, 1, 0.36, 1) both;
	}
	@keyframes fill-grow {
		from {
			width: 0;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.src-seg,
		.dist-row-fill {
			animation: none;
		}
	}
	.dist-row-val {
		width: 26px;
		flex-shrink: 0;
		text-align: right;
		font-size: 15px;
		font-weight: 850;
		color: var(--text-primary);
		font-variant-numeric: tabular-nums;
	}

	/* toolbar — 검색(좌) + 필터 드롭다운(우) */
	.toolbar {
		display: flex;
		align-items: center;
		gap: 14px;
		flex-wrap: wrap;
		margin-bottom: 10px;
	}
	.search-box {
		display: flex;
		align-items: center;
		gap: 9px;
		flex: 1;
		min-width: 260px;
		max-width: 460px;
		padding: 0 14px;
		height: 44px;
		background: var(--bg-card);
		border: var(--hairline);
		border-radius: var(--box-radius);
		transition: border-color 0.12s;
	}
	.search-box:focus-within {
		border-color: var(--accent);
	}
	.search-box svg {
		width: 18px;
		height: 18px;
		flex-shrink: 0;
		color: var(--text-muted);
	}
	.search-box input {
		flex: 1;
		min-width: 0;
		background: none;
		border: none;
		outline: none;
		color: var(--text-primary);
		font: inherit;
		font-size: 14.5px;
	}
	.search-box input::placeholder {
		color: var(--text-muted);
	}
	.filters {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		margin-left: auto;
	}
	.select-wrap {
		display: flex;
		align-items: center;
		height: 44px;
		padding: 0 4px 0 12px;
		background: var(--bg-card);
		border: var(--hairline);
		border-radius: var(--box-radius);
		transition: border-color 0.12s;
	}
	.select-wrap:focus-within {
		border-color: var(--accent);
	}
	.select-cap {
		font-size: 12.5px;
		font-weight: 700;
		color: var(--text-muted);
		white-space: nowrap;
		margin-right: 6px;
	}
	.select-wrap select {
		appearance: none;
		height: 100%;
		padding: 0 26px 0 4px;
		font: inherit;
		font-size: 13.5px;
		font-weight: 700;
		color: var(--text-primary);
		background: transparent;
		border: none;
		outline: none;
		cursor: pointer;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='3' stroke-linecap='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
		background-repeat: no-repeat;
		background-position: right 6px center;
	}
	.reset-btn {
		height: 44px;
		padding: 0 18px;
		font: inherit;
		font-size: 13.5px;
		font-weight: 800;
		color: var(--text-secondary);
		background: var(--bg-card);
		border: var(--hairline);
		border-radius: var(--box-radius);
		cursor: pointer;
		transition: color 0.12s, border-color 0.12s;
	}
	.reset-btn:hover:not(:disabled) {
		color: var(--text-primary);
		border-color: var(--accent);
	}
	.reset-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.result-line {
		margin: 0 0 12px;
		font-size: 13px;
		color: var(--text-muted);
	}
	.result-line b {
		color: var(--text-secondary);
		font-weight: 800;
	}

	/* table */
	.table-card {
		background: var(--bg-card);
		border: var(--hairline);
		border-radius: var(--box-radius);
		overflow: hidden;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 15px;
		table-layout: fixed;
	}
	thead th {
		text-align: left;
		background: rgba(13, 17, 23, 0.66);
		border-bottom: var(--hairline);
		padding: 0;
	}
	thead th:not(:has(.sort-th)) {
		padding: 14px 16px;
		font-size: 13px;
		font-weight: 800;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.sort-th {
		display: flex;
		align-items: center;
		gap: 7px;
		width: 100%;
		padding: 14px 16px;
		font: inherit;
		font-size: 13px;
		font-weight: 800;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		background: none;
		border: none;
		cursor: pointer;
		transition: color 0.12s;
	}
	.sort-th:hover {
		color: var(--text-primary);
	}
	.sort-th.on {
		color: var(--accent);
	}
	.sort-ico {
		font-size: 10px;
		opacity: 0.55;
	}
	.sort-th.on .sort-ico {
		opacity: 1;
	}
	/* 고정 컬럼 폭 — 정렬 흐트러짐 방지 */
	.col-name { width: 25%; }
	.col-desc { width: 27%; }
	.col-cat { width: 11%; }
	.col-conn { width: 11%; }
	.col-tags { width: 17%; }
	.col-status { width: 9%; }
	.col-chev { width: 46px; }

	.svc-row {
		cursor: pointer;
		transition: background 0.12s;
	}
	.svc-row td {
		padding: 15px 16px;
		border-bottom: var(--divider);
		vertical-align: middle;
	}
	.svc-row:hover {
		background: rgba(77, 191, 179, 0.05);
	}
	.svc-row:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	.svc-row.expanded {
		background: rgba(77, 191, 179, 0.07);
	}
	.svc-row.expanded td {
		border-bottom-color: transparent;
	}

	.svc-cell {
		display: flex;
		align-items: center;
		gap: 13px;
	}
	.svc-logo {
		display: grid;
		place-items: center;
		width: 42px;
		height: 42px;
		flex-shrink: 0;
		border-radius: 8px;
		color: var(--tint);
		background: color-mix(in srgb, var(--tint) 14%, transparent);
		border: 1px solid color-mix(in srgb, var(--tint) 30%, transparent);
	}
	.svc-logo svg {
		width: 21px;
		height: 21px;
	}
	.svc-meta {
		display: flex;
		flex-direction: column;
		gap: 3px;
		min-width: 0;
	}
	.svc-name-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.svc-name {
		font-size: 16.5px;
		font-weight: 750;
		color: var(--text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.src-badge {
		flex-shrink: 0;
		padding: 2px 8px;
		font-size: 11px;
		font-weight: 800;
		border-radius: 4px;
	}
	.src-badge.official {
		color: #93c5b8;
		background: rgba(77, 191, 179, 0.12);
		border: 1px solid rgba(77, 191, 179, 0.28);
	}
	.src-badge.community {
		color: #c4b5fd;
		background: rgba(167, 139, 250, 0.13);
		border: 1px solid rgba(167, 139, 250, 0.3);
	}
	.svc-vendor {
		font-size: 13px;
		color: var(--text-muted);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.svc-desc {
		margin: 0;
		font-size: 14px;
		line-height: 1.5;
		color: var(--text-secondary);
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		padding: 5px 11px;
		font-size: 13px;
		font-weight: 800;
		border-radius: 5px;
		color: var(--tint);
		background: color-mix(in srgb, var(--tint) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--tint) 28%, transparent);
		white-space: nowrap;
	}
	.conn {
		font-size: 14px;
		font-weight: 650;
		color: var(--text-secondary);
		white-space: nowrap;
	}
	.tag-row {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}
	.tag {
		padding: 3px 9px;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-muted);
		background: rgba(100, 116, 139, 0.16);
		border-radius: 4px;
		white-space: nowrap;
	}
	.status {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		font-size: 14px;
		font-weight: 750;
		color: var(--c);
		white-space: nowrap;
	}
	.status .dot {
		width: 8px;
		height: 8px;
		flex-shrink: 0;
		border-radius: 50%;
		background: var(--c);
		box-shadow: 0 0 7px color-mix(in srgb, var(--c) 60%, transparent);
	}
	.chev {
		display: inline-block;
		font-size: 17px;
		color: var(--text-muted);
		transition: transform 0.16s ease;
	}
	.chev.open {
		transform: rotate(180deg);
		color: var(--accent);
	}

	.empty-row td {
		padding: 0;
	}
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 60px 20px;
		color: var(--text-muted);
		font-size: 14px;
	}
	.empty-icon {
		font-size: 32px;
	}

	/* expanded detail */
	.detail-row td {
		padding: 0 16px 20px;
		background: rgba(77, 191, 179, 0.07);
		border-bottom: var(--divider);
	}
	.detail {
		display: flex;
		flex-direction: column;
		gap: 18px;
		padding: 20px 22px;
		background: rgba(13, 17, 23, 0.5);
		border: var(--hairline);
		border-radius: var(--box-radius);
	}
	.detail-grid {
		display: grid;
		grid-template-columns: 1.5fr 1fr;
		gap: 24px;
	}
	/* 설명 — 살짝 투명한 회색 박스. 요약/상세 두 영역을 라벨+구분선으로 분리 */
	.detail-info {
		display: flex;
		flex-direction: column;
		background: rgba(148, 163, 184, 0.06);
		border: 1px solid rgba(148, 163, 184, 0.12);
		border-radius: var(--box-radius);
		overflow: hidden;
	}
	.info-block {
		padding: 14px 17px;
	}
	.info-block-desc {
		flex: 1;
		border-top: 1px solid rgba(148, 163, 184, 0.12);
		background: rgba(148, 163, 184, 0.03);
	}
	.info-label {
		display: block;
		margin-bottom: 7px;
		font-size: 11px;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--text-muted);
	}
	.detail-summary {
		margin: 0;
		font-size: 15.5px;
		font-weight: 750;
		line-height: 1.45;
		color: var(--text-primary);
	}
	.detail-desc {
		margin: 0;
		font-size: 14px;
		line-height: 1.65;
		color: var(--text-secondary);
	}
	/* 액션 버튼 — 하단으로 분리, 구분선으로 컨텐츠와 나눔 */
	.detail-actions {
		display: flex;
		gap: 9px;
		flex-wrap: wrap;
		padding-top: 16px;
		border-top: var(--hairline);
	}
	.link-btn {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		padding: 10px 17px;
		font-size: 14px;
		font-weight: 800;
		text-decoration: none;
		border-radius: var(--box-radius);
		border: var(--hairline);
		background: var(--bg-card);
		color: var(--text-primary);
		transition: border-color 0.12s, background 0.12s, transform 0.1s;
	}
	.link-btn svg {
		width: 14px;
		height: 14px;
	}
	.link-btn:hover {
		transform: translateY(-1px);
		border-color: var(--accent);
		background: rgba(77, 191, 179, 0.08);
	}
	.link-btn.primary {
		background: linear-gradient(135deg, var(--accent), #20a89c);
		border-color: transparent;
		color: var(--bg-base);
	}
	.link-btn.primary:hover {
		box-shadow: 0 6px 18px -6px rgba(77, 191, 179, 0.6);
	}

	.detail-side-title {
		display: block;
		margin-bottom: 12px;
		font-size: 13px;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--text-muted);
	}
	.steps {
		margin: 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.steps li {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		font-size: 14px;
		line-height: 1.5;
		color: var(--text-secondary);
	}
	.step-num {
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		flex-shrink: 0;
		border-radius: 5px;
		font-size: 12px;
		font-weight: 800;
		color: var(--accent);
		background: rgba(77, 191, 179, 0.14);
		border: 1px solid rgba(77, 191, 179, 0.3);
	}
	.cmd {
		margin: 14px 0 0;
		padding: 13px 15px;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 13px;
		line-height: 1.6;
		color: #9fe7df;
		background: rgba(13, 17, 23, 0.85);
		border: var(--hairline);
		border-radius: var(--box-radius);
		white-space: pre-wrap;
		overflow-x: auto;
	}

	@media (max-width: 1100px) {
		table {
			table-layout: auto;
		}
		.subtitle {
			white-space: normal;
		}
		.summary {
			flex-direction: column;
			gap: 20px;
		}
		.sum-totals {
			min-width: 0;
		}
		.sum-div {
			width: auto;
			height: 1px;
		}
		.detail-grid {
			grid-template-columns: 1fr;
		}
		.col-desc,
		.col-tags {
			display: none;
		}
		.filters {
			margin-left: 0;
		}
	}
</style>
