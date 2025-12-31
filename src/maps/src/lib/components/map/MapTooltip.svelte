<script lang="ts">
    import type {
        AnyMapMarker,
        EnemyMarker,
        NpcMarker,
        ZoneLineMarker,
        DoorMarker,
        ItemBagMarker,
        TeleportMarker,
        SecretPassageMarker,
        AchievementTriggerMarker
    } from '$lib/types/map';
    import { calculateTooltipPosition } from '$lib/utils/tooltip';

    interface Props {
        marker: AnyMapMarker;
        x: number;
        y: number;
        zoneName: string;
    }

    let { marker, x, y, zoneName }: Props = $props();

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

    // Get border color based on marker category
    function getBorderColorClass(): string {
        switch (marker.category) {
            case 'enemy': {
                const m = marker as EnemyMarker;
                if (m.isUnique) return 'border-l-zinc-900';
                if (m.isRare) return 'border-l-red-500';
                return 'border-l-blue-500';
            }
            case 'npc':
                return 'border-l-green-500';
            case 'zone-line':
                return 'border-l-purple-500';
            case 'door':
                return 'border-l-amber-700';
            case 'item-bag':
                return 'border-l-orange-500';
            case 'mining-node':
                return 'border-l-gray-500';
            case 'teleport':
                return 'border-l-violet-500';
            case 'secret-passage':
                return 'border-l-violet-400';
            case 'achievement-trigger':
                return 'border-l-pink-500';
            case 'forge':
                return 'border-l-orange-600';
            case 'wishing-well':
                return 'border-l-cyan-500';
            case 'treasure-loc':
                return 'border-l-yellow-500';
            case 'water':
                return 'border-l-sky-400';
            default:
                return 'border-l-gray-500';
        }
    }

    // Format respawn time
    function formatRespawnTime(seconds: number | null): string {
        if (seconds === null || seconds === 0) return '';
        const minutes = Math.round(seconds / 60);
        if (minutes < 1) return `${seconds}s`;
        return `${minutes}m`;
    }

    type TooltipContent = { name: string; detail: string; warning?: string };

    // Get enemy spawn tooltip content
    function getEnemyContent(m: EnemyMarker): TooltipContent {
        const chars = m.characters;
        if (chars.length === 0) {
            return { name: 'Empty Spawn', detail: '' };
        }

        // Sort by rarity: unique > rare > common
        const sorted = [...chars].sort((a, b) => {
            if (a.isUnique !== b.isUnique) return a.isUnique ? -1 : 1;
            if (a.isRare !== b.isRare) return a.isRare ? -1 : 1;
            return 0;
        });

        const rarest = sorted[0];
        const rarestRarity = rarest.isUnique ? 'Unique' : rarest.isRare ? 'Rare' : '';
        const respawn = formatRespawnTime(m.spawnDelay);
        const night = m.isNightSpawn ? '🌙 23:00-7:00' : '';
        const warning = !m.isEnabled ? '(Initially) Disabled' : undefined;

        if (chars.length === 1) {
            const parts = [rarestRarity, night, respawn].filter(Boolean);
            return {
                name: rarest.name,
                detail: parts.join(' • '),
                warning
            };
        }

        // Multiple enemies - show rarest + count
        const others = chars.length - 1;
        const parts = [rarestRarity, `+${others} more`, night, respawn].filter(Boolean);
        return {
            name: rarest.name,
            detail: parts.join(' • '),
            warning
        };
    }

    // Get NPC tooltip content
    function getNpcContent(m: NpcMarker): TooltipContent {
        const night = m.isNightSpawn ? '🌙 23:00-7:00' : '';
        const parts = ['NPC', night].filter(Boolean);
        return {
            name: m.name,
            detail: parts.join(' • '),
            warning: !m.isEnabled ? '(Initially) Disabled' : undefined
        };
    }

    // Get zone line tooltip content
    function getZoneLineContent(m: ZoneLineMarker): TooltipContent {
        return {
            name: `→ ${m.destinationZoneName}`,
            detail: 'Zone Connection',
            warning: !m.isEnabled ? '(Initially) Disabled' : undefined
        };
    }

    // Get door tooltip content
    function getDoorContent(m: DoorMarker): TooltipContent {
        return {
            name: 'Locked Door',
            detail: `Key: ${m.keyItemName}`
        };
    }

    // Get item bag tooltip content
    function getItemBagContent(m: ItemBagMarker): TooltipContent {
        return {
            name: m.itemName,
            detail: 'Item Bag'
        };
    }

    // Get teleport tooltip content
    function getTeleportContent(m: TeleportMarker): TooltipContent {
        return {
            name: 'Teleport Point',
            detail: `Via: ${m.teleportItemName}`
        };
    }

    // Get secret passage tooltip content
    function getSecretPassageContent(m: SecretPassageMarker): TooltipContent {
        const typeMap: Record<string, string> = {
            HiddenDoor: 'Hidden Door',
            IllusoryWall: 'Illusory Wall',
            InvisibleFloor: 'Invisible Floor'
        };
        return {
            name: typeMap[m.passageType] || 'Secret Passage',
            detail: ''
        };
    }

    // Get achievement tooltip content
    function getAchievementContent(m: AchievementTriggerMarker): TooltipContent {
        return {
            name: m.achievementName,
            detail: 'Achievement'
        };
    }

    // Get tooltip content based on marker type
    function getTooltipContent(): TooltipContent {
        switch (marker.category) {
            case 'enemy':
                return getEnemyContent(marker as EnemyMarker);
            case 'npc':
                return getNpcContent(marker as NpcMarker);
            case 'zone-line':
                return getZoneLineContent(marker as ZoneLineMarker);
            case 'door':
                return getDoorContent(marker as DoorMarker);
            case 'item-bag':
                return getItemBagContent(marker as ItemBagMarker);
            case 'mining-node':
                return { name: 'Mining Node', detail: '' };
            case 'teleport':
                return getTeleportContent(marker as TeleportMarker);
            case 'secret-passage':
                return getSecretPassageContent(marker as SecretPassageMarker);
            case 'achievement-trigger':
                return getAchievementContent(marker as AchievementTriggerMarker);
            case 'forge':
                return { name: 'Forge', detail: 'Crafting Station' };
            case 'wishing-well':
                return { name: 'Wishing Well', detail: 'Set Respawn Point' };
            case 'treasure-loc':
                return { name: 'Treasure Location', detail: '' };
            case 'water':
                return { name: 'Fishing Spot', detail: '' };
            default:
                return { name: 'Unknown', detail: '' };
        }
    }

    const content = $derived(getTooltipContent());
    const borderColorClass = $derived(getBorderColorClass());
</script>

<div
    bind:this={tooltipRef}
    class="pointer-events-none fixed z-50 max-w-xs rounded-lg border border-l-[3px] {borderColorClass} border-zinc-700 bg-zinc-900/95 px-3 py-2 shadow-lg backdrop-blur"
    style="left: {position.left}px; top: {position.top}px;"
>
    <div class="text-sm font-medium text-white">{content.name}</div>
    {#if content.detail}
        <div class="text-xs text-zinc-400">{content.detail}</div>
    {/if}
    {#if content.warning}
        <div class="text-xs text-amber-400">{content.warning}</div>
    {/if}
    <div class="text-xs text-zinc-500">{zoneName}</div>
</div>
