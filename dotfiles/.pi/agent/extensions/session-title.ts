/**
 * Timestamped default session names for Pi, refreshed with a content summary
 * during the session and on exit.
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
 * 2. The name is refreshed to "MM-DD@HH:MM <short summary>" by a one-shot LLM
 *    call over the session's user turns, on the refresh schedule of
 *    dotfiles/.claude/hooks/session-title.py (see `inSchedule`). Each
 *    refresh runs once pi settles after a prompt, in the background, so the
 *    starship row and the terminal tab show the title while the session is
 *    live. It reuses the session's model and auth, with no subprocess and
 *    no sidecar file.
 *
 * 3. On real exit ("quit" only, never /new, /resume, /fork, or /reload), one
 *    last refresh covers the prompts sent since the last scheduled one, for
 *    /resume and --resume. Pi has already stopped the TUI by then.
 *
 * A session already renamed by hand (anything not matching our own
 * "MM-DD@HH:MM" or "MM-DD@HH:MM <summary>" pattern) is left untouched.
 */

import { appendFileSync, existsSync, statSync, unlinkSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const DEBUG_LOG = join(homedir(), ".pi", "agent", "session-title.log");

/**
 * Best-effort observability, mirroring dotfiles/.claude/hooks/wrapup-session-nudge.py: the title
 * calls run in the background or at exit and swallow every failure, so without a log there is no
 * telling "never fired" from "fired and gave up at step N". Wiped past 64 KiB.
 */
function debugLog(note: string): void {
	try {
		if (existsSync(DEBUG_LOG) && statSync(DEBUG_LOG).size > 65536) unlinkSync(DEBUG_LOG);
		appendFileSync(DEBUG_LOG, `${new Date().toISOString()} ${note}\n`);
	} catch {
		// Logging must never break the host.
	}
}

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
	// A real title fits the 50-character instruction. Far past it, the model answered or
	// refused instead of titling (observed: a refusal fragment stored as the session name),
	// and a truncated answer is worse than keeping the old name.
	return cleaned.length > 60 ? "" : cleaned;
}

/**
 * Whether the session's `turn`-th user prompt earns a mid-session refresh: turns 1, 3 and 6, then
 * every 5 from 10. Same schedule as `dotfiles/.claude/hooks/session-title.py`: many sessions never
 * reach a second prompt, so the first one gets a title at once, and later topic drift is caught
 * at a falling rate so a long session costs a handful of calls.
 */
function inSchedule(turn: number): boolean {
	if (turn === 1 || turn === 3 || turn === 6) return true;
	return turn >= 10 && (turn - 10) % 5 === 0;
}

/** The session's user prompts as plain text, without the `<`-prefixed injected ones. */
function userTurns(ctx: ExtensionContext): string[] {
	return ctx.sessionManager
		.getBranch()
		.filter((e) => e.type === "message" && e.message.role === "user")
		.map((e) => extractTextParts((e as { message: { content: unknown } }).message.content).join("\n"))
		.filter((text) => text.trim().length > 0 && !text.trimStart().startsWith("<"));
}

/**
 * Ask the session model for a title over `turns`, or return "" when it cannot or will not give
 * one. Every failure is logged and swallowed: a title is never worth an error in the session.
 */
