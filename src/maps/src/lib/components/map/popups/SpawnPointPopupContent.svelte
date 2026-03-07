<script lang="ts">
    import { SvelteMap } from 'svelte/reactivity';
    import type { WorldEnemy, WorldNpc, SpawnCharacter } from '$lib/types/world-map';
    import type { CharacterDrop, VendorItem } from '$lib/map-markers';
    import { Repository } from '$lib/database.default';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        marker: WorldEnemy | WorldNpc;
    }

    let { marker }: Props = $props();

    let characterDrops = new SvelteMap<string, CharacterDrop[]>();
    let characterVendorItems = new SvelteMap<string, VendorItem[]>();
    let isLoading = $state(true);
    let loadError = $state<string | null>(null);

    // Load drops and vendor items when component mounts
    $effect(() => {
        if (marker.characters.length > 0) {
            loadData();
        } else {
            isLoading = false;
        }
    });

    async function loadData() {
        isLoading = true;
        loadError = null;
        characterDrops.clear();
        characterVendorItems.clear();
        try {
            const repo = new Repository();
            await repo.init();

            for (const char of marker.characters) {
                const drops = await repo.getDropsForCharacter(char.stableKey);
                characterDrops.set(char.stableKey, drops);

                if (char.isVendor) {
                    const items = await repo.getVendorItems(char.stableKey);
                    characterVendorItems.set(char.stableKey, items);
                }
            }

            repo.close();
        } catch (err) {
            console.error('Failed to load spawn point data:', err);
            loadError = err instanceof Error ? err.message : 'Failed to load';
        } finally {
            isLoading = false;
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

    // Format spawn chance (0-100 range from database)
    function formatSpawnChance(chance: number): string {
        return `${chance.toFixed(1)}%`;
    }

    // Format vendor item price
    function formatPrice(price: number): string {
        return price.toLocaleString();
    }

    // Get rarity badge color
    function getRarityClass(char: SpawnCharacter): string {
        if (char.isUnique) return 'bg-zinc-700 text-zinc-200';
        if (char.isRare) return 'bg-red-900/50 text-red-300';
        return 'bg-blue-900/50 text-blue-300';
    }

    // Get rarity label
    function getRarityLabel(char: SpawnCharacter): string {
        if (char.isUnique) return 'Unique';
        if (char.isRare) return 'Rare';
        return 'Common';
    }

    // Sort characters by rarity (unique > rare > common)
    const sortedCharacters = $derived(
        [...marker.characters].sort((a, b) => {
            if (a.isUnique !== b.isUnique) return a.isUnique ? -1 : 1;
            if (a.isRare !== b.isRare) return a.isRare ? -1 : 1;
            return 0;
        })
    );
</script>

<div class="space-y-4">
    <!-- Spawn Info -->
    <div class="space-y-1">
        {#if marker.isNightSpawn}
            <div class="flex items-center gap-1.5 text-sm text-zinc-300">
                <span>Night spawn (23:00-7:00)</span>
            </div>
        {/if}
        <div class="text-xs text-zinc-400">
            Respawns {formatRespawnTime(marker.spawnDelay)}
        </div>
        {#if !marker.isEnabled}
            <div class="text-xs text-amber-400">(Initially) Disabled</div>
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

    <!-- Characters -->
    <div class="space-y-3">
        {#each sortedCharacters as char (char.stableKey)}
            <div class="rounded bg-zinc-800 p-3">
                <!-- Character header -->
                <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0 flex-1">
                        <div class="font-medium text-white">{char.name}</div>
                        <div class="text-xs text-zinc-400">
                            Level {char.level} &bull; {formatSpawnChance(char.spawnChance)} spawn
                        </div>
                    </div>
                    <div class="flex flex-col items-end gap-1 shrink-0">
                        <span class="rounded px-1.5 py-0.5 text-xs {getRarityClass(char)}">
                            {getRarityLabel(char)}
                        </span>
                        <WikiLink name={char.name} />
                    </div>
                </div>

                <!-- Vendor Items -->
                {#if isLoading && char.isVendor}
                    <div class="mt-2 text-xs text-zinc-500">Loading items...</div>
                {:else if characterVendorItems.has(char.stableKey)}
                    {@const items = characterVendorItems.get(char.stableKey) || []}
                    {#if items.length > 0}
                        <div class="mt-2 border-t border-zinc-700 pt-2">
                            <div class="text-xs text-zinc-500 uppercase tracking-wide mb-1">
                                Sells
                            </div>
                            <div class="space-y-0.5">
                                {#each items as item, i (i)}
                                    <div class="flex justify-between text-xs">
                                        <span class="text-zinc-300 truncate min-w-0"
                                            >{item.name}</span
                                        >
                                        <span class="text-zinc-500 shrink-0 ml-2">
                                            {formatPrice(item.price)}
                                        </span>
                                    </div>
                                {/each}
                            </div>
                        </div>
                    {/if}
                {/if}

                <!-- Drops -->
                {#if isLoading}
                    <div class="mt-2 text-xs text-zinc-500">Loading drops...</div>
                {:else if loadError}
                    <div class="mt-2 text-xs text-red-400">Error: {loadError}</div>
                {:else if characterDrops.has(char.stableKey)}
                    {@const drops = characterDrops.get(char.stableKey) || []}
                    {#if drops.length > 0}
                        <div class="mt-2 border-t border-zinc-700 pt-2">
                            <div class="text-xs text-zinc-500 uppercase tracking-wide mb-1">
                                Drops
                            </div>
                            <div class="space-y-0.5">
                                {#each drops as drop, i (i)}
                                    <div class="flex justify-between text-xs">
                                        <span class="text-zinc-300">{drop.itemName}</span>
                                        <span class="text-zinc-500"
                                            >{formatDropChance(drop.dropProbability)}</span
                                        >
                                    </div>
                                {/each}
                            </div>
                        </div>
                    {/if}
                {/if}
            </div>
        {/each}
    </div>
</div>
