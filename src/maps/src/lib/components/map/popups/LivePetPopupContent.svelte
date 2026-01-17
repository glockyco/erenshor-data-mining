<script lang="ts">
    import type { EntityData } from '$lib/map/live/types';

    interface Props {
        entity: EntityData;
    }

    let { entity }: Props = $props();
</script>

<div class="space-y-3">
    {#if entity.owner}
        <div class="text-sm text-zinc-400">Belongs to {entity.owner}</div>
    {/if}
</div>
