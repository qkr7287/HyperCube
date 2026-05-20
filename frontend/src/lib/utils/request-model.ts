/**
 * 컨테이너 요청 모달의 model_version_ids 결정 로직.
 *
 * 템플릿이 default 모델을 묶고 있는데 모델 목록(modelVersions)이 아직 안 왔거나
 * 불완전할 때, 사용자에게 경고 없이 default 를 버리면 model_version_ids:[] 가
 * 제출되어 prepare job 이 0건 생성된다. 제출 시점에 default 를 재적용하고,
 * 모델 목록이 비어 검증조차 불가하면 제출을 차단한다.
 */

export type ModelVersionRef = { id: string };

export type ResolveModelInput = {
	defaultModelVersionIds?: (string | number)[] | null;
	/** 현재 사용자가 선택한 model version id 목록 */
	selection: string[];
	/** 사용자가 모델 선택을 직접 건드렸는지 (true 면 default 재적용 안 함) */
	selectionDirty: boolean;
	modelVersions: ModelVersionRef[];
};

export type ResolveModelResult = {
	ids: string[];
	/** null 이 아니면 제출을 막아야 함 */
	error: string | null;
};

/**
 * 제출 직전 최종 model_version_ids 와 차단 여부를 계산한다.
 */
export function resolveSubmitModelIds(input: ResolveModelInput): ResolveModelResult {
	const defaults = (input.defaultModelVersionIds ?? []).map((id) => String(id));

	// 모델을 묶지 않는 일반 템플릿: 사용자 선택을 그대로 사용.
	if (defaults.length === 0) {
		return { ids: [...input.selection], error: null };
	}

	// 사용자가 손대지 않았고 선택이 비어 있으면 템플릿 기본값을 복원한다.
	const effective =
		!input.selectionDirty && input.selection.length === 0 ? defaults : input.selection;

	// 모델 목록을 아직 못 받아 검증 자체가 불가하면 제출을 차단한다.
	if (input.modelVersions.length === 0) {
		return {
			ids: effective,
			error: '모델 목록을 아직 불러오지 못했습니다. 잠시 후 다시 시도하세요.',
		};
	}

	return { ids: effective, error: null };
}

/**
 * 템플릿 default 모델 중 현재 모델 목록에 없는 id 들.
 * 카탈로그 미등록 / 페이지네이션 누락을 운영자가 즉시 인지하도록 경고용.
 */
export function missingDefaultModelIds(
	defaultModelVersionIds: (string | number)[] | null | undefined,
	modelVersions: ModelVersionRef[],
): string[] {
	const known = new Set(modelVersions.map((version) => version.id));
	return (defaultModelVersionIds ?? [])
		.map((id) => String(id))
		.filter((id) => !known.has(id));
}
