/**
 * ECharts entry point — partial import for tree-shaking.
 *
 * 모든 chart wrapper 는 이 파일에서 export 한 `echarts` 만 import 한다.
 * `import * as echarts from 'echarts'` 같은 full import 는 bundle 을
 * ~330KB gzip 까지 늘리므로 금지 (각 wrapper 의 import 도 reviewer 가 검증).
 *
 * Phase 별 chart 추가 시 여기 한 곳에서 `echarts.use([...])` 에 등록.
 */
import * as echarts from 'echarts/core';
import {
	LineChart,
	BarChart,
	PieChart,
	RadarChart,
	ScatterChart,
	GaugeChart,
} from 'echarts/charts';
import {
	GridComponent,
	TooltipComponent,
	LegendComponent,
	GraphicComponent,
	RadarComponent,
	TitleComponent,
	MarkLineComponent,
	MarkAreaComponent,
	DataZoomComponent,
	DataZoomInsideComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
	LineChart,
	BarChart,
	PieChart,
	RadarChart,
	ScatterChart,
	GaugeChart,
	GridComponent,
	TooltipComponent,
	LegendComponent,
	GraphicComponent,
	RadarComponent,
	TitleComponent,
	MarkLineComponent,
	MarkAreaComponent,
	DataZoomComponent,
	DataZoomInsideComponent,
	CanvasRenderer,
]);

export { echarts };
export type { EChartsType } from 'echarts/core';
export type { EChartsOption } from 'echarts';
