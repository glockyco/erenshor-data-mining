<script lang="ts">
    import type { ResolvedItemSource } from '$lib/map/search/item-source-provider';
    import type { ItemSearchResult } from '$lib/map/search';
    import { conditionLines, probabilityText, quantityText, conditionsSatisfiable } from '$lib/item-provenance';
    import WikiLink from '$lib/components/map/WikiLink.svelte';
    import Crosshair from '@lucide/svelte/icons/crosshair';

    interface Props {
        result: ItemSearchResult;
        sources: ResolvedItemSource[];
        onHoverSpawn: (stableKey: string | string[] | null) => void;
        onFocusSpawn: (stableKey: string | string[]) => void;
        onFocusAll: () => void;
    }
    let { result, sources, onHoverSpawn, onFocusSpawn, onFocusAll }: Props = $props();
    const allKeys = $derived([...new Set(sources.flatMap((source) => source.markers.map((marker) => marker.stableKey)))]);
    const labels: Record<string, string> = {
        character_drop: 'Dropped by', common_world_item: 'Common world drop', special_world_drop: 'World drop',
        vendor: 'Sold by', dialog: 'Talk to', quest_reward: 'Quest reward', crafting: 'Crafting recipe',
        item_drop: 'Use item', spell_created: 'Created by', mining: 'Mining', fishing: 'Fishing',
        fishing_bonus: 'Fishing bonus', auction_house: 'Auction House', item_bag: 'Ground item',
        starting_class: 'Starting item', ui_grant: 'Available from', item_conversion: 'Convert item'
    };
</script>

<div class="space-y-3 text-xs">
    <div class="relative flex items-center justify-center">
        {#if result.iconHash}<img src={`/items/${result.iconHash}.w48.webp`} alt="" class="h-12 w-12" />{/if}
        <div class="absolute right-0"><WikiLink pageName={result.wikiPageName} /></div>
    </div>
    {#if allKeys.length}
        <button type="button" onclick={() => onFocusAll()} onmouseenter={() => onHoverSpawn(allKeys)}
            onmouseleave={() => onHoverSpawn(null)} class="flex w-full items-center justify-center gap-2 rounded bg-zinc-700/50 px-3 py-2 text-zinc-300 hover:bg-zinc-700">
            <Crosshair class="h-3.5 w-3.5" />Show all {allKeys.length} location{allKeys.length === 1 ? '' : 's'}
        </button>
    {:else if !result.hasKnownSource}
        <p class="text-center text-zinc-400">The map has no data on how to obtain this item.</p>
    {/if}
    {#each sources as source (source.row.acquisitionKey)}
        {@const fact = source.row.provenance}
        <div class="space-y-1 border-t border-zinc-700 pt-2" data-acquisition-key={fact.acquisition_key} data-origin-item={fact.item_stable_key}
            data-presentation={source.presentation} data-acquisition-keys={JSON.stringify(source.members.map((member) => member.acquisitionKey))}
            data-origin-items={JSON.stringify(source.members.map((member) => member.originatingItemStableKey))}>
            <div class="text-zinc-500">{labels[fact.kind] ?? fact.kind.replaceAll('_', ' ')}</div>
            <div class="flex items-center gap-1 text-zinc-200">{source.presentation === 'any_water' ? 'Any water' : source.row.sourceName}<WikiLink pageName={source.row.sourceWikiPageName} /></div>
            {#if source.row.price !== null}<p class="text-zinc-400">{source.row.price.toLocaleString()} gold</p>{/if}
            {#if fact.kind === 'auction_house'}<p class="text-zinc-400">May be listed by simulated players. Stock is random.</p>{/if}
            {#if probabilityText(fact)}<p class="text-zinc-400">{probabilityText(fact)}</p>{/if}
            <p class="text-zinc-400">{quantityText(fact)}</p>
            {#if source.presentation !== 'any_water'}
            {#each conditionLines(fact.conditions, source.row.referenceNames) as condition, index (index)}<p class="text-zinc-300">{condition}</p>{/each}
            {#each fact.locations.filter((location) => conditionsSatisfiable([...fact.conditions, ...location.conditions])) as location (location.location_key)}
                {@const marker = source.markers.find((candidate) => candidate.stableKey === location.coordinate_stable_key)}
                {@const locationSource = location.source_copy_stable_key ? source.row.locationSources[location.source_copy_stable_key] : undefined}
                <div class="space-y-1 text-zinc-400">
                    {#if locationSource && locationSource.name !== source.row.sourceName}
                        <div class="flex items-center gap-1 text-zinc-300">{fact.kind === 'quest_reward' ? 'Turn in to ' : ''}{locationSource.name}<WikiLink pageName={locationSource.wikiPageName} /></div>
                    {/if}
                    {#if marker}
                        <button type="button" onclick={() => onFocusSpawn(marker.stableKey)}
                            onmouseenter={() => onHoverSpawn(marker.stableKey)} onmouseleave={() => onHoverSpawn(null)}
                            class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left hover:bg-zinc-700/50 hover:text-white">
                            <span>{marker.zoneName}{location.relation === 'possible_treasure' ? ' - Possible treasure hunt' : ''}</span><Crosshair class="h-3.5 w-3.5" />
                        </button>
                    {:else}
                        <p>{location.scene ? `${source.row.referenceNames[location.zone_stable_key ?? ''] ?? location.scene} - ` : ''}{location.x !== null && location.z !== null ? `X ${location.x}, Z ${location.z}` : 'Location unknown'}</p>
                    {/if}
                    {#if location.player_level_min !== null || location.player_level_max !== null}
                        <p>Player level {location.player_level_min ?? '?'} to {location.player_level_max ?? '?'}</p>
                    {/if}
                    {#each conditionLines(location.conditions, source.row.referenceNames) as condition, index (index)}<p>{condition}</p>{/each}
                    {#each location.entry_zone_line_keys as key (key)}
                        {@const entrance = source.entries.find((entry) => entry.stableKey === key)}
                        {#if entrance}
                            <button type="button" class="text-zinc-300 hover:text-white" onclick={() => onFocusSpawn(entrance.stableKey)}
                                onmouseenter={() => onHoverSpawn(entrance.stableKey)} onmouseleave={() => onHoverSpawn(null)}>
                                {entrance.destinationContext ? entrance.destinationZoneName : `Enter from ${entrance.zoneName} through ${entrance.destinationZoneName}`}
                            </button>
                        {:else}<p>Entrance location unknown</p>{/if}
                    {/each}
                </div>
            {:else}
                <p class="text-zinc-400">Location unknown</p>
            {/each}
            {/if}
        </div>
    {/each}
</div>
