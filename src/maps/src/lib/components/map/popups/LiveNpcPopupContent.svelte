<script lang="ts">
    import type { EntityData } from '$lib/map/live/types';
    import { liveState } from '$lib/map/live/stores.svelte';
    import { aggregateDropVariants, type AggregatedDrop } from '$lib/map/live/drop-variants';
    import { Repository } from '$lib/database.default';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        entity: EntityData;
    }

    let { entity }: Props = $props();

    let drops = $state<AggregatedDrop[]>([]);
    let variantCount = $state(0);
    let isLoadingDrops = $state(true);

    $effect(() => {
        loadData();
    });

    async function loadData() {
        isLoadingDrops = true;
        try {
            const repo = new Repository();
            await repo.init();

            // The game tells us a name and a scene, never a stable key, and a
            // name can belong to several characters with different loot. Prefer
            // the variants actually placed in this scene, and fall back to every
            // match when none is placed here, which is what a dynamically
            // spawned character looks like.
            const matches = await repo.getCharactersByName(entity.name, liveState.zone);
            const placed = matches.filter((match) => match.inScene);
            const candidates = placed.length > 0 ? placed : matches;

            const byCharacter = await repo.getDropsForCharacters(
                candidates.map((candidate) => candidate.stableKey)
            );
            drops = aggregateDropVariants([...byCharacter.values()]);
            variantCount = candidates.length;

            repo.close();
        } catch (err) {
            console.error('Failed to load NPC data:', err);
        } finally {
            isLoadingDrops = false;
        }
    }

    // A range wherever the candidates disagree, so the popup never states a
    // chance that none of them actually has.
    function formatDropChance(drop: AggregatedDrop): string {
        if (drop.minProbability === drop.maxProbability) {
            return `${drop.maxProbability.toFixed(1)}%`;
        }
        return `${drop.minProbability.toFixed(1)}\u2013${drop.maxProbability.toFixed(1)}%`;
    }

    function getRarityClass(): string {
        if (entity.rarity === 'boss') return 'bg-zinc-700 text-zinc-200';
        if (entity.rarity === 'rare') return 'bg-red-900/50 text-red-300';
        return 'bg-blue-900/50 text-blue-300';
    }

    function getRarityLabel(): string {
        if (entity.rarity === 'boss') return 'Boss';
        if (entity.rarity === 'rare') return 'Rare';
        return 'Common';
    }
</script>

<div class="space-y-3">
    <!-- Rarity Badge and Wiki Link -->
    <div class="flex items-center justify-between">
        {#if entity.rarity && entity.entityType === 'npc_enemy'}
            <span class="rounded px-1.5 py-0.5 text-xs {getRarityClass()}">
                {getRarityLabel()}
            </span>
        {:else}
            <div></div>
        {/if}
        <WikiLink pageName={entity.name} />
    </div>

    <!-- Drops -->
    {#if isLoadingDrops}
        <div class="text-xs text-zinc-500">Loading drops...</div>
    {:else if drops.length > 0}
        <div class="rounded bg-zinc-800 p-3">
            <div class="mb-2 text-xs uppercase tracking-wide text-zinc-500">Drops</div>
            {#if variantCount > 1}
                <div class="mb-2 text-xs text-zinc-400">
                    {variantCount} characters share this name and drop different things. Showing
                    everything any of them can drop.
                </div>
            {/if}
            <div class="space-y-1.5">
                {#each drops as drop (drop.itemName)}
                    <div class="flex items-center justify-between text-sm">
                        <span class="min-w-0 truncate text-zinc-300">{drop.itemName}</span>
                        <div class="flex shrink-0 items-center gap-2">
                            <span class="text-zinc-500">{formatDropChance(drop)}</span>
                            <WikiLink pageName={drop.itemName} />
                        </div>
                    </div>
                {/each}
            </div>
        </div>
    {/if}
</div>
