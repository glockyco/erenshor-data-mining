<script lang="ts">
    import type { CursorCoordinates } from '$lib/map/cursor-coordinates';
    import { formatCursorCoordinates } from '$lib/map/cursor-coordinates';

    interface Props {
        coordinates: CursorCoordinates | null;
        leftPx?: number;
    }

    let { coordinates, leftPx = 24 }: Props = $props();

    const label = $derived(coordinates ? formatCursorCoordinates(coordinates) : null);
    const style = $derived(`left: ${leftPx}px;`);
</script>

{#if label}
    <div class="coordinate-readout" {style} aria-label={`Cursor coordinates: ${label}`}>
        {label}
    </div>
{/if}

<style>
    .coordinate-readout {
        position: absolute;
        bottom: 62px;
        z-index: 900;
        width: max-content;
        max-width: min(28rem, calc(100vw - 3rem));
        color: #fff;
        font-family: var(--font-mono);
        font-size: 0.72rem;
        font-weight: 700;
        line-height: 1;
        letter-spacing: 0.03em;
        pointer-events: none;
        text-shadow:
            0 1px 2px rgb(0 0 0 / 0.95),
            1px 0 1px rgb(0 0 0 / 0.9),
            -1px 0 1px rgb(0 0 0 / 0.9),
            0 -1px 1px rgb(0 0 0 / 0.9);
    }
</style>
