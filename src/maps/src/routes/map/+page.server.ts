import { buildMapWorldData } from '$lib/map-world-data.server';

export const prerender = true;

export const load = async () => buildMapWorldData();
