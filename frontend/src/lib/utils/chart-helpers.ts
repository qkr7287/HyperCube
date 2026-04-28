/**
 * Chart.js + Svelte 5 호환 어댑터.
 *
 * Svelte 5 의 $state / $derived / $props 는 객체를 Proxy 로 감싸 reactivity 를
 * 부여하는데, Chart.js v4 는 자기 내부에서 데이터 객체의 prototype chain 을
 * walk 한다. Proxy 의 [[GetPrototypeOf]] trap 안에서 Reflect.getPrototypeOf 와
 * Object.getPrototypeOf 가 ping-pong 재귀하면서 stack overflow (RangeError:
 * Maximum call stack size exceeded) 가 발생한다.
 *
 * 해결: Chart.js 에 넘기는 데이터/옵션 객체는 plain object 로 deep-copy 해
 * 전달. 단, CanvasGradient / CanvasPattern / HTMLElement / 함수 같은 non-plain
 * 값은 ref 그대로 둬야 chart.js 가 정상 처리한다 (gradient backgroundColor 등).
 */
export function toChartPayload<T>(value: T): T {
	return clonePlain(value) as T;
}

function clonePlain(v: unknown): unknown {
	if (v === null || v === undefined || typeof v !== 'object') return v;
	if (Array.isArray(v)) return v.map(clonePlain);
	// Object.prototype.toString 으로 [[Class]] 만 보고 plain 판정.
	// (Object.getPrototypeOf 호출 자체가 svelte proxy 의 trap 에 걸려 cycle 을
	//  유발할 수 있어 우회.)
	if (Object.prototype.toString.call(v) !== '[object Object]') {
		// CanvasGradient / Image / Date / Map / class instance 등은 그대로.
		return v;
	}
	const out: Record<string, unknown> = {};
	for (const k of Object.keys(v as Record<string, unknown>)) {
		out[k] = clonePlain((v as Record<string, unknown>)[k]);
	}
	return out;
}
