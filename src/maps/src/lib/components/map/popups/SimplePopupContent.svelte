<script lang="ts">
    import type {
        AnyWorldMarker,
        WorldDoor,
        WorldItemBag,
        WorldTeleport,
        WorldSecretPassage,
        WorldAchievementTrigger
    } from '$lib/types/world-map';
    import WikiLink from '$lib/components/map/WikiLink.svelte';

    interface Props {
        marker: AnyWorldMarker;
    }

    let { marker }: Props = $props();

    // Get passage type display name
    function getPassageTypeName(passageType: string): string {
        const typeMap: Record<string, string> = {
            HiddenDoor: 'Hidden Door',
            IllusoryWall: 'Illusory Wall',
            InvisibleFloor: 'Invisible Floor'
        };
        return typeMap[passageType] || passageType;
    }
</script>

{#if marker.category === 'forge'}
    <div class="space-y-2">
        <div class="text-sm text-zinc-300">A forge you can craft at.</div>
        <WikiLink name="Forge" />
    </div>
{:else if marker.category === 'wishing-well'}
    <div class="space-y-2">
        <div class="text-sm text-zinc-300">A wishing well you can set your respawn point at.</div>
        <WikiLink name="Wishing_Well" />
    </div>
{:else if marker.category === 'treasure-loc'}
    <div class="space-y-2">
        <div class="text-sm text-zinc-300">A location where treasure can be found.</div>
        <WikiLink name="Treasure_Hunting" />
    </div>
{:else if marker.category === 'achievement-trigger'}
    {@const m = marker as WorldAchievementTrigger}
    <div class="space-y-2">
        <div class="text-sm text-zinc-300">Visit this location to unlock the achievement.</div>
        <div class="rounded bg-zinc-800 px-3 py-2">
            <div class="flex items-center justify-between">
                <div class="text-sm font-medium text-pink-400">{m.achievementName}</div>
                <WikiLink name="Achievements" />
            </div>
        </div>
    </div>
{:else if marker.category === 'door'}
    {@const m = marker as WorldDoor}
    <div class="space-y-2">
        <div class="text-sm text-zinc-300">This door requires a key to open.</div>
        <div class="rounded bg-zinc-800 px-3 py-2">
            <div class="text-xs text-zinc-500 uppercase tracking-wide">Required Key</div>
            <div class="flex items-center justify-between">
                <div class="text-sm font-medium text-amber-400">{m.keyItemName}</div>
                <WikiLink name={m.keyItemName} />
            </div>
        </div>
    </div>
{:else if marker.category === 'item-bag'}
    {@const m = marker as WorldItemBag}
    <div class="rounded bg-zinc-800 px-3 py-2">
        <div class="text-xs text-zinc-500 uppercase tracking-wide">Contains</div>
        <div class="flex items-center justify-between">
            <div class="text-sm font-medium text-orange-400">{m.itemName}</div>
            <WikiLink name={m.itemName} />
        </div>
    </div>
{:else if marker.category === 'teleport'}
    {@const m = marker as WorldTeleport}
    <div class="space-y-2">
        <div class="text-sm text-zinc-300">Use a teleport item to travel to this location.</div>
        <div class="rounded bg-zinc-800 px-3 py-2">
            <div class="text-xs text-zinc-500 uppercase tracking-wide">Teleport Item</div>
            <div class="flex items-center justify-between">
                <div class="text-sm font-medium text-violet-400">{m.teleportItemName}</div>
                <WikiLink name={m.teleportItemName} />
            </div>
        </div>
    </div>
{:else if marker.category === 'secret-passage'}
    {@const m = marker as WorldSecretPassage}
    <div class="space-y-2">
        <div class="rounded bg-zinc-800 px-3 py-2">
            <div class="text-xs text-zinc-500 uppercase tracking-wide">Type</div>
            <div class="text-sm font-medium text-violet-300">
                {getPassageTypeName(m.passageType)}
            </div>
        </div>
        <div class="text-sm text-zinc-300">
            {#if m.passageType === 'HiddenDoor'}
                A hidden door you can click to open.
            {:else if m.passageType === 'IllusoryWall'}
                An illusory wall you can walk through.
            {:else if m.passageType === 'InvisibleFloor'}
                An invisible floor you can walk on.
            {:else}
                A hidden passage is concealed here.
            {/if}
        </div>
    </div>
{:else}
    <div class="text-sm text-zinc-400">No additional information available.</div>
{/if}
