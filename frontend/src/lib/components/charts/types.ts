/**
 * 차트 wrapper 들이 공유하는 타입 정의.
 * .svelte 파일의 instance script 에서는 `export type` 이 컴파일러 단계에서
 * external export 로 보존되지 않으므로 .ts 파일로 분리.
 */

export type ValueFormat = 'percent' | 'bytes' | 'count';

export type LineSeries = {
	label: string;
	color: string;
	values: number[];
	fill?: boolean;
	format?: ValueFormat;
};

/**
 * 차트 위에 vertical mark 표시 (이벤트 시각 등).
 * `index`: x축 카테고리 인덱스 (labels 배열의 위치).
 * `label`: tooltip / legend 표시용 짧은 텍스트.
 * `color`: 라인 색.
 */
export type MarkLineEntry = {
	index: number;
	label: string;
	color: string;
};
