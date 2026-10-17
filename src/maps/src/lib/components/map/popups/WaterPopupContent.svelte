<script lang="ts">
    import type { WorldWater } from '$lib/types/world-map';
    import WikiLink from '$lib/components/map/WikiLink.svelte';
    import AcquisitionDetails from './AcquisitionDetails.svelte';
    let { marker }: { marker: WorldWater } = $props();
    const items = $derived([...new Map([...marker.daytimeItems, ...marker.nighttimeItems]
        .map((item) => [item.provenance.acquisition_key, item])).values()]);
</script>

<div class="space-y-3">
    <div class="rounded bg-zinc-800 p-3">
        <div class="mb-2 text-xs uppercase tracking-wide text-zinc-500">Catchable Fish</div>
        {#each items as item, i (i)}
            <div class="mb-2 space-y-1">
                <div class="flex items-center justify-between text-sm text-zinc-300">{item.name}<WikiLink pageName={item.wikiPageName} /></div>
                <AcquisitionDetails fact={item.provenance} coordinateKey={marker.stableKey} />
            </div>
        {:else}
            <p class="text-sm text-zinc-400">No fish data available.</p>
        {/each}
    </div>
</div>
