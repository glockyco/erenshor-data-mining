<script lang="ts">
    import type { WorldWater } from '$lib/types/world-map';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        marker: WorldWater;
    }

    let { marker }: Props = $props();

    // Format drop chance (0-100 range from database)
    function formatDropChance(chance: number): string {
        return `${chance.toFixed(1)}%`;
    }

    // Check if day and night items are the same
    const sameItems = $derived(() => {
        if (marker.daytimeItems.length !== marker.nighttimeItems.length) return false;
        for (let i = 0; i < marker.daytimeItems.length; i++) {
            const day = marker.daytimeItems[i];
            const night = marker.nighttimeItems[i];
            if (day.name !== night.name || day.dropChance !== night.dropChance) {
                return false;
            }
        }
        return true;
    });
</script>

<div class="space-y-3">
    {#if sameItems() || marker.nighttimeItems.length === 0}
        <!-- Single list if items are the same -->
        {#if marker.daytimeItems.length > 0}
            <div class="rounded bg-zinc-800 p-3">
                <div class="text-xs text-zinc-500 uppercase tracking-wide mb-2">Catchable Fish</div>
                <div class="space-y-1.5">
                    {#each marker.daytimeItems as item, i (i)}
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-zinc-300">{item.name}</span>
                            <div class="flex items-center gap-2">
                                <span class="text-zinc-500"
                                    >{formatDropChance(item.dropChance)}</span
                                >
                                <WikiLink pageName={item.wikiPageName} />
                            </div>
                        </div>
                    {/each}
                </div>
            </div>
        {:else}
            <div class="text-sm text-zinc-400">No fish data available.</div>
        {/if}
    {:else}
        <!-- Separate day/night sections -->
        {#if marker.daytimeItems.length > 0}
            <div class="rounded bg-zinc-800 p-3">
                <div class="text-xs text-zinc-500 uppercase tracking-wide mb-2">
                    Daytime (7:00-23:00)
                </div>
                <div class="space-y-1.5">
                    {#each marker.daytimeItems as item, i (i)}
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-zinc-300">{item.name}</span>
                            <div class="flex items-center gap-2">
                                <span class="text-zinc-500"
                                    >{formatDropChance(item.dropChance)}</span
                                >
                                <WikiLink pageName={item.wikiPageName} />
                            </div>
                        </div>
                    {/each}
                </div>
            </div>
        {/if}

        {#if marker.nighttimeItems.length > 0}
            <div class="rounded bg-zinc-800 p-3">
                <div class="text-xs text-zinc-500 uppercase tracking-wide mb-2">
                    Nighttime (23:00-7:00)
                </div>
                <div class="space-y-1.5">
                    {#each marker.nighttimeItems as item, i (i)}
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-zinc-300">{item.name}</span>
                            <div class="flex items-center gap-2">
                                <span class="text-zinc-500"
                                    >{formatDropChance(item.dropChance)}</span
                                >
                                <WikiLink pageName={item.wikiPageName} />
                            </div>
                        </div>
                    {/each}
                </div>
            </div>
        {/if}
    {/if}
</div>
