export type Tick = (dt: number) => void;

/**
 * Single requestAnimationFrame owner for the topology. Subscribers
 * register a tick and get a detacher back. Start / stop are
 * idempotent so the same loop survives remounts.
 */
export class RenderLoop {
	private readonly ticks: Set<Tick> = new Set();
	private rafId: number | null = null;
	private lastTs: number | null = null;

	add(cb: Tick): () => void {
		this.ticks.add(cb);
		return () => this.ticks.delete(cb);
	}

	start(): void {
		if (this.rafId !== null) return;
		const step = (ts: number): void => {
			const dt = this.lastTs === null ? 0 : (ts - this.lastTs) / 1000;
			this.lastTs = ts;
			this.ticks.forEach((cb) => cb(dt));
			this.rafId = requestAnimationFrame(step);
		};
		this.rafId = requestAnimationFrame(step);
	}

	stop(): void {
		if (this.rafId !== null) cancelAnimationFrame(this.rafId);
		this.rafId = null;
		this.lastTs = null;
	}
}
