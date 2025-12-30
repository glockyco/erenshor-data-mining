<script lang="ts">
    interface Props {
        label: string;
        checked: boolean;
        color?: string;
        onchange: (checked: boolean) => void;
    }

    let { label, checked, color, onchange }: Props = $props();

    function handleChange(event: Event) {
        const target = event.target as HTMLInputElement;
        onchange(target.checked);
    }
</script>

<label class="flex cursor-pointer items-center gap-2 py-1 text-sm hover:bg-zinc-700/50">
    <input type="checkbox" {checked} onchange={handleChange} class="sr-only" />
    <span
        class="flex h-4 w-4 items-center justify-center rounded border transition-colors"
        class:bg-zinc-600={!checked}
        class:border-zinc-500={!checked}
        style:background-color={checked ? color : undefined}
        style:border-color={checked ? color : undefined}
    >
        {#if checked}
            <svg class="h-3 w-3 text-white" viewBox="0 0 12 12" fill="none" stroke="currentColor">
                <path
                    d="M2 6l3 3 5-6"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                />
            </svg>
        {/if}
    </span>
    <span class="text-zinc-200">{label}</span>
</label>
