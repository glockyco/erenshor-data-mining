<script lang="ts">
    import type { EntityData } from '$lib/map/live/types';

    interface Props {
        entity: EntityData;
    }

    let { entity }: Props = $props();
</script>

<div class="space-y-3">
    <div class="flex items-center justify-between">
        {#if entity.level}
            <div class="text-sm text-zinc-300">Level {entity.level}</div>
        {/if}
        {#if entity.characterClass}
            <div class="text-sm text-zinc-300">{entity.characterClass}</div>
        {/if}
    </div>
</div>
