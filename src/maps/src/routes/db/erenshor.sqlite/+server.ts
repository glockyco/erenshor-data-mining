import { readFile } from 'node:fs/promises';
import { getMapsDatabasePath } from '$lib/database-path.server';

export const prerender = true;

/**
 * The clean database, published unchanged. Consumers outside the site may
 * download it, and shipped companion overlays keep it same-origin.
 */
export async function GET() {
    return new Response(await readFile(getMapsDatabasePath()), {
        headers: { 'Content-Type': 'application/vnd.sqlite3' }
    });
}
