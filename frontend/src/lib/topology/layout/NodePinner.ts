/**
 * Remembers which nodes have already been scattered outward so that
 * subsequent focus changes leave them alone (req #10). Pure state —
 * the actual fx/fy/fz fixing happens in ForceLayout.
 */
export class NodePinner {
	private readonly pinned: Set<string> = new Set();

	pin(id: string): void {
		this.pinned.add(id);
	}

	unpin(id: string): void {
		this.pinned.delete(id);
	}

	isPinned(id: string): boolean {
		return this.pinned.has(id);
	}

	size(): number {
		return this.pinned.size;
	}

	clear(): void {
		this.pinned.clear();
	}

	snapshot(): readonly string[] {
		return Array.from(this.pinned);
	}
}
