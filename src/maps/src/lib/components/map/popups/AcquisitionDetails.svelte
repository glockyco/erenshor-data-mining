<script lang="ts">
    import type { ItemAcquisition } from '$lib/item-provenance';
    import { conditionLines, probabilityText, quantityText, conditionsSatisfiable } from '$lib/item-provenance';
    let { fact, coordinateKey, scene, names = {} }: {
        fact: ItemAcquisition; coordinateKey?: string; scene?: string | null; names?: Record<string, string>
    } = $props();
</script>

<div class="space-y-0.5 text-xs text-zinc-400" data-acquisition-key={fact.acquisition_key} data-origin-item={fact.item_stable_key}>
    {#if probabilityText(fact)}<p>{probabilityText(fact)}</p>{/if}
    <p>{quantityText(fact)}</p>
    {#each conditionLines(fact.conditions, names) as condition, index (index)}<p>{condition}</p>{/each}
    {#each fact.locations.filter((location) => conditionsSatisfiable([...fact.conditions, ...location.conditions]) &&
        (!coordinateKey || location.coordinate_stable_key === coordinateKey) &&
        (!scene || !location.scene || location.scene === scene)) as location (location.location_key)}
        {#if !coordinateKey && !scene && fact.locations.length > 1}<p>{location.scene ?? 'Source location'}</p>{/if}
        {#each conditionLines(location.conditions, names) as condition, index (index)}<p>{condition}</p>{/each}
        {#if location.player_level_min !== null || location.player_level_max !== null}
            <p>Player level {location.player_level_min ?? '?'} to {location.player_level_max ?? '?'}</p>
        {/if}
    {/each}
</div>
