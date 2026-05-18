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

// Keep only presets whose base_image actually exists in the registry.
// Add a new preset here once its airgap image is built and pushed.
export const MODEL_PRESETS: ModelPreset[] = [
	{
		id: 'pytorch-jupyter',
		label: 'PyTorch + Jupyter Lab',
		tagline: '딥러닝 실험·학습 (멀티모달 포함)',
		description:
			'PyTorch + CUDA 12.4 환경에서 Jupyter Lab으로 노트북 실험. transformers · gradio 데모 · 학습 스크립트 모두 가능. 일반 .pt / .pth / .safetensors / HuggingFace 디렉터리 모델에 적합.',
		badge: 'PyTorch',
		framework: 'pytorch',
		task: 'general',
		baseImage: 'hypercube/ml-pytorch-jupyter:cuda12.4-airgap',
		requiresGpu: true,
		workspaceKind: 'jupyter',
		workspacePort: 8888,
		minCpuPercent: 100,
		minMemoryMb: 4096,
		minWorkspaceGb: 20,
		defaultMaxRuntimeHours: 24,
	},
];

export function getPresetById(id: string | null | undefined): ModelPreset | null {
	if (!id) return null;
	return MODEL_PRESETS.find((p) => p.id === id) ?? null;
}
