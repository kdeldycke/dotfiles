/**
 * `/cmd [n]`: copy one fenced code block from the last assistant message to
 * the clipboard, raw, without the transcript's soft wrapping.
 *
 * A mouse selection copies rendered screen cells, so a long line that the
 * transcript wrapped pastes back with literal line breaks and padding
 * spaces. Pi already exposes the raw text through `/copy` (`app.message.copy`
 * -> `getLastAssistantText()` in agent-session.js), but that copies the whole
 * message, prose included. This command narrows it to a single fenced block,
 * which is the part that gets pasted into a shell.
 *
 * A `shell-session` block copies as commands only: lines carrying the `$ `
 * prompt are kept with the prompt stripped, sample output between them is
 * dropped. A block with no prompted lines, and any block tagged with a
 * non-shell language, copies verbatim.
 *
 * After each agent run the copyable blocks are listed in a themed row above
 * the editor (`setWidget`), refreshed again on session start. The row shows
 * only from two blocks up: with a single block the transcript already
 * displays it and a bare "/cmd" copies it, so a hint would repeat what is on
 * screen. Typing "/cmd" followed by a space offers the blocks as editor
 * completions, which works even when the row is hidden.
 *
 * The row is a widget and not extension status text (`setStatus`). Status text
 * reaches the footer through a pipeline that drops the ESC byte and leaves the
 * rest of the sequence on screen as literal `[38;2;...m` characters, so a
 * themed status line is unreadable. A widget renders as a component, the way
 * pi's own borders and markdown do, so theme colors survive.
 *
 * `pbcopy` is macOS-only, which matches the one machine this runs on.
 */

import { spawn } from "node:child_process";

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

