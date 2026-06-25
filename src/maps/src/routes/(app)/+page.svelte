<script lang="ts">
    import { onMount } from 'svelte';
    import type { PageData } from './$types';
    import Seo from '$lib/components/Seo.svelte';
    import { websiteJsonLd, webApplicationJsonLd, videoGameJsonLd } from '$lib/seo/jsonld';
    import Hero from '$lib/components/landing/Hero.svelte';
    import ToolsSection from '$lib/components/landing/ToolsSection.svelte';
    import SectionDivider from '$lib/components/landing/SectionDivider.svelte';
    import AboutSection from '$lib/components/landing/AboutSection.svelte';
    import CommunitySection from '$lib/components/landing/CommunitySection.svelte';
    import CoordHud from '$lib/components/landing/CoordHud.svelte';
    import { initCoordinates } from '$lib/components/landing/coordinates';

    let { data }: { data: PageData } = $props();

    onMount(() => initCoordinates());
</script>

<Seo
    path="/"
    title="Erenshor Maps – Interactive Maps, Mods & Data"
    description="Interactive maps, reference data, and companion mods for Erenshor, the single-player simulated MMORPG."
    jsonLd={[websiteJsonLd(), webApplicationJsonLd(), videoGameJsonLd()]}
/>

<Hero />

<main class="mx-auto max-w-[1140px] px-7">
    <ToolsSection />
    <SectionDivider />
    <AboutSection stats={data.stats} />
    <SectionDivider />
    <CommunitySection />
</main>

<CoordHud />
