import type { Plugin } from 'chart.js';

export type RightEdgeLabelFormatter = (value: number) => string;

export type RightEdgeLabelOptions = {
	enabled?: boolean;
	topNames?: Set<string>;
	format?: RightEdgeLabelFormatter;
	fontSize?: number;
	lineHeight?: number;
	padding?: number;
};

const DEFAULT_FONT_SIZE = 10;
const DEFAULT_LINE_HEIGHT = 14;
const DEFAULT_PADDING = 6;

/**
 * Draws `{dataset.label} {formatted-last-value}` next to the last point of each
 * highlighted ("top-N") dataset, with simple vertical collision handling. Meant
 * to be registered inline per chart via `plugins: [rightEdgeLabelsPlugin]` and
 * configured via `options.plugins.rightEdgeLabels`. Reserve ~110px of
 * `layout.padding.right` so labels don't clip.
 */
export const rightEdgeLabelsPlugin: Plugin = {
	id: 'rightEdgeLabels',
	afterDatasetsDraw(chart, _args, pluginOptions: RightEdgeLabelOptions = {}) {
		if (pluginOptions?.enabled === false) return;
		const topNames = pluginOptions.topNames;
		if (!topNames || topNames.size === 0) return;

		const { ctx, chartArea } = chart;
		if (!chartArea) return;

		const fontSize = pluginOptions.fontSize ?? DEFAULT_FONT_SIZE;
		const lineHeight = pluginOptions.lineHeight ?? DEFAULT_LINE_HEIGHT;
		const padding = pluginOptions.padding ?? DEFAULT_PADDING;
		const format = pluginOptions.format ?? ((value: number) => value.toFixed(1));

		const placed: number[] = [];

		chart.data.datasets.forEach((dataset, index) => {
			if ((dataset as { hidden?: boolean }).hidden) return;
			const label = dataset.label ?? '';
			if (!topNames.has(label)) return;

			const meta = chart.getDatasetMeta(index);
			const points = meta.data;
			if (!points?.length) return;
			const last = points[points.length - 1] as unknown as { x: number; y: number };
			if (!last || !Number.isFinite(last.x) || !Number.isFinite(last.y)) return;

			const values = dataset.data as Array<number | null | undefined>;
			const lastValue = Number(values[values.length - 1] ?? 0);
			const text = `${label} ${format(lastValue)}`;

			let yPos = last.y;
			for (const previous of placed) {
				if (Math.abs(yPos - previous) < lineHeight) {
					yPos = previous + lineHeight;
				}
			}
			const clampedY = Math.min(
				chartArea.bottom - fontSize / 2,
				Math.max(chartArea.top + fontSize / 2, yPos),
			);
			placed.push(clampedY);

			ctx.save();
			ctx.font = `700 ${fontSize}px system-ui, -apple-system, 'Segoe UI', sans-serif`;
			ctx.textBaseline = 'middle';
			ctx.textAlign = 'left';

			const textWidth = ctx.measureText(text).width;
			const labelX = last.x + padding;
			const pillWidth = textWidth + padding * 2;
			const pillHeight = lineHeight;

			ctx.fillStyle = 'rgba(13, 17, 23, 0.78)';
			ctx.strokeStyle = (dataset.borderColor as string) ?? '#30d5c8';
			ctx.lineWidth = 1;
			ctx.beginPath();
			const radius = 4;
			const x0 = labelX - padding / 2;
			const y0 = clampedY - pillHeight / 2;
			const x1 = x0 + pillWidth;
			const y1 = y0 + pillHeight;
			ctx.moveTo(x0 + radius, y0);
			ctx.lineTo(x1 - radius, y0);
			ctx.quadraticCurveTo(x1, y0, x1, y0 + radius);
			ctx.lineTo(x1, y1 - radius);
			ctx.quadraticCurveTo(x1, y1, x1 - radius, y1);
			ctx.lineTo(x0 + radius, y1);
			ctx.quadraticCurveTo(x0, y1, x0, y1 - radius);
			ctx.lineTo(x0, y0 + radius);
			ctx.quadraticCurveTo(x0, y0, x0 + radius, y0);
			ctx.closePath();
			ctx.fill();
			ctx.stroke();

			ctx.fillStyle = (dataset.borderColor as string) ?? '#e2e8f0';
			ctx.fillText(text, labelX, clampedY);
			ctx.restore();
		});
	},
};