/** An opening or closing code fence, capturing its indentation. */
const FENCE_RE = /^(\s*)(`{3,}|~{3,})/;

/** A `$ `-prompted command line in a session transcript block. */
const PROMPT_RE = /^\s*\$\s?/;

/** Info strings whose blocks may hold a prompted session transcript. */
const SESSION_LANG_RE = /^(shell|console|sh|bash|zsh)([-.][a-z0-9-]*)?$/;

/** Maximum characters of a block's first line shown in the list. */
const SUMMARY_MAX = 48;

/** Widget key for the block hint row. Distinct from starship-row's key. */
const WIDGET_KEY = "cmd-blocks-hint";

/** Characters of each block's first line shown in the footer hint. */
const STATUS_SUMMARY_MAX = 24;

/** Blocks shown in the hint row before a "+N more" suffix takes over. */
const STATUS_SHOWN_MAX = 3;

/** Box-drawing light vertical, the adopted entry separator. */
const BAR = "\u2502";

/**
 * The prompt invite, shared with the zsh prompt: starship's default character
 * module draws a bold green U+276F, and this row opens with the same glyph so
 * a copyable answer reads like a command waiting to run.
 */
const PROMPT = "\u276f ";

/** Blocks of the last assistant message, primed by `refreshHint()`. */
let lastBlocks: CodeBlock[] = [];

/** One run of text and the theme token that colors it. */
interface Segment {
	text: string;
	/** Theme color token, or null for the terminal default. */
	token: string | null;
	/** Render in bold, the way starship draws the shell prompt character. */
	bold?: boolean;
}

/** Structural slice of `Theme` used to color the hint row. */
interface ThemeLike {
	fg(token: string, text: string): string;
	bold(text: string): string;
}

/** Structural slice of a pi TUI component, enough for one static row. */
interface WidgetLike {
	render(width: number): string[];
}

/**
 * A one-line widget painting the block hint in theme colors.
 *
 * Entries are laid out whole: when the next one does not fit the width pi
 * handed the widget, it is dropped rather than cut mid-prefix. Only the first
 * entry is ever char-truncated, for terminals narrower than one entry.
 */
class HintRow implements WidgetLike {
	private readonly entries: Segment[][];
	private readonly theme: () => ThemeLike;

	constructor(entries: Segment[][], theme: () => ThemeLike) {
		this.entries = entries;
		this.theme = theme;
	}

	render(width: number): string[] {
		if (width <= 0) return [];
		let budget = width;
		let line = "";
		for (const [index, entry] of this.entries.entries()) {
			const plainWidth = entry.reduce((sum, segment) => sum + segment.text.length, 0);
			if (plainWidth <= budget) {
				line += this.paint(entry);
				budget -= plainWidth;
				continue;
			}
			// The first entry may be cut; a later one would start mid-row with a
			// bar and half a prefix, which reads as corruption.
			if (index === 0) line += this.paint(this.cut(entry, budget));
			break;
		}
		return line ? [line] : [];
	}

	private paint(entry: Segment[]): string {
		return entry
			.map((segment) => {
				const text = segment.token === null ? segment.text : this.theme().fg(segment.token, segment.text);
				return segment.bold ? this.theme().bold(text) : text;
			})
			.join("");
	}

	/** Char-truncate an entry's last segment to fit the budget. */
	private cut(entry: Segment[], budget: number): Segment[] {
		const out: Segment[] = [];
		let left = budget;
		for (const segment of entry) {
			if (left <= 0) break;
			out.push({ ...segment, text: segment.text.slice(0, left) });
			left -= segment.text.length;
		}
		return out;
	}
}

/** One fenced code block extracted from assistant markdown. */
interface CodeBlock {
	/** Info string from the opening fence, lowercased, empty when absent. */
	lang: string;
	/** Text to copy: commands only for a prompted transcript, raw otherwise. */
	content: string;
	/** First line to run or show, truncated, for the block list display. */
	summary: string;
}

/**
 * Text content of the last assistant message in the session, or undefined.
 * Mirrors `AgentSession.getLastAssistantText()`, including its skip of an
 * aborted message that carries no content.
 */
function lastAssistantText(entries: readonly unknown[]): string | undefined {
	for (let index = entries.length - 1; index >= 0; index -= 1) {
		// SessionMessageEntry: { type: "message", message: AgentMessage }.
		const entry = entries[index] as
			| { type?: unknown; message?: { role?: unknown; content?: unknown; stopReason?: unknown } }
			| null;
		if (!entry || entry.type !== "message" || !entry.message) continue;
		if (entry.message.role !== "assistant") continue;
		const content = entry.message.content;
		if (!Array.isArray(content)) continue;
		if (entry.message.stopReason === "aborted" && content.length === 0) continue;
		let text = "";
		for (const block of content) {
			if (typeof block === "object" && block !== null && (block as { type?: unknown }).type === "text") {
				text += String((block as { text?: unknown }).text ?? "");
			}
		}
		const trimmed = text.trim();
		if (trimmed) return trimmed;
	}
	return undefined;
}

/** Build one block, keeping only command lines from a prompted transcript. */
function makeBlock(lang: string, lines: readonly string[]): CodeBlock {
	let content = lines.join("\n");
	const prompted = lines.some((line) => PROMPT_RE.test(line));
	if (prompted && (lang === "" || SESSION_LANG_RE.test(lang))) {
		const commands = lines
			.filter((line) => PROMPT_RE.test(line))
			.map((line) => line.replace(PROMPT_RE, ""))
			.filter((line) => line.trim().length > 0);
		if (commands.length > 0) content = commands.join("\n");
	}
	const first = content.split("\n").find((line) => line.trim().length > 0) ?? "";
	const summary = first.length > SUMMARY_MAX ? `${first.slice(0, SUMMARY_MAX - 3)}...` : first;
	return { lang, content, summary };
}

/** Split assistant markdown into its fenced code blocks. */
function extractBlocks(markdown: string): CodeBlock[] {
	const blocks: CodeBlock[] = [];
	const lines = markdown.split("\n");
	let open: string[] | null = null;
	let openIndent = 0;
	let lang = "";
	for (const line of lines) {
		const fence = FENCE_RE.exec(line);
		if (open === null) {
			if (fence) {
				openIndent = fence[1].length;
				lang = line.slice(fence[0].length).trim().toLowerCase();
				open = [];
			}
		} else if (fence && fence[1].length <= openIndent) {
			blocks.push(makeBlock(lang, open));
			open = null;
		} else {
			open.push(line);
		}
	}
	// An unterminated fence is dropped: half a block is worse than none.
	return blocks;
}

/** Write text to the clipboard through macOS `pbcopy`. */
function writeClipboard(text: string): Promise<void> {
	return new Promise((resolve, reject) => {
		const child = spawn("pbcopy", { stdio: ["pipe", "ignore", "ignore"] });
		child.once("error", reject);
		child.once("close", (code) => {
			if (code === 0) resolve();
			else reject(new Error(`pbcopy exited with status ${code}.`));
		});
		child.stdin.once("error", reject);
		child.stdin.end(text, "utf8");
	});
}

/**
 * Hint row segments, in the adopted layout: every entry repeats its own
 * `/cmd n:` prefix so it reads on its own, and a box-drawing bar in
 * borderMuted separates the entries. That token sits below the dim summaries,
 * so the bar groups without competing with any text.
 */
function hintSegments(blocks: readonly CodeBlock[]): Segment[][] {
	const entries: Segment[][] = blocks.slice(0, STATUS_SHOWN_MAX).map((block, i) => [
		...(i === 0 ? [{ text: PROMPT, token: "accent", bold: true }] : []),
		...(i > 0 ? [{ text: ` ${BAR} `, token: "borderMuted" as string | null }] : []),
		{ text: "/cmd", token: "accent" },
		{ text: ` ${i + 1}: `, token: "accent" },
		{ text: block.summary.slice(0, STATUS_SUMMARY_MAX), token: "dim" },
	]);
	if (blocks.length > STATUS_SHOWN_MAX) {
		entries.push([
			{ text: ` ${BAR} `, token: "borderMuted" },
			{ text: `+${blocks.length - STATUS_SHOWN_MAX} more`, token: "muted" },
		]);
	}
	return entries;
}

/** Refresh or clear the hint row against the current session state. */
function refreshHint(ctx: ExtensionContext): void {
	// The widget renders only in the TUI; print and JSON modes have no editor row.
	if (ctx.mode !== "tui") {
		lastBlocks = [];
		return;
	}
	try {
		const markdown = lastAssistantText(ctx.sessionManager.getEntries());
		const blocks = markdown ? extractBlocks(markdown) : [];
		lastBlocks = blocks;
		// One block needs no index: bare "/cmd" copies it, and the transcript
		// already shows it. The row earns its line only from two blocks up.
		if (blocks.length >= 2) {
			const entries = hintSegments(blocks);
			// Reading the theme per render keeps the colors right after a theme switch.
			ctx.ui.setWidget(WIDGET_KEY, () => new HintRow(entries, () => ctx.ui.theme), {
				placement: "aboveEditor",
			});
		} else {
			ctx.ui.setWidget(WIDGET_KEY, undefined);
		}
	} catch {
		lastBlocks = [];
		// A hint must never fail an agent run.
	}
}

export default function (pi: ExtensionAPI): void {
	pi.registerCommand("cmd", {
		description: "Copy a fenced code block from the last agent message to the clipboard",
		// "/cmd" + Tab lists the blocks: the index picker that works with the
		// footer line hidden, and the one channel print mode cannot serve.
		getArgumentCompletions: (argumentPrefix: string) => {
			const prefix = argumentPrefix.trim().toLowerCase();
			if (prefix === "" || /^\d/.test(prefix)) {
				const items = lastBlocks.map((block, i) => ({
					value: String(i + 1),
					label: String(i + 1),
					description: `${block.content.length} chars: ${block.summary}`,
				}));
				const matching = items.filter((item) => item.value.startsWith(prefix));
				return matching.length > 0 ? matching : null;
			}
			if ("list".startsWith(prefix)) {
				return [{ value: "list", label: "list", description: "List the blocks" }];
			}
			return null;
		},
		handler: async (args: string, ctx) => {
			const markdown = lastAssistantText(ctx.sessionManager.getEntries());
			if (!markdown) {
				ctx.ui.notify("No agent message to copy from yet.", "error");
				return;
			}
			const blocks = extractBlocks(markdown);
			if (blocks.length === 0) {
				ctx.ui.notify("The last agent message has no fenced code block.", "error");
				return;
			}
			const arg = args.trim().toLowerCase();
			if (arg === "list" || arg === "ls" || arg === "l") {
				const listing = blocks
					.map((block, i) => `${i + 1}. ${block.summary}  (${block.content.length} chars)`)
					.join("\n");
				ctx.ui.notify(listing, "info");
				return;
			}
			let index = blocks.length;
			if (arg !== "") {
				if (!/^\d+$/.test(arg)) {
					ctx.ui.notify('Usage: "/cmd [n]" copies block n, "/cmd" the last block, "/cmd list" lists them.', "error");
					return;
				}
				index = Number.parseInt(arg, 10);
				if (index < 1 || index > blocks.length) {
					ctx.ui.notify(`Block index must be 1 to ${blocks.length}. Use "/cmd list".`, "error");
					return;
				}
			}
			const block = blocks[index - 1];
			try {
				await writeClipboard(block.content);
				ctx.ui.notify(
					`Copied block ${index} of ${blocks.length} (${block.content.length} chars): ${block.summary}`,
					"info",
				);
			} catch (error) {
				ctx.ui.notify(`Copy failed: ${error instanceof Error ? error.message : String(error)}`, "error");
			}
		},
	});

	// The footer hint follows every agent run, and is rebuilt on session start
	// so it survives a reload into an existing transcript.
	pi.on("agent_end", (_event, ctx) => {
		refreshHint(ctx);
	});
	pi.on("session_start", (_event, ctx) => {
		refreshHint(ctx);
	});
}