import type { PageServerLoad } from './$types';
import { Repository } from '$lib/database.node';

export const prerender = true;

export const load: PageServerLoad = async () => {
    const repo = new Repository();
    await repo.init();
    try {
        return { stats: repo.getWorldStats() };
    } finally {
        repo.close();
    }
};
