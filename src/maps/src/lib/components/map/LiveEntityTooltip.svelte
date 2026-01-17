<script lang="ts">
    import type { EntityData } from '$lib/map/live/types';
    import { calculateTooltipPosition } from '$lib/utils/tooltip';

    interface Props {
        entity: EntityData;
        x: number;
        y: number;
    }

    let { entity, x, y }: Props = $props();

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

    // Border color by entity type
    const borderColorClass = $derived(getBorderColor(entity.entityType));

    // Rarity badge color (for enemies)
    const rarityColorClass = $derived(
        entity.rarity === 'boss'
            ? 'text-red-400'
            : entity.rarity === 'rare'
              ? 'text-purple-400'
              : 'text-gray-400'
    );

    function getBorderColor(entityType: string): string {
        switch (entityType) {
            case 'player':
                return 'border-blue-400';
            case 'simplayer':
                return 'border-cyan-400';
            case 'pet':
                return 'border-green-400';
            case 'npc_friendly':
                return 'border-emerald-400';
            case 'npc_enemy':
                return 'border-red-400';
            default:
                return 'border-gray-400';
        }
    }

    function getEntityTypeLabel(entityType: string): string {
        switch (entityType) {
            case 'player':
                return 'Player';
            case 'simplayer':
                return 'SimPlayer';
            case 'pet':
                return 'Pet';
            case 'npc_friendly':
                return 'Friendly NPC';
            case 'npc_enemy':
                return 'Enemy';
            default:
                return 'Unknown';
        }
    }
</script>

<div class="tooltip-container" style="left: {position.left}px; top: {position.top}px;">
    <div bind:this={tooltipRef} class="tooltip-content border-l-4 {borderColorClass}">
        <div class="tooltip-title">
            {entity.name}
            {#if entity.rarity}
                <span class="rarity-badge {rarityColorClass}">
                    {entity.rarity === 'boss' ? '★' : entity.rarity === 'rare' ? '◆' : ''}
                </span>
            {/if}
        </div>
        <div class="tooltip-detail">
            {getEntityTypeLabel(entity.entityType)}
            {#if entity.level}
                • Level {entity.level}
            {/if}
        </div>
    </div>
</div>

<style>
    .tooltip-container {
        position: fixed;
        pointer-events: none;
        z-index: 50;
    }

    .tooltip-content {
        background: rgba(17, 24, 39, 0.95);
        border-radius: 0.375rem;
        padding: 0.5rem 0.75rem;
        color: white;
        font-size: 0.875rem;
        min-width: 120px;
        max-width: 250px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }

    .tooltip-title {
        font-weight: 600;
        margin-bottom: 0.25rem;
    }

    .tooltip-detail {
        font-size: 0.75rem;
        color: rgb(156, 163, 175);
    }

    .rarity-badge {
        font-weight: bold;
        margin-left: 0.25rem;
    }
</style>
