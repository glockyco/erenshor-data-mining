<script lang="ts">
    import type { EntityData } from '$lib/map/live/types';

    interface Props {
        entity: EntityData;
        zoneName: string;
    }

    let { entity, zoneName }: Props = $props();

    const [x, y, z] = entity.position;
</script>

<div class="space-y-4">
    <div class="space-y-2">
        <h3 class="text-sm font-semibold text-gray-300">Current Location</h3>
        <div class="space-y-1 text-sm">
            <div class="flex justify-between">
                <span class="text-gray-400">Zone:</span>
                <span class="text-white">{zoneName}</span>
            </div>
            <div class="flex justify-between">
                <span class="text-gray-400">Position:</span>
                <span class="text-white font-mono text-xs"
                    >{x.toFixed(1)}, {y.toFixed(1)}, {z.toFixed(1)}</span
                >
            </div>
            <div class="flex justify-between">
                <span class="text-gray-400">Facing:</span>
                <span class="text-white">{entity.rotation.toFixed(0)}°</span>
            </div>
        </div>
    </div>
</div>
