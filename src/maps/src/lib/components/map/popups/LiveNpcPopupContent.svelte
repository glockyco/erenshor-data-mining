<script lang="ts">
    import type { EntityData } from '$lib/map/live/types';
    import type { CharacterDrop } from '$lib/map-markers';
    import { Repository } from '$lib/database.default';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        entity: EntityData;
    }

    let { entity }: Props = $props();

    let drops = $state<CharacterDrop[]>([]);
    let isLoadingDrops = $state(true);

    $effect(() => {
        loadData();
    });

    async function loadData() {
        isLoadingDrops = true;
        try {
            const repo = new Repository();
            await repo.init();

            const result = await repo.getCharacterByName(entity.name);

            if (result) {
                drops = await repo.getDropsForCharacter(result.stableKey);
            }

            repo.close();
        } catch (err) {
            console.error('Failed to load NPC data:', err);
        } finally {
            isLoadingDrops = false;
        }
    }

    function formatDropChance(probability: number): string {
        return `${probability.toFixed(1)}%`;
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
            <div class="space-y-1.5">
                {#each drops as drop, i (i)}
                    <div class="flex items-center justify-between text-sm">
                        <span class="min-w-0 truncate text-zinc-300">{drop.itemName}</span>
                        <div class="flex shrink-0 items-center gap-2">
                            <span class="text-zinc-500"
                                >{formatDropChance(drop.dropProbability)}</span
                            >
                            <WikiLink pageName={drop.itemName} />
                        </div>
                    </div>
                {/each}
            </div>
        </div>
    {/if}
</div>
