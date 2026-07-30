<!--
  Footer uses only vertical padding so the parent container's horizontal padding
  is preserved. The generous bottom padding reserves space for the section lens
  nav, which floats bottom-right at every width.
-->
<script lang="ts">
    import { compareFreshness, type Freshness, type PatchAnnouncement } from '$lib/steam-news';

    interface Provenance {
        gameBuildId: string;
        buildUpdatedAt: string;
    }

    // Null whenever the export did not record a build. An honest older date is
    // fine for a reference tool; a fabricated "updated today" is not, so the
    // line is omitted rather than guessed.
    let { provenance = null }: { provenance?: Provenance | null } = $props();

    const STEAMDB_PATCH_NOTES = 'https://steamdb.info/app/2382520/patchnotes/';

    const buildDate = $derived.by(() => {
        if (!provenance) return null;
        const date = new Date(provenance.buildUpdatedAt);
        if (Number.isNaN(date.getTime())) return null;
        return date.toLocaleDateString('en-US', {
            month: 'long',
            year: 'numeric',
            timeZone: 'UTC'
        });
    });

    // The site is prerendered, so the live patch check cannot run at render
    // time the way a server-rendered page would do it. It is a progressive
    // enhancement instead: the build and its date are already in the static
    // HTML, and this only adds how that build compares to the live game. On any
    // failure the comparison stays absent rather than claiming currency.
    let freshness = $state<Freshness | null>(null);

    $effect(() => {
        const buildUpdatedAt = provenance?.buildUpdatedAt;
        if (!buildUpdatedAt) return;

        const aborter = new AbortController();
        fetch('/api/game-version', { signal: aborter.signal })
            .then((response) => (response.ok ? (response.json() as Promise<PatchAnnouncement>) : null))
            .then((latest) => {
                freshness = compareFreshness(buildUpdatedAt, latest);
            })
            .catch(() => {
                freshness = null;
            });

        return () => aborter.abort();
    });

    const freshnessLabel = $derived.by(() => {
        if (!freshness) return null;
        if (freshness.state === 'current') return 'up to date';
        if (freshness.daysBehind < 1) return 'game patched since';
        return `game patched ${freshness.daysBehind} day${freshness.daysBehind === 1 ? '' : 's'} later`;
    });
</script>

<footer class="mt-2 border-t border-line">
    <div
        class="mx-auto flex max-w-[1140px] flex-col gap-2 px-7 pt-[26px] pb-20 text-[0.88rem] text-muted min-[880px]:flex-row min-[880px]:flex-wrap min-[880px]:items-center min-[880px]:justify-between min-[880px]:gap-[14px]"
    >
        <span>Erenshor Maps. A fan project, not affiliated with Burgee Media.</span>
        {#if provenance && buildDate}
            <span>
                Map data synced to Erenshor build
                <a
                    href={STEAMDB_PATCH_NOTES}
                    rel="noreferrer"
                    class="text-muted no-underline hover:text-accent">{provenance.gameBuildId}</a
                >
               &middot; {buildDate}{#if freshnessLabel}&nbsp;<span
                        class={freshness?.state === 'behind' ? 'text-accent' : 'text-muted'}
                    >
                        · {#if freshness?.state === 'behind'}<a
                                href={freshness.latest.url}
                                rel="noreferrer"
                                class="text-accent underline decoration-dotted underline-offset-2"
                                >{freshnessLabel}</a
                            >{:else}{freshnessLabel}{/if}
                    </span>{/if}
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
