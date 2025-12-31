<script lang="ts">
    import { onMount } from 'svelte';
    import { beforeNavigate } from '$app/navigation';
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

<slot />
