<script lang="ts">
    import type { WorldEnemy, WorldNpc, SpawnCharacter } from '$lib/types/world-map';
    import { compareEncounterTier, formatSpawnLevels, isFurnishingSpawn } from '$lib/map-markers';
    import type { CharacterDetails } from '$lib/map/character-details';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        marker: WorldEnemy | WorldNpc;
        characterDetails: CharacterDetails;
    }

    let { marker, characterDetails }: Props = $props();

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
    function formatSpawnChance(chance: number | null): string {
        if (chance === null) return 'Event spawn';
        return `${chance.toFixed(1)}% spawn`;
    }

    function formatSpawnSource(char: SpawnCharacter): string {
        if (!char.sourceScript) return formatSpawnChance(char.spawnChance);
        return formatSpawnChance(null);
    }

    // Format vendor item price
    function formatPrice(price: number): string {
        return price.toLocaleString();
    }

    function getTierClass(char: SpawnCharacter): string {
        if (char.encounterTier === 'boss') return 'bg-zinc-700 text-zinc-200';
        if (char.encounterTier === 'elite') return 'bg-red-900/50 text-red-300';
        if (char.encounterTier === 'chest') return 'bg-teal-900/50 text-teal-300';
        return 'bg-blue-900/50 text-blue-300';
    }

    const sortedCharacters = $derived(
        [...marker.characters].sort((a, b) => compareEncounterTier(a.encounterTier, b.encounterTier))
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
        {#if !marker.isEnabled && !isFurnishingSpawn(marker.characters)}
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
            {@const drops = characterDetails.drops.get(char.stableKey) ?? []}
            <div class="rounded bg-zinc-800 p-3">
                <!-- Character header -->
                <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0 flex-1">
                        <div class="font-medium text-white">{char.name}</div>
                        <div class="text-xs text-zinc-400">
                            {formatSpawnLevels([char])} &bull; {formatSpawnSource(char)}
                        </div>
                        {#if char.furniture}
                            <div class="text-xs text-zinc-400">
                                Appears when the player places the
                                {#if char.furniture.wikiPageName}
                                    <a
                                        class="text-blue-400 hover:underline"
                                        href="https://erenshor.wiki.gg/wiki/{encodeURIComponent(
                                            char.furniture.wikiPageName
                                        )}">{char.furniture.name}</a
                                    >
                                {:else}{char.furniture.name}{/if} in this room.
                            </div>
                        {/if}
                    </div>
                    <div class="flex flex-col items-end gap-1 shrink-0">
                        <span class="rounded px-1.5 py-0.5 text-xs {getTierClass(char)}">
                            {char.encounterTier === 'npc' ? 'NPC' : char.encounterTier === 'boss' ? 'Boss' : char.encounterTier === 'elite' ? 'Elite' : char.encounterTier === 'chest' ? 'Chest' : 'Enemy'}
                        </span>
                        <WikiLink pageName={char.wikiPageName} />
                    </div>
                </div>

                <!-- Vendor Items -->
                {#if char.isVendor}
                    {@const items = characterDetails.vendorItems.get(char.stableKey) ?? []}
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
                                            {formatPrice(item.price)} gold
                                        </span>
                                    </div>
                                {/each}
                            </div>
                        </div>
                    {/if}
                {/if}

                <!-- Drops -->
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
            </div>
        {/each}
    </div>
</div>
