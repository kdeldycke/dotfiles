/**
 * `/bye [focus]`: run the wrapup-session skill as a final turn, then quit.
 *
 * ## Why the wrap-up is a command and not a quit hook
 *
 * pi has no cancellable pre-quit event. `/quit` is matched in the editor's
 * `onSubmit` before extension command dispatch (`interactive-mode.js`), and
 * Ctrl+C / Ctrl+D call `shutdown()` directly, so no extension can intercept
 * either. `session_shutdown` fires with the TUI already stopped and the
 * runtime mid-teardown: good for a last one-shot call (see session-title.ts),
 * useless for a turn that needs tools. So the flow is inverted: the wrap-up
 * runs as a normal turn with full tool access, and quitting is its last step.
 *
 * ## Why `agent_settled` and not `waitForIdle()` in the handler
 *
 * The extension-facing `sendUserMessage` is fire-and-forget, and `prompt()`
 * awaits several times (command lookup, input event, auth check) before the
 * run starts and marks the session busy (pi 1.3.0). A `waitForIdle()` right
 * after the send can therefore return while the agent is still idle, and the
 * shutdown would race the wrap-up.
 * Instead the command arms a flag and `agent_settled` decides: quit only when
 * the last user message in the branch is the wrap-up prompt (matched on the
 * `<skill name="wrapup-session">` block pi expands, or on the fallback tag)
 * and the turn ended cleanly. The signature check also covers the case where
 * the send failed silently (compaction in progress) and a later, unrelated
 * turn settles: that turn's last user message is not the wrap-up, so it
 * disarms rather than quits.
 *
 * ## Cancelling
 *
 * Esc aborts the turn, which settles with stopReason "aborted": pi stays
 * open. Any interactive input while armed also disarms, so steering the
 * wrap-up (or typing anything after `/bye`) cancels the auto-quit rather
 * than quitting under the user.
 *
 * ## The resume-line rewrite
 *
 * pi prints its own exit hint as one line, `To resume this session: pi
 * --session <id>`, from core (`interactive-mode.ts`), after `session_shutdown`
 * handlers run. A triple-click on that line selects the label with the
 * command, so the paste is not runnable. Upstream declined the one-line fix
 * (earendil-works/pi#9515, closed NOT_PLANNED), so this extension rewrites the
 * chunk during the shutdown window: the label keeps its line, the command
 * gets the next one. The match is anchored to the label and its optional dim
 * escape, so no other write in that window changes.
 *
 * ## The nudge
 *
 * A plain `/quit` or Ctrl+D on a session with real user turns prints a dim
 * hint line, then the one-liner `pi --session <id> "/bye"` on a line of its
 * own, next to pi's own resume hint: a terminal triple-click then copies the
 * command without the hint text. pi's own resume hint still prefixes the
 * command inline. An initial CLI message goes through
 * `session.prompt()`, whose `expandPromptTemplates` defaults to true, so the
 * `/bye` argument dispatches as an extension command (pi 1.3.0) and the
 * one-liner resumes, wraps up, and quits in one move. TUI
 * mode only, so `pi -p` output stays clean, and only for persisted sessions:
 * an unsaved session has nothing to resume.
 *
 * ```{todo}
 * Ask upstream for a cancellable pre-quit event (or extension-visible
 * `/quit`), which would let the wrap-up hook the real exit paths instead of
 * needing its own command.
 * ```
 */

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const SKILL_NAME = "wrapup-session";
const SKILL_COMMAND = `skill:${SKILL_NAME}`;

/** How a wrap-up prompt starts: pi's skill expansion block, or the fallback's own tag. */
const WRAPUP_PREFIXES = [`<skill name="${SKILL_NAME}"`, `<${SKILL_NAME}>`] as const;

/**
 * Sent when the skill is not discoverable (a `--no-skills` run): a missing
 * skill must degrade to a shorter wrap-up, never abort the command. The tag
 * wrapper gives the signature check its prefix and keeps the message out of
 * session-title.ts's summary input, which skips user turns starting with "<".
 */
const FALLBACK_PROMPT = `<${SKILL_NAME}>
The session is closing. Do a final wrap-up pass, then stop:
1. List anything left to do from this session: promises not delivered, changes left uncommitted, jobs still running.
2. Name anything learned worth persisting into agent instructions, skills, or code comments, and apply the small safe edits directly. Working tree only: never commit, push, or post anywhere.
Most sessions have nothing worth persisting: say so plainly instead of inventing a lesson. Do not ask questions; state assumptions.
End with two short lists: left to do, and persisted or proposed.
</${SKILL_NAME}>`;

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

/** Text of every user turn on the current branch, oldest first. */
function userTexts(ctx: ExtensionContext): string[] {
	return ctx.sessionManager
		.getBranch()
		.filter((e) => e.type === "message" && e.message.role === "user")
		.map((e) => extractTextParts((e as { message: { content: unknown } }).message.content).join("\n"));
}

/** Whether the user actually typed anything: synthetic "<"-prefixed turns do not count. */
function hasRealUserTurns(ctx: ExtensionContext): boolean {
	return userTexts(ctx).some((text) => text.trim().length > 0 && !text.trimStart().startsWith("<"));
}

