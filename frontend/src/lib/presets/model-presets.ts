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
	available?: boolean;
};

// 실제 운영 가능한 환경. baseImage 가 registry 에 로드돼 있어야 함.
// 새 환경 추가 절차:
//   1) packaging/ml-images/<name>/ 에 Dockerfile + start.sh 작성
//   2) bash packaging/ml-images/build-<name>.sh 로 빌드 (+ docker load on airgap)
//   3) 아래 배열에 entry 추가
// 변형(model_class 만 다른 모델)은 wizard 의 "직접 입력" recipe 로 별도 등록 없이 처리됨.
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
		available: true,
	},
];

export function getPresetById(id: string | null | undefined): ModelPreset | null {
	if (!id) return null;
	return MODEL_PRESETS.find((p) => p.id === id) ?? null;
}
