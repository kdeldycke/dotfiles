/**
 * Timestamped default session names for Pi, refreshed with a content summary
 * on exit.
 *
 * Pi core already sets the terminal tab title from the session name,
 * reactively, on every `session_info_changed` event (see
 * `updateTerminalTitle()` in `interactive-mode.js`): `π - <name> - <cwd
 * basename>` if a name is set, `π - <cwd basename>` otherwise. No extension
 * is needed for that part, and calling `ctx.ui.setTitle()` here would only
 * race pi's own internal listener on the same event and lose (or worse,
 * duplicate the cwd if the name also embeds a path, since core always
 * appends the basename itself).
 *
 * This extension covers the two things pi does not do on its own:
 *
 * 1. Unnamed sessions get a bare "MM-DD@HH:MM" name at startup, so /resume
 *    entries aren't all identical (mirrors Claude Code's default naming).
 *
 * 2. On real exit ("quit" only, never /new, /resume, /fork, or /reload), the
 *    name is refreshed to "MM-DD@HH:MM <short summary>" using a one-shot LLM
 *    call over the session's user turns, mirroring
 *    dotfiles/.claude/hooks/session-title.py's Stop-hook behavior. Unlike
 *    that script, this has no Haiku subprocess, no sidecar files, and no
 *    mid-conversation refresh schedule: pi sessions aren't resumed/renamed
 *    anywhere near as often as Claude Code's, so a single end-of-session pass
 *    is enough, and it reuses whatever model/auth the session already has
 *    instead of depending on a specific provider.
 *
 * The refreshed name only ever affects /resume and --resume (via the session
 * file's stored SessionInfoEntry): by the time it is set, pi has already
 * stopped the TUI and is mid-exit, so there is no live terminal title left to
 * usefully update, the shell's own prompt title takes over immediately after.
 *
 * A session already renamed by hand (anything not matching our own
 * "MM-DD@HH:MM" or "MM-DD@HH:MM <summary>" pattern) is left untouched.
 */

import { complete } from "@earendil-works/pi-ai/compat";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const TIMESTAMP_RE = /^(\d\d-\d\d@\d\d:\d\d)(?: (.+))?$/;
const MAX_TRANSCRIPT_CHARS = 8000;
const SUMMARY_TIMEOUT_MS = 15_000;

const SUMMARY_SYSTEM_PROMPT = `You generate a concise summary title for a coding-assistant session.

Hard rules:
- 3 to 7 words. Maximum 50 characters.
- Sentence case: capitalize the first word and proper nouns only.
- Capture the main topic or goal. Be specific, not vague.
- Reply with the title text only. No quotes, no punctuation at the end, no prose.

Examples:
Input: "fix the login button on mobile"
Output: Fix login button on mobile

Input: "refactor the API client error handling and add retries"
Output: Refactor API client error handling

Input: "investigate the flaky test in tests/integration/test_auth.py"
Output: Debug flaky integration auth test`;

function timestamp(): string {
	const now = new Date();
	const pad = (n: number) => String(n).padStart(2, "0");
	return `${pad(now.getMonth() + 1)}-${pad(now.getDate())}@${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function extractTextParts(content: unknown): string[] {
	if (typeof content === "string") return [content];
	if (!Array.isArray(content)) return [];
	const parts: string[] = [];
	for (const block of content) {
		if (block && typeof block === "object" && (block as { type?: string }).type === "text") {
			const text = (block as { text?: unknown }).text;
			if (typeof text === "string") parts.push(text);
		}
	}
	return parts;
}

function sanitizeTitle(title: string): string {
	let cleaned = title
		.replace(/[\x1b\x07\r]/g, "")
		.replace(/\n/g, " ")
		.trim();
	// Strip surrounding quotes the model sometimes adds despite instructions.
	cleaned = cleaned.replace(/^["'`]+|["'`]+$/g, "").trim();
	if (!cleaned || cleaned.startsWith("/")) return "";
	return cleaned.length > 60 ? cleaned.slice(0, 60) : cleaned;
}

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (_event, _ctx) => {
		if (!pi.getSessionName()) {
			pi.setSessionName(timestamp());
		}
	});

	pi.on("session_shutdown", async (event, ctx) => {
		if (event.reason !== "quit") return;

		const currentName = pi.getSessionName();
		if (!currentName) return;
		const match = currentName.match(TIMESTAMP_RE);
		if (!match) return; // User-set name that doesn't carry our prefix: leave it alone.
		const prefix = match[1];

		const userTurns = ctx.sessionManager
			.getBranch()
			.filter((e) => e.type === "message" && e.message.role === "user")
			.map((e) => extractTextParts((e as { message: { content: unknown } }).message.content).join("\n"))
			.filter((text) => text.trim().length > 0 && !text.trimStart().startsWith("<"));
		if (userTurns.length === 0) return;

		const model = ctx.model;
		if (!model) return;
		const auth = await ctx.modelRegistry.getApiKeyAndHeaders(model);
		if (!auth.ok || !auth.apiKey) return;

		const transcript = userTurns.join("\n\n---\n\n").slice(0, MAX_TRANSCRIPT_CHARS);

		try {
			const response = await complete(
				model,
				{
					systemPrompt: SUMMARY_SYSTEM_PROMPT,
					messages: [
						{
							role: "user",
							content: [{ type: "text", text: transcript }],
							timestamp: Date.now(),
						},
					],
				},
				{
					apiKey: auth.apiKey,
					headers: auth.headers,
					env: auth.env,
					cacheRetention: "none",
					signal: AbortSignal.timeout(SUMMARY_TIMEOUT_MS),
				},
			);
			const summary = sanitizeTitle(
				response.content
					.filter((c): c is { type: "text"; text: string } => c.type === "text")
					.map((c) => c.text)
					.join(""),
			);
			if (summary) {
				pi.setSessionName(`${prefix} ${summary}`);
			}
		} catch {
			// Best-effort only: never block or fail exit over a summarization error.
		}
	});
}
