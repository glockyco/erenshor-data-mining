import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
    preprocess: vitePreprocess(),
    kit: {
        // No `fallback`: every reachable URL is prerendered (the (app)
        // group, /map, /robots.txt, /sitemap.xml, and every /[mapName]
        // slug enumerated from MAPS). Unknown URLs should 404, not be
        // rewritten to the home page.
        adapter: adapter()
    }
};

export default config;
