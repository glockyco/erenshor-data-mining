<script lang="ts">
    import type { WorldNpc } from '$lib/types/world-map';
    import type { CharacterDrop } from '$lib/map-markers';
    import { Repository } from '$lib/database.default';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        marker: WorldNpc;
    }

    let { marker }: Props = $props();

    // Vendor items state
    let vendorItems = $state<string[]>([]);
    let isLoadingItems = $state(true);

    // Drops state
    let drops = $state<CharacterDrop[]>([]);
    let isLoadingDrops = $state(true);

    // Load data when component mounts
    $effect(() => {
        loadData();
    });

    async function loadData() {
        isLoadingItems = true;
        isLoadingDrops = true;
        try {
            const repo = new Repository();
            await repo.init();

            // Load vendor items if vendor
            if (marker.isVendor) {
                vendorItems = await repo.getVendorItems(marker.stableKey);
            }

            // Load drops
            drops = await repo.getDropsForCharacter(marker.stableKey);

            repo.close();
        } catch (err) {
            console.error('Failed to load NPC data:', err);
        } finally {
            isLoadingItems = false;
            isLoadingDrops = false;
        }
    }

    // Format respawn time
    function formatRespawnTime(seconds: number | null): string {
        if (seconds === null || seconds === 0) return 'when re-entering the zone';
        const minutes = Math.round(seconds / 60);
        if (minutes < 1) return `after ~${seconds}s`;
        if (minutes === 1) return 'after ~1 minute';
        return `after ~${minutes} minutes`;
    }

    // Format drop chance (0-100 range from database)
    function formatDropChance(probability: number): string {
        return `${probability.toFixed(1)}%`;
    }
</script>

<div class="space-y-3">
    <!-- Wiki link and Level -->
    <div class="flex items-center justify-between">
        <div class="text-sm text-zinc-300">Level {marker.level}</div>
        <WikiLink name={marker.name} />
    </div>

    <!-- Vendor Items -->
    {#if marker.isVendor}
        {#if isLoadingItems}
            <div class="text-xs text-zinc-500">Loading items...</div>
        {:else if vendorItems.length > 0}
            <div class="rounded bg-zinc-800 p-3">
                <div class="text-xs text-zinc-500 uppercase tracking-wide mb-2">Sells</div>
                <div class="space-y-1.5">
                    {#each vendorItems as item (item)}
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-zinc-300 truncate min-w-0">{item}</span>
                            <div class="shrink-0 ml-2">
                                <WikiLink name={item} />
                            </div>
                        </div>
                    {/each}
                </div>
            </div>
        {/if}
    {/if}

    <!-- Drops -->
    {#if isLoadingDrops}
        <div class="text-xs text-zinc-500">Loading drops...</div>
    {:else if drops.length > 0}
        <div class="rounded bg-zinc-800 p-3">
            <div class="text-xs text-zinc-500 uppercase tracking-wide mb-2">Drops</div>
            <div class="space-y-1.5">
                {#each drops as drop (drop.itemName)}
                    <div class="flex items-center justify-between text-sm">
                        <span class="text-zinc-300 truncate min-w-0">{drop.itemName}</span>
                        <div class="flex items-center gap-2 shrink-0">
                            <span class="text-zinc-500"
                                >{formatDropChance(drop.dropProbability)}</span
                            >
                            <WikiLink name={drop.itemName} />
                        </div>
                    </div>
                {/each}
            </div>
        </div>
    {/if}

    <!-- Spawn Info -->
    <div class="space-y-1 text-xs text-zinc-400">
        {#if marker.isNightSpawn}
            <div>Night spawn (23:00-7:00)</div>
        {/if}
        <div>Respawns {formatRespawnTime(marker.spawnDelay)}</div>
        {#if !marker.isEnabled}
            <div class="text-amber-400">(Initially) Disabled</div>
        {/if}
    </div>

    <!-- Movement Info -->
    {#if marker.movement?.wanderRange || marker.worldPatrolWaypoints}
        <div class="space-y-1 text-xs text-zinc-400 border-t border-zinc-700 pt-2">
            {#if marker.movement?.wanderRange && marker.movement.wanderRange > 0}
                <div class="flex items-center gap-1.5">
                    <span class="inline-block w-2 h-2 rounded-full bg-blue-400"></span>
                    <span>Wanders {marker.movement.wanderRange.toFixed(0)} units</span>
                </div>
            {/if}
            {#if marker.worldPatrolWaypoints && marker.worldPatrolWaypoints.length > 0}
                <div class="flex items-center gap-1.5">
                    <span class="inline-block w-2 h-2 rounded-full bg-yellow-400"></span>
                    <span
                        >Patrols {marker.worldPatrolWaypoints.length} waypoints{marker.movement
                            ?.loopPatrol
                            ? ' (loops)'
                            : ''}</span
                    >
                </div>
            {/if}
        </div>
    {/if}
</div>
