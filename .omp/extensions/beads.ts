import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
import { execSync } from "child_process";

/** Run `bd prime` and return its output, or null if bd is unavailable or the project has no .beads/ */
function bdPrime(cwd: string): string | null {
	try {
		const output = execSync("bd prime", {
			cwd,
			encoding: "utf-8",
			timeout: 5000,
		}).trim();
		return output || null;
	} catch {
		// bd not installed, not initialized, or errored — silently skip
		return null;
	}
}

export default function beadsExtension(pi: ExtensionAPI) {
	pi.setLabel("Beads");

	// Inject beads context at session start so the agent knows the current issue state
	pi.on("session_start", async (_event, ctx) => {
		const prime = bdPrime(ctx.cwd);
		if (prime) {
			pi.sendMessage(prime, { deliverAs: "nextTurn" });
		}
	});

	// Re-inject after compaction so beads context survives context-window resets
	pi.on("session_compact", async (_event, ctx) => {
		const prime = bdPrime(ctx.cwd);
		if (prime) {
			pi.sendMessage(prime, { deliverAs: "nextTurn" });
		}
	});
}
