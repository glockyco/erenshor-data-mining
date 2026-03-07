<script lang="ts">
    import type { ZoneWorldPosition } from '$lib/types/world-map';
    import PopupContainer from './PopupContainer.svelte';
    import ZonePopupContent from './popups/ZonePopupContent.svelte';

    interface Props {
        zone: ZoneWorldPosition;
        mode?: 'panel' | 'drawer';
        onClose: () => void;
        onFocus: () => void;
    }

    let { zone, mode = 'panel', onClose, onFocus }: Props = $props();
</script>

<PopupContainer title={zone.name} subtitle="Zone" {mode} {onClose} {onFocus}>
    <ZonePopupContent {zone} />
</PopupContainer>
