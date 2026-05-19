/**
 * Container grouping logic
 *
 * Priority chain:
 *   1. hypercube.stack label
 *   2. com.docker.compose.project label
 *   3. com.docker.compose.project.working_dir (folder name)
 *   4. Unmanaged
 */

export type GroupSource = 'label' | 'compose' | 'working_dir' | 'unmanaged';

export interface GroupResult {
	name: string;
	source: GroupSource;
	rawValue: string;
}

interface Labelable {
	labels?: Record<string, string> | null;
	names?: string[];
}

function normalizeName(raw: string): string {
	const trimmed = raw.trim();
	if (!trimmed) return 'Unmanaged';

	return trimmed
		.replace(/_default$/, '')
		.replace(/[-_]+/g, ' ')
		.trim();
}

function folderBaseName(workingDir: string): string {
	const trimmed = workingDir.replace(/[/\\]+$/, '');
	return trimmed.split(/[/\\]/).pop() ?? '';
}

export function resolveGroup(container: Labelable): GroupResult {
	const labels = container.labels ?? {};

	const hcStack = labels['hypercube.stack'];
	if (hcStack) {
		return { name: normalizeName(hcStack), source: 'label', rawValue: hcStack };
	}

	const composeProject = labels['com.docker.compose.project'];
	if (composeProject) {
		return {
			name: normalizeName(composeProject),
			source: 'compose',
			rawValue: composeProject,
		};
	}

	const workingDir = labels['com.docker.compose.project.working_dir'];
	if (workingDir) {
		const folder = folderBaseName(workingDir);
		if (folder) {
			return {
				name: normalizeName(folder),
				source: 'working_dir',
				rawValue: workingDir,
			};
		}
	}

	return { name: 'Unmanaged', source: 'unmanaged', rawValue: '' };
}

export interface GroupedProject<T extends Labelable = Labelable> {
	name: string;
	source: GroupSource;
	containers: T[];
	color: string;
	stats: { total: number; running: number; stopped: number; paused: number };
}

export function groupContainersByStack<T extends Labelable & { state?: string }>(
	containers: T[],
	colors: string[],
): GroupedProject<T>[] {
	const map = new Map<string, { source: GroupSource; items: T[] }>();

	for (const container of containers) {
		const group = resolveGroup(container);
		const existing = map.get(group.name);

		if (existing) {
			existing.items.push(container);
			continue;
		}

		map.set(group.name, { source: group.source, items: [container] });
	}

	return Array.from(map.entries())
		.map(([name, { source, items }], index) => ({
			name,
			source,
			containers: items,
			color: colors[index % colors.length],
			stats: {
				total: items.length,
				running: items.filter((item) => item.state === 'running').length,
				stopped: items.filter((item) => item.state === 'exited').length,
				paused: items.filter((item) => item.state === 'paused').length,
			},
		}))
		.sort((a, b) => {
			if (a.source === 'unmanaged' && b.source !== 'unmanaged') return 1;
			if (a.source !== 'unmanaged' && b.source === 'unmanaged') return -1;
			return a.name.localeCompare(b.name);
		});
}
