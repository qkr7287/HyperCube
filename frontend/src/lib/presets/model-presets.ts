export type ModelPreset = {
	id: string;
	label: string;
	tagline: string;
	description: string;
	badge: string;
	framework: string;
	task: string;
	baseImage: string;
	requiresGpu: boolean;
	workspaceKind: 'jupyter' | 'code-server' | 'api';
	workspacePort: number;
	minCpuPercent: number;
	minMemoryMb: number;
	minWorkspaceGb: number;
	defaultMaxRuntimeHours: number;
};

export const MODEL_PRESETS: ModelPreset[] = [
	{
		id: 'pytorch-jupyter',
		label: 'PyTorch + Jupyter Lab',
		tagline: '딥러닝 실험·학습',
		description:
			'PyTorch + CUDA 12.4 환경에서 Jupyter Lab으로 노트북 실험. 일반적인 .pt / .pth / .safetensors 모델에 적합.',
		badge: 'PyTorch',
		framework: 'pytorch',
		task: 'general',
		baseImage: 'hypercube/ml-pytorch-jupyter:cuda12.4-airgap',
		requiresGpu: true,
		workspaceKind: 'jupyter',
		workspacePort: 8888,
		minCpuPercent: 100,
		minMemoryMb: 2048,
		minWorkspaceGb: 10,
		defaultMaxRuntimeHours: 24,
	},
	{
		id: 'tensorflow-jupyter',
		label: 'TensorFlow + Jupyter Lab',
		tagline: 'TF/Keras 실험',
		description:
			'TensorFlow + Keras + CUDA 12.4 환경에서 Jupyter Lab. SavedModel / .h5 / .pb 형식 권장.',
		badge: 'TensorFlow',
		framework: 'tensorflow',
		task: 'general',
		baseImage: 'hypercube/ml-tensorflow-jupyter:cuda12.4-airgap',
		requiresGpu: true,
		workspaceKind: 'jupyter',
		workspacePort: 8888,
		minCpuPercent: 100,
		minMemoryMb: 2048,
		minWorkspaceGb: 10,
		defaultMaxRuntimeHours: 24,
	},
	{
		id: 'code-server',
		label: 'Code Server (VS Code)',
		tagline: '코드 편집 + 실행',
		description:
			'브라우저에서 VS Code를 사용. 모델을 코드와 함께 다루거나 커스텀 스크립트로 추론할 때.',
		badge: 'Code',
		framework: 'pytorch',
		task: 'general',
		baseImage: 'hypercube/ml-code-server:cuda12.4-airgap',
		requiresGpu: true,
		workspaceKind: 'code-server',
		workspacePort: 8080,
		minCpuPercent: 100,
		minMemoryMb: 2048,
		minWorkspaceGb: 10,
		defaultMaxRuntimeHours: 24,
	},
	{
		id: 'vllm-api',
		label: 'vLLM OpenAI API',
		tagline: 'LLM 서빙 (OpenAI 호환)',
		description:
			'vLLM으로 LLM을 OpenAI API 호환 엔드포인트로 서빙. HuggingFace 형식 모델 디렉터리 권장.',
		badge: 'vLLM',
		framework: 'vllm',
		task: 'text-generation',
		baseImage: 'hypercube/ml-vllm-openai:cuda12.4-airgap',
		requiresGpu: true,
		workspaceKind: 'api',
		workspacePort: 8000,
		minCpuPercent: 200,
		minMemoryMb: 8192,
		minWorkspaceGb: 30,
		defaultMaxRuntimeHours: 48,
	},
];

export function getPresetById(id: string | null | undefined): ModelPreset | null {
	if (!id) return null;
	return MODEL_PRESETS.find((p) => p.id === id) ?? null;
}
