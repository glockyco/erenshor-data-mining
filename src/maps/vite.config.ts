import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
    plugins: [sveltekit(), tailwindcss()],
    assetsInclude: ['**/*.wasm'],
    build: { sourcemap: true },
    ssr: {
        noExternal: ['@lucide/svelte', 'bits-ui']
    }
});
