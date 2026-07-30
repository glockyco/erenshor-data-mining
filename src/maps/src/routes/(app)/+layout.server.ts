import { getMapsDatabasePath } from '$lib/database-path.server';
import { Repository } from '$lib/database.node';

export const prerender = true;

/**
 * Load the data-provenance stamp once for every page in the (app) group so the
 * shared footer can state which game build the site's data came from.
 */
export const load = async () => {
	const repo = new Repository();
	try {
		await repo.init(getMapsDatabasePath());
		return { provenance: repo.getDataProvenance() };
	} finally {
		repo.close();
	}
};
