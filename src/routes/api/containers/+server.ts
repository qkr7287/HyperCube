import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import Docker from 'dockerode';

const docker = new Docker();

export const GET: RequestHandler = async () => {
	try {
		const containers = await docker.listContainers({ all: true });
		
		const containerData = containers.map(container => ({
			id: container.Id,
			shortId: container.Id.substring(0, 12),
			names: container.Names,
			image: container.Image,
			imageId: container.ImageID,
			command: container.Command,
			created: container.Created,
			state: container.State,
			status: container.Status,
			ports: container.Ports,
			labels: container.Labels,
			sizeRw: container.SizeRw,
			sizeRootFs: container.SizeRootFs,
			hostConfig: container.HostConfig,
			networkSettings: container.NetworkSettings,
			mounts: container.Mounts
		}));

		return json({
			success: true,
			data: containerData
		});
	} catch (error) {
		console.error('Docker API Error:', error);
		return json({
			success: false,
			error: 'Docker API 연결에 실패했습니다.'
		}, { status: 500 });
	}
};
