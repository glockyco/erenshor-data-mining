<script lang="ts">
    import { Slider } from '$lib/components/ui/slider';

    interface Props {
        label: string;
        min: number;
        max: number;
        value: [number, number];
        onchange: (value: [number, number]) => void;
    }

    let { label, min, max, value, onchange }: Props = $props();

    function handleChange(newValue: number[] | undefined) {
        if (newValue && newValue.length === 2) {
            onchange([newValue[0], newValue[1]]);
        }
    }
</script>

<div class="mb-2 space-y-1.5 py-1">
    <div class="flex items-center justify-between text-xs">
        <span class="text-zinc-400">{label}</span>
        <span class="font-mono text-zinc-400">{value[0]} - {value[1]}</span>
    </div>
    {#key `${min}-${max}`}
        <Slider
            type="multiple"
            {min}
            {max}
            step={1}
            value={[...value]}
            onValueChange={handleChange}
        />
    {/key}
</div>
