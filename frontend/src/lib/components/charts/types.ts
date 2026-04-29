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