async function summarize(ctx: ExtensionContext, turns: string[], signal: AbortSignal): Promise<string> {
	const model = ctx.model;
	if (!model) {
		debugLog("skip: no model");
		return "";
	}
	// Cheap early exit only: the registry resolves auth per request, and a provider it
	// cannot resolve throws into the catch around the call below.
	if (!ctx.modelRegistry.hasConfiguredAuth(model)) {
		debugLog("skip: no configured auth for the session model");
		return "";
	}

	const transcript = turns.join("\n\n---\n\n").slice(0, MAX_TRANSCRIPT_CHARS);
	// Delimit the transcript and restate the task after it: with instructions only in the
	// system prompt, a low-effort model responds to the transcript's content instead of
	// titling it (observed live: a refusal about the transcript stored as the name).
	const request = `<transcript>\n${transcript}\n</transcript>\n\nReply with only the session title for the transcript above: 3 to 7 words, maximum 50 characters, sentence case, no quotes.`;

	try {
		const response = await ctx.modelRegistry.complete(
			model,
			{
				systemPrompt: SUMMARY_SYSTEM_PROMPT,
				messages: [
					{
						role: "user",
						content: [{ type: "text", text: request }],
						timestamp: Date.now(),
					},
				],
			},
			{
				cacheRetention: "none",
				signal: AbortSignal.any([signal, AbortSignal.timeout(SUMMARY_TIMEOUT_MS)]),
				// Room for a thinking model's reasoning preamble plus the one-line title.
				maxTokens: 2000,
				// Without an effort, the openrouter adapter sends `reasoning: {effort: "none"}`,
				// which mandatory-reasoning models (qwen3.8-max) reject with a 400. "low" keeps
				// the title call valid there and cheap everywhere; providers that do not
				// support an effort ignore it.
				reasoningEffort: "low",
			},
		);
		const summary = sanitizeTitle(
			response.content
				.filter((c): c is { type: "text"; text: string } => c.type === "text")
				.map((c) => c.text)
				.join(""),
		);
		if (!summary) {
			const blocks = response.content.map((c) => c.type).join(",");
			const error = (response as { errorMessage?: string }).errorMessage ?? "";
			debugLog(`empty summary: stopReason=${response.stopReason} blocks=[${blocks}] ${error}`);
		}
		return summary;
	} catch (error) {
		debugLog(`skip: summary call failed: ${error}`);
		return "";
	}
}

export default function (pi: ExtensionAPI) {
	/** User-prompt count the current name was summarized from, so no pass repeats the last one. */
	let titledTurns = 0;
	/** The mid-session call in flight, if any: one at a time, and aborted at shutdown. */
	let inFlight: AbortController | undefined;

	/**
	 * Refresh the name from the session's user prompts, keeping its timestamp prefix. Leaves a
	 * name that does not carry our prefix alone, and drops the result when the name changed
	 * while the call ran, like a `/rename` typed meanwhile.
	 */
	async function refresh(ctx: ExtensionContext, turns: string[], signal: AbortSignal, when: string): Promise<void> {
		const currentName = pi.getSessionName();
		if (!currentName) {
			debugLog(`${when} skip: no session name set`);
			return;
		}
		const match = currentName.match(TIMESTAMP_RE);
		if (!match) {
			debugLog(`${when} skip: name not ours (${currentName})`);
			return;
		}
		const summary = await summarize(ctx, turns, signal);
		if (!summary) {
			debugLog(`${when} skip: summary came back empty`);
			return;
		}
		if (signal.aborted || pi.getSessionName() !== currentName) {
			debugLog(`${when} skip: session changed during the call`);
			return;
		}
		titledTurns = turns.length;
		const name = `${match[1]} ${summary}`;
		if (name !== currentName) pi.setSessionName(name);
		debugLog(`${when} renamed at turn ${turns.length}: ${name}`);
	}

	pi.on("session_start", async (_event, ctx) => {
		titledTurns = 0;
		if (!pi.getSessionName()) {
			pi.setSessionName(timestamp());
		}
		// A resumed session already holds a title for the prompts it has: count them as titled,
		// so its next scheduled refresh waits for a new prompt.
		const name = pi.getSessionName();
		if (name && TIMESTAMP_RE.exec(name)?.[2]) titledTurns = userTurns(ctx).length;
	});

	// Fired once pi stops working on a prompt. Not awaited by the session: the title call runs
	// beside the next prompt rather than delaying it.
	pi.on("agent_settled", async (_event, ctx) => {
		if (inFlight) return;
		const turns = userTurns(ctx);
		if (turns.length <= titledTurns || !inSchedule(turns.length)) return;
		const controller = new AbortController();
		inFlight = controller;
		void refresh(ctx, turns, controller.signal, "mid-session").finally(() => {
			if (inFlight === controller) inFlight = undefined;
		});
	});

	pi.on("session_shutdown", async (event, ctx) => {
		inFlight?.abort();
		inFlight = undefined;
		if (event.reason !== "quit") return;
		const turns = userTurns(ctx);
		if (turns.length === 0) {
			debugLog("exit skip: no user turns");
			return;
		}
		if (turns.length === titledTurns) {
			debugLog(`exit skip: title already covers turn ${titledTurns}`);
			return;
		}
		await refresh(ctx, turns, new AbortController().signal, "exit");
	});
}
