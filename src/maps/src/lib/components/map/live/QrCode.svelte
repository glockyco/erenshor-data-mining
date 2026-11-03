<script lang="ts">
    import { encode } from 'uqr';

    interface Props {
        value: string;
        /** Rendered width and height in CSS pixels */
        size: number;
        label: string;
    }

    let { value, size, label }: Props = $props();

    // Dark modules on a light square with a one-module quiet zone, as phone cameras
    // read a code shown on a dark page.
    const code = $derived(encode(value, { ecc: 'L', border: 1 }));
    const path = $derived(
        code.data
            .flatMap((row, y) => row.map((dark, x) => (dark ? `M${x} ${y}h1v1h-1z` : '')))
            .join('')
    );
</script>

<svg
    width={size}
    height={size}
    viewBox={`0 0 ${code.size} ${code.size}`}
    shape-rendering="crispEdges"
    role="img"
    aria-label={label}
    class="flex-none rounded"
>
    <rect width={code.size} height={code.size} fill="#f4f4f5" />
    <path d={path} fill="#18181b" />
</svg>
