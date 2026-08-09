/**
 * Canonical Worker for `erenshor.compendiums.org`.
 *
 * The canonical host is a static site with exactly one dynamic route. Static
 * assets are served without invoking this Worker, so the only requests that
 * reach it are `/api/game-version`, which `assets.run_worker_first` routes here
 * unconditionally, and paths that match no asset.
 *
 * Host-aware redirects and the shipped-overlay compatibility surface live in
 * `legacy-worker.ts`, not here.
 */
import { GAME_VERSION_PATH, handleGameVersion } from '$lib/game-version';

export interface AssetsBinding {
    fetch(request: Request): Promise<Response>;
}

export interface Env {
    ASSETS: AssetsBinding;
}

export default {
    fetch(request: Request, env: Env): Promise<Response> {
        if (new URL(request.url).pathname === GAME_VERSION_PATH) {
            return handleGameVersion();
        }

        // An asset miss. Delegating preserves the deliberate 404 that
        // `not_found_handling: "none"` produces, rather than inventing a
        // fallback page.
        return env.ASSETS.fetch(request);
    }
};
