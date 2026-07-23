import type { PageServerLoad } from './$types';
import { getMapsDatabasePath } from '$lib/database-path.server';
import { Repository } from '$lib/database.node';

export const prerender = true;

export const load: PageServerLoad = async () => {
    const repo = new Repository();
    await repo.init(getMapsDatabasePath());
    try {
        return { stats: repo.getWorldStats() };
    } finally {
        repo.close();
    }
};
