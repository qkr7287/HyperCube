/**
 * Initial state marker — the layout's default parameters already
 * cluster everything toward the origin; ClusterState exists so that
 * Phase 2 can add sibling states (FocusState) without reshuffling
 * the facade.
 */
export class ClusterState {
	readonly kind = 'cluster' as const;
}
