<script lang="ts">
    import { onMount } from 'svelte';
    import type { EntityData } from '$lib/map/live/types';
    import { Repository } from '$lib/database.default';
    import type { CharacterDrop } from '$lib/map-markers';

    interface Props {
        entity: EntityData;
    }

    let { entity }: Props = $props();

    let drops = $state<CharacterDrop[] | null>(null);
    let dropsLoading = $state(true);
    let characterStableKey = $state<string | null>(null);

    onMount(async () => {
        // Try to find character in database by NPCName
        const db = new Repository();
        await db.init();

        try {
            const result = await db.getCharacterByName(entity.name);

            if (result) {
                characterStableKey = result.stableKey;

                // Load drops
                drops = await db.getDropsForCharacter(characterStableKey);
            }
        } catch (err) {
            console.error('Failed to load character data:', err);
        } finally {
            dropsLoading = false;
        }
    });

    const wikiUrl = $derived(
        characterStableKey
            ? `https://erenshor.wiki/${encodeURIComponent(entity.name.replace(/ /g, '_'))}`
            : null
    );

    const [x, y] = entity.position;
</script>

<div class="space-y-4">
    <!-- Live Entity Info -->
    <div class="space-y-2">
        <h3 class="text-sm font-semibold text-gray-300">Live Entity Info</h3>
        <div class="space-y-1 text-sm">
            {#if entity.level}
                <div class="flex justify-between">
                    <span class="text-gray-400">Level:</span>
                    <span class="text-white">{entity.level}</span>
                </div>
            {/if}
            {#if entity.rarity}
                <div class="flex justify-between">
                    <span class="text-gray-400">Rarity:</span>
                    <span class="text-white capitalize">{entity.rarity}</span>
                </div>
            {/if}
            <div class="flex justify-between">
                <span class="text-gray-400">Position:</span>
                <span class="text-white font-mono text-xs">{x.toFixed(1)}, {y.toFixed(1)}</span>
            </div>
        </div>

        {#if wikiUrl}
            <a
                href={wikiUrl}
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300 hover:underline"
            >
                View on Wiki
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                </svg>
            </a>
        {/if}
    </div>

    <!-- Drops Section -->
    {#if dropsLoading}
        <div class="space-y-2">
            <h3 class="text-sm font-semibold text-gray-300">Drops</h3>
            <p class="text-sm text-gray-400">Loading...</p>
        </div>
    {:else if drops && drops.length > 0}
        <div class="space-y-2">
            <h3 class="text-sm font-semibold text-gray-300">Drops</h3>
            <div class="space-y-1">
                {#each drops as drop (drop.itemName)}
                    <div class="flex justify-between text-sm">
                        <span class="text-white">{drop.itemName}</span>
                        <span class="text-gray-400">{(drop.dropProbability * 100).toFixed(1)}%</span
                        >
                    </div>
                {/each}
            </div>
        </div>
    {:else if characterStableKey}
        <div class="space-y-2">
            <h3 class="text-sm font-semibold text-gray-300">Drops</h3>
            <p class="text-sm text-gray-400">No drops found</p>
        </div>
    {/if}
</div>
