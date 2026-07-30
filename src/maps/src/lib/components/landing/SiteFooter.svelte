<!--
  Footer uses only vertical padding so the parent container's horizontal padding
  is preserved. The generous bottom padding reserves space for the section lens
  nav, which floats bottom-right at every width.
-->
<script lang="ts">
    import type { PatchAnnouncement } from '$lib/steam-news';
    import { compareFreshness, isNotablyStale, type Freshness } from '$lib/steam-news';

    interface Provenance {
        gameBuildId: string;
        buildUpdatedAt: string;
    }

    // Null whenever the export did not record a build. An honest older date is
    // fine for a reference tool; a fabricated "updated today" is not, so the
    // line is omitted rather than guessed.
    let { provenance = null }: { provenance?: Provenance | null } = $props();

    const buildDate = $derived.by(() => {
        if (!provenance) return null;
        const date = new Date(provenance.buildUpdatedAt);
        if (Number.isNaN(date.getTime())) return null;
        return date.toLocaleDateString('en-US', {
            day: 'numeric',
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
            .then((response) =>
                response.ok ? (response.json() as Promise<PatchAnnouncement>) : null
            )
            .then((latest) => {
                freshness = compareFreshness(buildUpdatedAt, latest);
            })
            .catch(() => {
                freshness = null;
            });

        return () => aborter.abort();
    });

    // How old the data is answers "can I trust this" without the reader needing
    // to know Erenshor's release cadence, but it is only true at read time, so a
    // prerendered copy would be wrong the day after a deploy. It rides along
    // with the live comparison rather than being baked into the HTML.
    const ageLabel = $derived.by(() => {
        if (!freshness) return null;
        if (freshness.daysOld === 0) return 'today';
        if (freshness.daysOld === 1) return 'yesterday';
        return `${freshness.daysOld} days ago`;
    });

    // The verdict is deliberately unquantified: see `compareFreshness` for why a
    // patch count over this data would be false precision. "Has it changed" and
    // "how old is it" are the two questions a reader actually has, and the link
    // lets them judge whether the change touches what they came to read.
    const freshnessLabel = $derived.by(() => {
        if (!freshness) return null;
        return freshness.state === 'current' ? 'up to date' : 'game patched since';
    });
    const notablyStale = $derived(freshness ? isNotablyStale(freshness) : false);
</script>

<footer class="mt-2 border-t border-line">
    <div
        class="mx-auto flex max-w-[1140px] flex-col gap-2 px-7 pt-[26px] pb-20 text-[0.88rem] text-muted min-[880px]:flex-row min-[880px]:flex-wrap min-[880px]:items-center min-[880px]:justify-between min-[880px]:gap-[14px]"
    >
        <span>Erenshor Maps. A fan project, not affiliated with Burgee Media.</span>
        {#if provenance && buildDate}
            <span>
                Game data from <time
                    datetime={provenance.buildUpdatedAt}
                    title="Steam build {provenance.gameBuildId}">{buildDate}</time
                >{#if ageLabel}&nbsp;<span class="whitespace-nowrap">({ageLabel})</span
                    >{/if}{#if freshnessLabel}&nbsp;<span
                        class={notablyStale ? 'text-accent' : 'text-muted'}
                        >&middot; {#if freshness?.latest}<a
                                href={freshness.latest.url}
                                rel="noreferrer"
                                title={freshness.latest.title}
                                class="underline decoration-dotted underline-offset-2 hover:decoration-solid focus-visible:rounded-[2px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                                >{freshnessLabel}</a
                            >{:else}{freshnessLabel}{/if}</span
                    >{/if}
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
