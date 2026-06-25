<!--
  Footer uses only vertical padding so the parent container's horizontal padding
  is preserved. Bottom padding reserves space for the fixed coordinate HUD
  (visible >=640px); on small screens the HUD is hidden so the padding shrinks.
-->
<footer class="mt-2 border-t border-line">
    <div
        class="mx-auto flex max-w-[1140px] flex-col gap-2 px-7 pt-[26px] pb-8 text-[0.88rem] text-muted min-[640px]:pb-20 min-[880px]:flex-row min-[880px]:flex-wrap min-[880px]:items-center min-[880px]:justify-between min-[880px]:gap-[14px]"
    >
        <span>Erenshor Maps. A fan project, not affiliated with Burgee Media.</span>
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
