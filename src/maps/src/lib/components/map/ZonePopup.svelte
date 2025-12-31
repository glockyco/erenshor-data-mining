<script lang="ts">
    import type { ZoneWorldPosition } from '$lib/types/world-map';
    import PopupContainer from './PopupContainer.svelte';
    import ZonePopupContent from './popups/ZonePopupContent.svelte';

    interface Props {
        zone: ZoneWorldPosition;
        onClose: () => void;
        onFocus: () => void;
    }

    let { zone, onClose, onFocus }: Props = $props();
</script>

<PopupContainer title={zone.name} subtitle="Zone" {onClose} {onFocus}>
    <ZonePopupContent {zone} />
</PopupContainer>
