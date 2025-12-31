<script lang="ts">
    import type { ZoneWorldPosition } from '$lib/types/world-map';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        zone: ZoneWorldPosition;
    }

    let { zone }: Props = $props();

    // Get enemy info
    const enemyInfo = $derived(zone.enemyInfo);

    // Format level range for display
    const formattedLevelRange = $derived(() => {
        const range = enemyInfo?.levelRange;
        if (!range) return null;
        return `${range.min} - ${range.max}`;
    });
</script>

<div class="space-y-3">
    <!-- Enemy Level Range -->
    {#if formattedLevelRange()}
        <div class="rounded bg-zinc-800 px-3 py-2">
            <div class="text-xs text-zinc-500 uppercase tracking-wide">Enemy Levels</div>
            <div class="text-sm font-medium text-zinc-300">{formattedLevelRange()}</div>
        </div>
    {:else}
        <div class="text-sm text-zinc-400">No enemies in this zone.</div>
    {/if}

    <!-- Unique Enemies -->
    {#if enemyInfo && enemyInfo.uniques.length > 0}
        <div class="rounded bg-zinc-800 p-3">
            <div class="text-xs text-zinc-500 uppercase tracking-wide mb-2">Uniques</div>
            <div class="space-y-1.5">
                {#each enemyInfo.uniques as enemy, i (i)}
                    <div class="flex items-center justify-between gap-2 text-sm">
                        <span class="text-zinc-300 truncate min-w-0">{enemy.name}</span>
                        <div class="flex items-center gap-2 shrink-0">
                            <span class="text-zinc-500">Lv. {enemy.level}</span>
                            <WikiLink name={enemy.name} />
                        </div>
                    </div>
                {/each}
            </div>
        </div>
    {/if}

    <!-- Rare Enemies -->
    {#if enemyInfo && enemyInfo.rares.length > 0}
        <div class="rounded bg-zinc-800 p-3">
            <div class="text-xs text-zinc-500 uppercase tracking-wide mb-2">Rares</div>
            <div class="space-y-1.5">
                {#each enemyInfo.rares as enemy, i (i)}
                    <div class="flex items-center justify-between gap-2 text-sm">
                        <span class="text-zinc-300 truncate min-w-0">{enemy.name}</span>
                        <div class="flex items-center gap-2 shrink-0">
                            <span class="text-zinc-500">Lv. {enemy.level}</span>
                            <WikiLink name={enemy.name} />
                        </div>
                    </div>
                {/each}
            </div>
        </div>
    {/if}
</div>
