/**
 * 차트 wrapper 들이 공유하는 타입 정의.
 * .svelte 파일의 instance script 에서는 `export type` 이 컴파일러 단계에서
 * external export 로 보존되지 않으므로 .ts 파일로 분리.
 */

export type ValueFormat = 'percent' | 'bytes' | 'count' | 'bytes_per_sec';

export type LineSeries = {
	label: string;
	color: string;
	values: number[];
	fill?: boolean;
	format?: ValueFormat;
};

/**
 * 차트 위에 mark 표시. 둘 중 하나만 채움:
 * - `index`: x축 카테고리 인덱스 (labels 배열의 위치). vertical line.
 * - `yAxis`: y축 값. horizontal line (임계 표시 등).
 * `label`: tooltip / legend 표시용 짧은 텍스트.
 * `color`: 라인 색.
 */
export type MarkLineEntry = {
	index?: number;
	yAxis?: number;
	label: string;
	color: string;
};
