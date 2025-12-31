<script lang="ts">
    import type { WorldZoneLine } from '$lib/types/world-map';

    interface Props {
        marker: WorldZoneLine;
    }

    let { marker }: Props = $props();

    // Format level range for display
    const formattedLevelRange = $derived(() => {
        const range = marker.destinationEnemyInfo.levelRange;
        if (!range) return null;
        return `${range.min} - ${range.max}`;
    });
</script>

<div class="space-y-3">
    <!-- Destination -->
    <div class="rounded bg-zinc-800 px-3 py-2">
        <div class="text-xs text-zinc-500 uppercase tracking-wide">Destination</div>
        <div class="text-sm font-medium text-purple-400">{marker.destinationZoneName}</div>
    </div>

    <!-- Enemy Level Range -->
    {#if formattedLevelRange()}
        <div class="rounded bg-zinc-800 px-3 py-2">
            <div class="text-xs text-zinc-500 uppercase tracking-wide">Enemy Levels</div>
            <div class="text-sm font-medium text-zinc-300">{formattedLevelRange()}</div>
        </div>
    {/if}

    <!-- Warning if disabled -->
    {#if !marker.isEnabled}
        <div class="text-xs text-amber-400">(Initially) Disabled</div>
    {/if}
</div>
