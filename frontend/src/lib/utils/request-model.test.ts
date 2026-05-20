import { describe, expect, it } from 'vitest';
import { missingDefaultModelIds, resolveSubmitModelIds } from './request-model';

const versions = [{ id: 'v1' }, { id: 'v2' }, { id: 'v3' }];

describe('resolveSubmitModelIds', () => {
	it('returns the selection as-is for templates with no default models', () => {
		const result = resolveSubmitModelIds({
			defaultModelVersionIds: [],
			selection: ['v2'],
			selectionDirty: true,
			modelVersions: versions,
		});
		expect(result).toEqual({ ids: ['v2'], error: null });
	});

	it('restores template defaults when selection is empty and untouched', () => {
		const result = resolveSubmitModelIds({
			defaultModelVersionIds: ['v1', 'v2'],
			selection: [],
			selectionDirty: false,
			modelVersions: versions,
		});
		expect(result).toEqual({ ids: ['v1', 'v2'], error: null });
	});

	it('normalizes non-string default ids', () => {
		const result = resolveSubmitModelIds({
			defaultModelVersionIds: [1, 2] as unknown as string[],
			selection: [],
			selectionDirty: false,
			modelVersions: [{ id: '1' }, { id: '2' }],
		});
		expect(result.ids).toEqual(['1', '2']);
	});

	it('does not override an explicit empty selection (user cleared it)', () => {
		const result = resolveSubmitModelIds({
			defaultModelVersionIds: ['v1'],
			selection: [],
			selectionDirty: true,
			modelVersions: versions,
		});
		expect(result).toEqual({ ids: [], error: null });
	});

	it('keeps the user selection when they picked their own models', () => {
		const result = resolveSubmitModelIds({
			defaultModelVersionIds: ['v1'],
			selection: ['v3'],
			selectionDirty: true,
			modelVersions: versions,
		});
		expect(result).toEqual({ ids: ['v3'], error: null });
	});

	it('blocks submission when a model template has no model list loaded yet', () => {
		const result = resolveSubmitModelIds({
			defaultModelVersionIds: ['v1'],
			selection: [],
			selectionDirty: false,
			modelVersions: [],
		});
		expect(result.ids).toEqual(['v1']);
		expect(result.error).not.toBeNull();
	});

	it('does not block a no-model template even when the list is empty', () => {
		const result = resolveSubmitModelIds({
			defaultModelVersionIds: [],
			selection: [],
			selectionDirty: false,
			modelVersions: [],
		});
		expect(result).toEqual({ ids: [], error: null });
	});
});

describe('missingDefaultModelIds', () => {
	it('returns default ids absent from the model list', () => {
		expect(missingDefaultModelIds(['v1', 'v9'], versions)).toEqual(['v9']);
	});

	it('returns empty when all defaults are known', () => {
		expect(missingDefaultModelIds(['v1', 'v2'], versions)).toEqual([]);
	});

	it('handles null/undefined defaults', () => {
		expect(missingDefaultModelIds(null, versions)).toEqual([]);
		expect(missingDefaultModelIds(undefined, versions)).toEqual([]);
	});
});
