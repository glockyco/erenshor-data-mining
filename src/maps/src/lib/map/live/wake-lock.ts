/**
 * Keeps the screen on while wanted. Browsers release a screen wake lock whenever the page
 * is hidden, so it is requested again each time the page becomes visible. Browsers
 * without the Screen Wake Lock API, or that refuse it, leave the screen to its settings.
 */
export class ScreenWakeLock {
    private sentinel: WakeLockSentinel | null = null;
    private wanted = false;

    private readonly onVisibilityChange = () => {
        if (document.visibilityState === 'visible') void this.acquire();
    };

    set(wanted: boolean): void {
        if (wanted === this.wanted) return;
        this.wanted = wanted;

        if (wanted) {
            document.addEventListener('visibilitychange', this.onVisibilityChange);
            void this.acquire();
            return;
        }

        document.removeEventListener('visibilitychange', this.onVisibilityChange);
        const sentinel = this.sentinel;
        this.sentinel = null;
        void sentinel?.release().catch(() => {});
    }

    private async acquire(): Promise<void> {
        if (
            !this.wanted ||
            this.sentinel ||
            !('wakeLock' in navigator) ||
            document.visibilityState !== 'visible'
        ) {
            return;
        }

        try {
            const sentinel = await navigator.wakeLock.request('screen');
            if (!this.wanted || this.sentinel) {
                void sentinel.release().catch(() => {});
                return;
            }
            this.sentinel = sentinel;
            sentinel.addEventListener('release', () => {
                if (this.sentinel === sentinel) this.sentinel = null;
            });
        } catch {
            // Refused, for example in battery saver mode.
        }
    }
}
