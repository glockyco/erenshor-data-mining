<script lang="ts">
    import '../../app.css';
    import { page } from '$app/state';
    import SiteHeader from '$lib/components/landing/SiteHeader.svelte';
    import SiteFooter from '$lib/components/landing/SiteFooter.svelte';

    let { children } = $props();

    // The landing page owns its full-bleed layout; every other (app) page keeps
    // the shared centered content container it was designed against.
    const isHome = $derived(page.url.pathname === '/');
</script>

<div class="flex min-h-screen flex-col bg-bg">
    <SiteHeader />
    {#if isHome}
        {@render children()}
    {:else}
        <div class="mx-auto w-full max-w-7xl flex-1 px-4 py-8">
            {@render children()}
        </div>
    {/if}
    <SiteFooter />
</div>
