import { Entity } from './Entity';

export type HubType = 'stack' | 'network' | 'volume';

/**
 * Abstract hub — tracks its member container ids and is rendered
 * with a subclass-specific mesh / color.
 */
export abstract class Hub extends Entity {
	readonly kind = 'hub' as const;
	abstract readonly hubType: HubType;
	readonly memberIds: Set<string> = new Set();

	addMember(id: string): void {
		this.memberIds.add(id);
	}

	removeMember(id: string): void {
		this.memberIds.delete(id);
	}

	clearMembers(): void {
		this.memberIds.clear();
	}
}
