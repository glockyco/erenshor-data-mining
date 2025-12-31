<script lang="ts">
    import type { ZoneWorldPosition } from '$lib/types/world-map';
    import { calculateTooltipPosition } from '$lib/utils/tooltip';

    interface Props {
        zone: ZoneWorldPosition;
        x: number;
        y: number;
    }

    let { zone, x, y }: Props = $props();

    // Track tooltip dimensions for positioning
    let tooltipRef: HTMLDivElement | null = $state(null);
    let tooltipWidth = $state(200);
    let tooltipHeight = $state(80);

    $effect(() => {
        if (tooltipRef) {
            tooltipWidth = tooltipRef.offsetWidth;
            tooltipHeight = tooltipRef.offsetHeight;
        }
    });

    let position = $derived(calculateTooltipPosition(x, y, tooltipWidth, tooltipHeight));

    // Get enemy info
    const enemyInfo = $derived(zone.enemyInfo);

    // Format level range
    const levelRange = $derived(() => {
        const range = enemyInfo?.levelRange;
        if (!range) return null;
        return `${range.min} - ${range.max}`;
    });

    // Format notable enemies count
    const notableCount = $derived(() => {
        if (!enemyInfo) return null;
        const uniques = enemyInfo.uniques.length;
        const rares = enemyInfo.rares.length;
        if (uniques === 0 && rares === 0) return null;
        const parts: string[] = [];
        if (uniques > 0) parts.push(`${uniques} unique${uniques > 1 ? 's' : ''}`);
        if (rares > 0) parts.push(`${rares} rare${rares > 1 ? 's' : ''}`);
        return parts.join(', ');
    });
</script>

<div
    bind:this={tooltipRef}
    class="pointer-events-none fixed z-50 max-w-xs rounded-lg border border-l-[3px] border-l-zinc-500 border-zinc-700 bg-zinc-900/95 px-3 py-2 shadow-lg backdrop-blur"
    style="left: {position.left}px; top: {position.top}px;"
>
    <div class="text-sm font-medium text-white">{zone.name}</div>
    {#if levelRange()}
        <div class="text-xs text-zinc-400">Enemies: Lv. {levelRange()}</div>
    {:else}
        <div class="text-xs text-zinc-500">No enemies</div>
    {/if}
    {#if notableCount()}
        <div class="text-xs text-zinc-400">{notableCount()}</div>
    {/if}
</div>
