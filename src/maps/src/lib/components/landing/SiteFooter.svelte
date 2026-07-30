<!--
  Footer uses only vertical padding so the parent container's horizontal padding
  is preserved. The generous bottom padding reserves space for the section lens
  nav, which floats bottom-right at every width.
-->
<script lang="ts">
    interface Provenance {
        gameBuildId: string;
        extractedAt: string;
    }

    // Null whenever the export did not record a build ID. An honest older date
    // is fine for a reference tool; a fabricated "updated today" is not, so the
    // line is omitted rather than guessed.
    let { provenance = null }: { provenance?: Provenance | null } = $props();

    const STEAMDB_PATCH_NOTES = 'https://steamdb.info/app/2382520/patchnotes/';

    const exportedOn = $derived.by(() => {
        if (!provenance) return null;
        const date = new Date(provenance.extractedAt);
        if (Number.isNaN(date.getTime())) return null;
        return date.toLocaleDateString('en-US', {
            month: 'long',
            year: 'numeric',
            timeZone: 'UTC'
        });
    });
</script>

<footer class="mt-2 border-t border-line">
    <div
        class="mx-auto flex max-w-[1140px] flex-col gap-2 px-7 pt-[26px] pb-20 text-[0.88rem] text-muted min-[880px]:flex-row min-[880px]:flex-wrap min-[880px]:items-center min-[880px]:justify-between min-[880px]:gap-[14px]"
    >
        <span>Erenshor Maps. A fan project, not affiliated with Burgee Media.</span>
        {#if provenance && exportedOn}
            <span>
                Map data synced to Erenshor build
                <a
                    href={STEAMDB_PATCH_NOTES}
                    rel="noreferrer"
                    class="text-muted no-underline hover:text-accent">{provenance.gameBuildId}</a
                >
                · {exportedOn}
            </span>
        {/if}
        <span>
            <a href="https://erenshor.com/" class="text-muted no-underline hover:text-accent"
                >erenshor.com</a
            >
            ·
            <a href="https://erenshor.wiki.gg/" class="text-muted no-underline hover:text-accent"
                >wiki</a
            >
            ·
            <a href="https://discord.gg/erenshor" class="text-muted no-underline hover:text-accent"
                >discord</a
            >
        </span>
    </div>
</footer>