function lastAssistantStopReason(ctx: ExtensionContext): string | undefined {
	const entries = ctx.sessionManager.getBranch();
	for (let i = entries.length - 1; i >= 0; i--) {
		const entry = entries[i] as { type: string; message?: { role?: string; stopReason?: string } };
		if (entry.type === "message" && entry.message?.role === "assistant") {
			return entry.message.stopReason;
		}
	}
	return undefined;
}

function notify(ctx: ExtensionContext, text: string, level: "info" | "warning"): void {
	if (ctx.hasUI) ctx.ui.notify(text, level);
}

export default function (pi: ExtensionAPI) {
	/** True from `/bye` until the wrap-up settles, is cancelled, or turns out hijacked. */
	let armed = false;

	pi.registerCommand("bye", {
		description: "Wrap up the session (loose ends, lessons to persist), then quit",
		handler: async (args, ctx) => {
			if (armed) {
				notify(ctx, "Wrap-up already in progress.", "info");
				return;
			}
			armed = true;
			// Nothing said yet: nothing to wrap up, so quit directly (still through
			// ctx.shutdown(), so session_shutdown handlers run as on any quit).
			if (!hasRealUserTurns(ctx)) {
				ctx.shutdown();
				return;
			}
			const skillLoaded = pi
				.getCommands()
				.some((command) => command.source === "skill" && command.name === SKILL_COMMAND);
			const focus = (args ?? "").trim();
			const text = skillLoaded
				? `/skill:${SKILL_NAME}${focus ? ` ${focus}` : ""}`
				: focus
					? `${FALLBACK_PROMPT}\n\n${focus}`
					: FALLBACK_PROMPT;
			pi.sendUserMessage(text, {
				expandPromptTemplates: true,
				// Mid-stream /bye: finish the current work first, then wrap up.
				...(ctx.isIdle() ? {} : { deliverAs: "followUp" as const }),
			});
			notify(ctx, "Wrapping up: pi quits when the wrap-up settles. Esc or any input cancels the quit.", "info");
		},
	});

	pi.on("input", async (event, ctx) => {
		// The wrap-up's own message arrives with source "extension"; anything else
		// while armed is the user taking over, so the pending quit is dropped.
		if (armed && event.source !== "extension") {
			armed = false;
			notify(ctx, "Auto-quit cancelled by new input: /bye again or /quit to close.", "info");
		}
	});

	pi.on("agent_settled", async (_event, ctx) => {
		if (!armed) return;
		const texts = userTexts(ctx);
		const last = texts[texts.length - 1] ?? "";
		if (!WRAPUP_PREFIXES.some((prefix) => last.startsWith(prefix))) {
			// The settled turn was not the wrap-up (the send failed, or something
			// else drove a turn): disarm so no later turn quits by surprise.
			armed = false;
			return;
		}
		const stop = lastAssistantStopReason(ctx);
		if (stop === "aborted" || stop === "error") {
			armed = false;
			notify(ctx, `Wrap-up ${stop}: staying open. /bye to retry, /quit to close anyway.`, "warning");
			return;
		}
		ctx.shutdown();
	});

	/** Installed once per process, from the first quit through process exit. */
	let resumeLineRewritten = false;

	/** Put pi's exit resume command on its own line, for terminal line selection. */
	function rewriteResumeLineOntoItsOwn(): void {
		if (resumeLineRewritten) return;
		resumeLineRewritten = true;
		const original = process.stdout.write.bind(process.stdout);
		process.stdout.write = ((chunk: unknown, ...rest: unknown[]): boolean => {
			if (typeof chunk === "string") {
				return (original as (...args: unknown[]) => boolean)(
					chunk.replace(/(To resume this session:(?:\x1b\[[0-9;]*m)?) /, "$1\n"),
					...rest,
				);
			}
			return (original as (...args: unknown[]) => boolean)(chunk, ...rest);
		}) as typeof process.stdout.write;
	}

	pi.on("session_shutdown", async (event, ctx) => {
		if (event.reason !== "quit" || ctx.mode !== "tui") return;
		rewriteResumeLineOntoItsOwn();
		if (armed) return;
		if (!hasRealUserTurns(ctx)) return;
		// The runtime object behind ReadonlySessionManager is the full SessionManager;
		// the probes beyond the Pick type are optional so a slimmer object degrades to -c.
		const manager = ctx.sessionManager as unknown as {
			getSessionId?(): string;
			isPersisted?(): boolean;
			usesDefaultSessionDir?(): boolean;
		};
		if (manager.isPersisted && !manager.isPersisted()) return; // Nothing resumable to wrap up.
		// A non-default session dir would need a --session-dir flag the id alone cannot carry.
		const sessionId = manager.usesDefaultSessionDir?.() === false ? undefined : manager.getSessionId?.();
		const command = sessionId ? `pi --session ${sessionId} "/bye"` : `pi -c "/bye"`;
		// The command sits alone on its line so a triple-click selects it whole,
		// without the hint text in the selection, as pi's own hint now does too.
		try {
			process.stdout.write(`\x1b[2mWrap-up skipped. Close it properly with:\x1b[0m\n${command}\n`);
		} catch {
			// A signal shutdown can reach here with the terminal already gone.
		}
	});
}
