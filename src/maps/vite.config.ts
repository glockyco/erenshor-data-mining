import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, type Plugin, type Connect } from 'vite';
import { GAME_VERSION_PATH, handleGameVersion } from './src/lib/game-version';

/**
 * Serve the site's one dynamic endpoint in `dev` and `preview`.
 *
 * In production the Cloudflare Worker answers `/api/game-version` in front of
 * the prerendered assets, but neither Vite server runs the Worker, so the
 * footer's freshness fetch 404s without this. The handler is shared with the
 * Worker so there is one implementation to keep honest.
 */
function gameVersionEndpoint(): Plugin {
    const middleware: Connect.NextHandleFunction = (req, res, next) => {
        if (!req.url || new URL(req.url, 'http://localhost').pathname !== GAME_VERSION_PATH) {
            next();
            return;
        }

        handleGameVersion()
            .then(async (response) => {
                res.statusCode = response.status;
                response.headers.forEach((value, name) => res.setHeader(name, value));
                res.end(await response.text());
            })
            .catch(next);
    };

    return {
        name: 'erenshor-game-version-endpoint',
        configureServer(server) {
            server.middlewares.use(middleware);
        },
        configurePreviewServer(server) {
            server.middlewares.use(middleware);
        }
    };
}

export default defineConfig({
    plugins: [gameVersionEndpoint(), sveltekit(), tailwindcss()],
    assetsInclude: ['**/*.wasm'],
    ssr: {
        noExternal: ['@lucide/svelte', 'bits-ui']
    }
});
