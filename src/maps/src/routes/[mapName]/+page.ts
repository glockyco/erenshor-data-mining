import type { Load } from '@sveltejs/kit';

// Disable prerendering since we use URL search params (coordinateId) dynamically
export const prerender = false;

export const load: Load = ({ params }) => {
	return {
		mapName: params.mapName
	};
};
