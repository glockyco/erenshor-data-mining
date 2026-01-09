<script lang="ts">
    import { onMount } from 'svelte';
    import { beforeNavigate } from '$app/navigation';
    import { PUBLIC_CLOUDFLARE_ANALYTICS_TOKEN } from '$env/static/public';
    import '../app.css';

    onMount(() => {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/service-worker.js', { type: 'module' });
        }
    });

    beforeNavigate(async () => {
        if (!('serviceWorker' in navigator)) return;
        const registration = await navigator.serviceWorker.ready;
        if (registration.waiting) {
            registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
    });
</script>

<svelte:head>
    {#if PUBLIC_CLOUDFLARE_ANALYTICS_TOKEN}
        <script
            defer
            src="https://static.cloudflareinsights.com/beacon.min.js"
            data-cf-beacon={`{"token": "${PUBLIC_CLOUDFLARE_ANALYTICS_TOKEN}"}`}
        ></script>
    {/if}
</svelte:head>

<slot />
