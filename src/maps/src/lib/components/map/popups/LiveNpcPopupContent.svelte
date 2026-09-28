<script lang="ts">
    import type { EntityData } from '$lib/map/live/types';
    import { resolveLiveEncounterTier, type EnemyTier } from '$lib/map-markers';
    import { liveState } from '$lib/map/live/stores.svelte';
    import { aggregateDropVariants, type AggregatedDrop } from '$lib/map/live/drop-variants';
    import { resolveLiveCandidates, type CharacterDetails } from '$lib/map/character-details';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        entity: EntityData;
        encounterTierByName: ReadonlyMap<string, EnemyTier>;
        characterDetails: CharacterDetails;
    }

    let { entity, encounterTierByName, characterDetails }: Props = $props();

    const candidates = $derived(
        resolveLiveCandidates(characterDetails.charactersByName, entity.name, liveState.zone)
    );
    const drops = $derived(
        aggregateDropVariants(
            candidates.map((candidate) => characterDetails.drops.get(candidate.stableKey) ?? [])
        )
    );

    // A range wherever the candidates disagree, so the popup never states a
    // chance that none of them actually has.
    function formatDropChance(drop: AggregatedDrop): string {
        if (drop.minProbability === drop.maxProbability) {
            return `${drop.maxProbability.toFixed(1)}%`;
        }
        return `${drop.minProbability.toFixed(1)}\u2013${drop.maxProbability.toFixed(1)}%`;
    }

    const tier = $derived(resolveLiveEncounterTier(entity, encounterTierByName));

    function getTierClass(): string {
        if (tier === 'boss') return 'bg-zinc-700 text-zinc-200';
        if (tier === 'elite') return 'bg-red-900/50 text-red-300';
        return 'bg-blue-900/50 text-blue-300';
    }
</script>

<div class="space-y-3">
    <!-- Encounter tier and wiki link -->
    <div class="flex items-center justify-between">
        {#if entity.entityType === 'npc_enemy'}
            <span class="rounded px-1.5 py-0.5 text-xs {getTierClass()}">
                {tier === 'boss' ? 'Boss' : tier === 'elite' ? 'Elite' : 'Enemy'}
            </span>
        {:else}
            <div></div>
        {/if}
        <WikiLink pageName={entity.name} />
    </div>

    <!-- Drops -->
    {#if drops.length > 0}
        <div class="rounded bg-zinc-800 p-3">
            <div class="mb-2 text-xs uppercase tracking-wide text-zinc-500">Drops</div>
            {#if candidates.length > 1}
                <div class="mb-2 text-xs text-zinc-400">
                    {candidates.length} characters share this name and drop different things. Showing
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
