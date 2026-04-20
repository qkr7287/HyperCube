// Shared "stack health" colour helper used by both the 3D scene
// (membrane / group mesh) and the sidebar project card edge bar so
// the two layers read the same colour from the same data.

export interface StackHealth {
	running: number;
	total: number;
}

export type HealthColorOutput = {
	hex: string; // "#rrggbb"
	rgb: { r: number; g: number; b: number };
	number: number; // 0xrrggbb for three.js
};

// Three anchor stops along a red → amber → green gradient.
const STOP_RED = { r: 0xf8, g: 0x71, b: 0x71 }; // #f87171
const STOP_AMBER = { r: 0xfa, g: 0xcc, b: 0x15 }; // #facc15
const STOP_GREEN = { r: 0x4a, g: 0xde, b: 0x80 }; // #4ade80

function lerp(a: number, b: number, t: number): number {
	return Math.round(a + (b - a) * t);
}

function lerpRgb(
	a: { r: number; g: number; b: number },
	b: { r: number; g: number; b: number },
	t: number
): { r: number; g: number; b: number } {
	return { r: lerp(a.r, b.r, t), g: lerp(a.g, b.g, t), b: lerp(a.b, b.b, t) };
}

function toHex(v: number): string {
	return v.toString(16).padStart(2, '0');
}

/**
 * Map a running/total ratio to a three-stop gradient:
 *   ratio 0.0 → red (all stopped)
 *   ratio 0.5 → amber (half running)
 *   ratio 1.0 → green (all running)
 *
 * Empty stacks (total = 0) are treated as fully-healthy rather than
 * divide-by-zero; they just don't contribute to the scene anyway.
 */
export function healthColor(running: number, total: number): HealthColorOutput {
	const ratio = total > 0 ? Math.max(0, Math.min(1, running / total)) : 1;
	const rgb =
		ratio < 0.5
			? lerpRgb(STOP_RED, STOP_AMBER, ratio * 2)
			: lerpRgb(STOP_AMBER, STOP_GREEN, (ratio - 0.5) * 2);
	const hex = `#${toHex(rgb.r)}${toHex(rgb.g)}${toHex(rgb.b)}`;
	const number = (rgb.r << 16) | (rgb.g << 8) | rgb.b;
	return { hex, rgb, number };
}

export function healthColorFromStack(stack: StackHealth): HealthColorOutput {
	return healthColor(stack.running, stack.total);
}
