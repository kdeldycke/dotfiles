/**
 * Render the starship row the shell prompt and the Claude Code status line already use, so all
 * three read the same way, and place it above pi's editor rather than below it.
 *
 * ## Why a widget and not the footer
 *
 * Above the editor the row reads like a shell prompt: the state first, then the line you type
 * on. `ctx.ui.setWidget` takes exactly that placement, and `aboveEditor` is even its default,
 * so no upstream change is needed. Claude Code has no equivalent: its `statusLine` accepts only
 * `type`, `command` and `padding`, and always renders at the bottom.
 *
 * The trade is that a widget factory receives `(tui, theme)` and no `FooterDataProvider`, where
 * a footer factory gets one. Only `getExtensionStatuses()` is lost with it, so the footer stays
 * on as {py:class}`ExtensionStatusFooter`, rendering that and nothing else.
 *
 * The rendering itself is not done here. `dotfiles/.claude/statusline.py` already maps a session
 * onto starship, and this extension feeds it the same JSON shape Claude Code sends on stdin,
 * asking for the `pi` profile instead of `claude-code`. Anything with no Claude Code counterpart
 * travels as an environment variable: that wrapper forwards its whole environment, and the
 * `[env_var.PI_*]` blocks in `starship.toml` render them. So the field mapping lives in one
 * place rather than being written twice in two languages.
 *
 * ## What pi's own footer showed and this one keeps
 *
 * Directory, git branch, model, thinking level, cost and context percentage come back through
 * starship modules. The session name comes back through `CC_SESSION`, prefix and all, and loses
 * its tail to an ellipsis only when the terminal has no room for the whole of it. The Claude Code
 * row drops the name entirely, because Claude Code prints it twice elsewhere; pi does not, so
 * here it earns its place. `PI_CTXWINDOW` survives as
 * the bare `?` that marks a known window whose percentage is not, the one thing
 * `claude_context` cannot say: its gauge reads empty there, which reads as zero rather than as
 * unknown. The cumulative token counts and the cache hit rate pi's footer printed are gone from
 * the row: the cost already prices the session, and the counts only restated that price in
 * tokens.
 *
 * ## What it cannot keep
 *
 * Three values pi's footer printed are not reachable from the extension API, and are dropped
 * rather than faked:
 *
 * - The `(auto)` auto-compaction marker. `ExtensionContext` has no auto-compact field; pi's own
 *   footer receives it through `setAutoCompactEnabled()`, a direct call onto the concrete
 *   component that no extension can intercept.
 * - The `xp` experimental-features flag. `areExperimentalFeaturesEnabled()` is not exported from
 *   the package root, and the `exports` map has no subpath that would reach it.
 * - `(sub)` for subscription-backed cost, in the general case. That test is
 *   `ModelRuntime.isUsingSubscription()`, and the context exposes `modelRegistry` rather than
 *   `modelRuntime`. Only pi's hardcoded `kimi-coding` provider is checkable from here, so that
 *   one case is kept and the rest is not.
 *
 * ```{todo}
 * Ask upstream to put `autoCompactEnabled`, the experimental flag and a subscription predicate
 * on `ExtensionContext`. All three are read-only facts about the session that pi's own footer
 * prints, so any extension replacing the footer needs them to reach parity.
 * ```
 *
 * ## Fitting the terminal
 *
 * pi throws and ends the session when a rendered line is wider than the width it handed the
 * component. That is its documented contract, and a deliberate one, so an extension author learns
 * their component overflowed rather than watching it wrap: the maintainer declined to soften it
 * in [earendil-works/pi#5773](https://github.com/earendil-works/pi/issues/5773). So `render()`
 * clamps every line to the width of the frame it draws, which also covers the frames between a
 * resize and the starship run that answers it: those still hold the row measured for the old,
 * wider terminal.
 *
 * Shortening segments first is what keeps the clamp rare, since a cut row loses its right-hand
 * block, where the context gauge and the cost live, and leaves a powerline glyph dangling. Two
 * segments give way, the directory path and then the session name, see `nextFit`. Starship fills
 * the rest from its own modules, which no variable of `statusline.py` reaches, so a terminal
 * narrower than the row's floor, about 100 columns with a long model label and a dirty tree, gets
 * a cut row.
 *
 * ## Refresh
 *
 * `render()` runs on every frame, and starship is a subprocess, so rendering cannot wait for it.
 * The component returns the last row it received and refreshes in the background, asking the TUI
 * to redraw only when the output actually changed. That last condition is what stops the loop:
 * a redraw that produced identical bytes requests nothing.
 *
 * Inputs that change while a run is in flight start one more refresh when that run ends: the run
 * read the inputs from before the change. An idle session never redraws, so waiting for the next
 * redraw would leave its row on the old cost and context.
 */

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// pi's own measures, not a local copy of them: the renderer compares against these two, so a
// component that measures differently can pass its own check and still be thrown out. Its
// extension loader resolves the specifier to the bundled TUI, which is why the package needs no
// install beside the extension.
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";

import type {
	ExtensionAPI,
	ExtensionContext,
	ReadonlyFooterDataProvider,
	SessionEntry,
} from "@earendil-works/pi-coding-agent";

/** Minimal view of the TUI: the only thing this component asks of it is a redraw. */
interface RenderTarget {
	requestRender(force?: boolean): void;
}

const PROFILE = "pi";
const WIDGET_KEY = "starship-row";

const STALE_MS = 2000;
/**
 * How long a rendered row is trusted before starship is asked again, even with identical inputs.
 *
 * The session payload cannot detect everything the row shows: git status flags, the working-tree
 * diff and the python version all come from disk, and starship reads them itself. Re-running on a
 * timer is what notices an edit. `render()` only fires on a redraw, so an idle session spawns
 * nothing.
 */

const STATUSLINE_FALLBACK = join(
	homedir(),
	"code/dotfiles/dotfiles/.claude/statusline.py",
);
/**
 * Where to find the wrapper when the path relative to this file does not resolve.
 *
 * `~/.pi/agent/extensions` is a symlink into the dotfiles checkout. Resolving `../../../` works
 * when pi loads the extension through its real path, and lands in `$HOME` when it loads through
 * the symlink, where no `.claude/statusline.py` exists.
 */

function resolveStatusline(): string | undefined {
	const here = dirname(fileURLToPath(import.meta.url));
	for (const candidate of [
		resolve(here, "../../../.claude/statusline.py"),
		STATUSLINE_FALLBACK,
	]) {
		if (existsSync(candidate)) return candidate;
	}
	return undefined;
}

interface Usage {
	input: number;
	output: number;
	cacheRead: number;
	cacheWrite: number;
	cost?: { total?: number };
}

interface Totals {
	input: number;
	output: number;
	cost: { total: number };
}

/**
 * Pull usage off a session entry, covering the same four entry shapes pi's footer counted.
 *
 * Assistant messages and tool results carry their own usage; a branch summary or a compaction
 * carries the usage of the call that produced it. Missing any of them would understate the
 * totals against what pi printed.
 */
function entryUsage(entry: SessionEntry): { usage: Usage; assistant: boolean } | undefined {
	const record = entry as unknown as {
		type: string;
		usage?: Usage;
		message?: { role?: string; usage?: Usage };
	};
	if (record.type === "message" && record.message?.usage) {
		const role = record.message.role;
		if (role === "assistant" || role === "toolResult") {
			return { usage: record.message.usage, assistant: role === "assistant" };
		}
		return undefined;
	}
	if ((record.type === "branch_summary" || record.type === "compaction") && record.usage) {
		return { usage: record.usage, assistant: false };
	}
	return undefined;
}

function collectUsage(ctx: ExtensionContext): { totals: Totals; latest?: Usage } {
	const totals: Totals = { input: 0, output: 0, cost: { total: 0 } };
	let latest: Usage | undefined;
	for (const entry of ctx.sessionManager.getEntries()) {
		const found = entryUsage(entry);
		if (!found) continue;
		totals.input += found.usage.input ?? 0;
		totals.output += found.usage.output ?? 0;
		totals.cost.total += found.usage.cost?.total ?? 0;
		if (found.assistant) latest = found.usage;
	}
	return { totals, latest };
}

/**
 * How much of the row gives way when it is wider than the terminal.
 *
 * Fixed width thresholds would not survive here: a pi model label runs from `anthropic:opus` to
 * `openrouter:qwen3.8-max-0902`, so the same terminal fits everything for one model and
 * overflows for another. The component measures what starship actually returned and gives up a
 * little more until it fits, which needs no calibration and follows a model switch on its own.
 * The model name never gives way: an elided one names no model the picker could list.
 */
interface Fit {
	/** Print the path `abbreviatePath` returns instead of the real one. */
	shortPath: boolean;
	/** Widest the session name may print, in columns: unset prints it whole, 0 drops it. */
	sessionWidth?: number;
}

const WHOLE: Fit = { shortPath: false };

const SESSION_MIN_WIDTH = 16;
/**
 * Narrowest the session name prints, in columns, before the row drops it.
 *
 * A name `session-title.ts` writes opens on an 11-column timestamp, and a cut that leaves little
 * more reads as the clock `DEFAULT_SESSION_NAME` keeps off the row.
 */

const ELLIPSIS = "…";

const GRAPHEMES = new Intl.Segmenter(undefined, { granularity: "grapheme" });

/**
 * Abbreviate every directory above the working one to its initial: `~/L/C/P/Network & machines`.
 *
 * Same rule as the `directory` module applies past its `truncation_length`, a leading dot keeping
 * the letter after it, so starship prints the result as given. The home prefix stays whole, for
 * starship to contract to `~`.
 */
function abbreviatePath(path: string): string {
	const home = homedir();
	const base = path === home || path.startsWith(`${home}/`) ? home : "";
	const parts = path.slice(base.length).split("/").filter(Boolean);
	const leaf = parts.pop();
	if (leaf === undefined) return path;
	const initials = parts.map((part) =>
		Array.from(GRAPHEMES.segment(part), ({ segment }) => segment)
			.slice(0, part.startsWith(".") ? 2 : 1)
			.join(""),
	);
	return [base, ...initials, leaf].join("/");
}

/**
 * Cut plain text to `width` columns, ending on an ellipsis when anything was cut.
 *
 * pi-tui's `truncateToWidth` wraps its ellipsis in ANSI resets, which inside a starship segment
 * clear the background too and leave a hole in the block.
 */
function elide(text: string, width: number): string {
	if (visibleWidth(text) <= width) return text;
	const room = width - visibleWidth(ELLIPSIS);
	let kept = "";
	let used = 0;
	for (const { segment } of GRAPHEMES.segment(text)) {
		used += visibleWidth(segment);
		if (used > room) break;
		kept += segment;
	}
	return `${kept.trimEnd()}${ELLIPSIS}`;
}

/**
 * Name the model under its provider's full name: `openrouter:qwen3.8-max-0902`. The prefix says
 * where the model is consumed from, in the grammar of a fully qualified image or coordinate, and
 * costs nine columns over the bare id, which the row takes from the path and the session name
 * before it ever truncates. A family prefix before a slash in the id still goes, since it only
 * repeats the model's own name.
 */
function modelLabel(ctx: ExtensionContext): string {
	const model = ctx.model;
	if (!model) return "no-model";
	const name = model.id.slice(model.id.lastIndexOf("/") + 1);
	return `${model.provider}:${name}`;
}

/** pi's fallback name for a session nobody renamed: its creation time, which would read as a clock. */
const DEFAULT_SESSION_NAME = /^\d{2}-\d{2}@\d{2}:\d{2}$/;

/**
 * The session name the row prints, before any fitting, or `undefined` for none.
 *
 * pi names an unrenamed session after its creation time, and a frozen timestamp on the row reads
 * as a clock that stalls while the session ages. No row draws a clock, so the stored name earns
 * its column only once it says more: a `/rename`, or the summary `session-title.ts` adds at exit.
 */
function sessionName(ctx: ExtensionContext): string | undefined {
	const stored = ctx.sessionManager.getSessionName();
	return stored && !DEFAULT_SESSION_NAME.test(stored) ? stored : undefined;
}

/**
 * The fit to try after a row came back `overflow` columns too wide, or `undefined` once nothing
 * is left to give way and `render()` clamps the row.
 *
 * The path gives way first: its abbreviation keeps the working directory whole, where a cut name
 * loses words. The name then loses exactly the overflow: starship prints one fill glyph even on a
 * row too wide for `$fill`, and the overflow counts it, so the cut row lands on the terminal width.
 */
function nextFit(ctx: ExtensionContext, fit: Fit, overflow: number): Fit | undefined {
	const cwd = ctx.sessionManager.getCwd();
	if (!fit.shortPath && abbreviatePath(cwd) !== cwd) return { ...fit, shortPath: true };
	const name = sessionName(ctx);
	if (!name || fit.sessionWidth === 0) return undefined;
	const shown = fit.sessionWidth === undefined ? name : elide(name, fit.sessionWidth);
	const width = visibleWidth(shown) - overflow;
	return { ...fit, sessionWidth: width >= SESSION_MIN_WIDTH ? width : 0 };
}

/**
 * Build the payload in the shape Claude Code sends, so `statusline.py` needs no pi-specific code.
 *
 * `effort.level` is where pi's thinking level goes: the `claude_model` format renders that field
 * as `$effort`, the same slot Claude Code's reasoning effort occupies.
 */
function buildPayload(ctx: ExtensionContext, fit: Fit): Record<string, unknown> {
	const { totals, latest } = collectUsage(ctx);
	const cwd = ctx.sessionManager.getCwd();
	const context = ctx.getContextUsage();
	const reasoning = (ctx.model as { reasoning?: unknown } | undefined)?.reasoning;
	const thinking = ctx.thinkingLevel;
	const name = fit.sessionWidth === 0 ? undefined : sessionName(ctx);

	return {
		hook_event_name: "Status",
		model: { id: ctx.model?.id ?? "", display_name: modelLabel(ctx) },
		cwd,
		workspace: { current_dir: cwd, project_dir: cwd },
		session_name: name && fit.sessionWidth !== undefined ? elide(name, fit.sessionWidth) : name,
		effort: reasoning && thinking ? { level: thinking } : undefined,
		context_window: {
			context_window_size: context?.contextWindow ?? 0,
			total_input_tokens: totals.input,
			total_output_tokens: totals.output,
			used_percentage: context?.percent ?? 0,
			current_usage: {
				input_tokens: latest?.input ?? 0,
				output_tokens: latest?.output ?? 0,
				cache_creation_input_tokens: latest?.cacheWrite ?? 0,
				cache_read_input_tokens: latest?.cacheRead ?? 0,
			},
		},
		cost: {
			total_cost_usd: totals.cost.total,
			total_duration_ms: 0,
			total_api_duration_ms: 0,
			total_lines_added: 0,
			total_lines_removed: 0,
		},
	};
}

/** Values pi printed that no starship module reproduces, passed through the environment. */
function buildEnvironment(ctx: ExtensionContext): Record<string, string> {
	const environment: Record<string, string> = {};

	const context = ctx.getContextUsage();
	if (context?.contextWindow && context.percent === null) {
		// The gauge reads empty between a compaction and the next response, where the window is
		// known and the percentage is not: the "?" says which of the two is missing. The window
		// size itself earns no column, since it is constant per model and the gauge and the
		// percentage already state the fill.
		environment.PI_CTXWINDOW = "?";
	}

	if (ctx.model?.provider === "kimi-coding") environment.PI_SUB = "(sub)";

	return environment;
}

class StarshipRow {
	private lines: string[] = [];
	private signature = "";
	private lastRun = 0;
	private running = false;
	private pending = false;
	private disposed = false;
	private width = 0;

	private readonly tui: RenderTarget;
	private readonly ctx: ExtensionContext;
	private readonly statusline: string;

	// Plain assignment rather than TypeScript's constructor parameter properties: those need a
	// real transform, so they fail under any strip-only TypeScript loader.
	constructor(tui: RenderTarget, ctx: ExtensionContext, statusline: string) {
		this.tui = tui;
		this.ctx = ctx;
		this.statusline = statusline;
	}

	render(width: number): string[] {
		this.maybeRefresh(width);

		// Clamped per frame rather than stored clamped: the same row fits one terminal and not the
		// next, and the rows held here were measured for the width the last starship run was given.
		// No ellipsis, because a cut on this row lands inside a powerline block, where three dots
		// read as content rather than as a missing tail.
		return this.lines.map((line) =>
			visibleWidth(line) > width ? truncateToWidth(line, width, "") : line,
		);
	}

	dispose(): void {
		this.disposed = true;
	}

	private maybeRefresh(width: number): void {
		// What overflowed a moment ago may fit now: a resize changes the room, and a commit removes
		// the git status and diff counts that pushed the row over. So each refresh starts again from
		// the whole row and lets the measurement decide how much gives way.
		this.width = width;
		const stale = Date.now() - this.lastRun >= STALE_MS;
		const inputs = [buildPayload(this.ctx, WHOLE), buildEnvironment(this.ctx)];
		const signature = `${width} ${JSON.stringify(inputs)}`;
		if (signature === this.signature && !stale) return;
		// Not stored yet: the run in flight read the old inputs, see Refresh above.
		if (this.running) {
			this.pending = true;
			return;
		}
		this.pending = false;
		this.signature = signature;
		this.run(width, WHOLE);
	}

	private run(width: number, fit: Fit): void {
		if (this.running || this.disposed) return;
		this.running = true;
		this.lastRun = Date.now();

		const payload = buildPayload(this.ctx, fit);
		// pi hands the component its exact usable width, so it is stated rather than left to the
		// wrapper's COLUMNS reading, which subtracts a margin for the narrower box Claude Code draws.
		const args = ["--profile", PROFILE, "--terminal-width", String(width)];
		// The display path only: `statusline.py` still hands starship the real one, for git.
		if (fit.shortPath) {
			args.push("--logical-path", abbreviatePath(this.ctx.sessionManager.getCwd()));
		}
		const child = spawn(this.statusline, args, {
			env: { ...process.env, ...buildEnvironment(this.ctx), COLUMNS: String(width) },
			stdio: ["pipe", "pipe", "ignore"],
		});

		let output = "";
		child.stdout.setEncoding("utf8");
		child.stdout.on("data", (chunk: string) => {
			output += chunk;
		});
		child.on("error", () => {
			this.running = false;
		});
		child.on("close", () => {
			this.running = false;
			if (this.disposed) return;
			// A run that started before a resize measured the old width. Its overflow says nothing
			// about the new width, so drop the result and measure again.
			if (width !== this.width) {
				this.signature = "";
				this.tui.requestRender();
				return;
			}
			const lines = output.replace(/\n+$/, "").split("\n");

			// Measure what came back instead of predicting it. An overflowing row is worth another
			// run with the next fit, since a shortened segment reads better than a cut row. Past the
			// last fit `render()` clamps what is left.
			const overflow = Math.max(...lines.map((line) => visibleWidth(line))) - width;
			const next = overflow > 0 ? nextFit(this.ctx, fit, overflow) : undefined;
			if (next) {
				this.run(width, next);
				return;
			}

			if (lines.join("\n") !== this.lines.join("\n")) {
				this.lines = lines;
				// Only on a real change, or this redraw would request the next one forever.
				this.tui.requestRender();
			}
			if (this.pending) this.maybeRefresh(this.width);
		});
		// An extension must never take down the host TUI. A failed spawn destroys stdin before this
		// runs, and a child that exits early makes the write an EPIPE, so neither may throw.
		child.stdin.on("error", () => {
			this.running = false;
		});
		try {
			child.stdin.end(JSON.stringify(payload));
		} catch {
			this.running = false;
		}
	}
}

/**
 * All that is left of the footer: the statuses other extensions publish via `ctx.ui.setStatus()`.
 *
 * pi's built-in footer devoted its last line to them. Replacing that footer with nothing would
 * drop the line silently, with no error for the author of such an extension to notice, so this
 * keeps rendering it. With no statuses set, it returns no rows and costs no terminal line.
 */
class ExtensionStatusFooter {
	private readonly footerData: ReadonlyFooterDataProvider;

	constructor(footerData: ReadonlyFooterDataProvider) {
		this.footerData = footerData;
	}

	render(width: number): string[] {
		const statuses = this.footerData.getExtensionStatuses();
		if (statuses.size === 0) return [];
		// Joined without a bound, so the clamp is what keeps the sum of every extension's status
		// inside the width pi handed the footer. Same contract as the row above.
		return [
			truncateToWidth(
				Array.from(statuses.entries())
					.sort(([a], [b]) => a.localeCompare(b))
					.map(([, text]) => text.replace(/[\r\n\t]/g, " ").replace(/ +/g, " ").trim())
					.join(" "),
				width,
				"",
			),
		];
	}
}

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (_event, ctx) => {
		// Only the TUI has an editor to sit above. In print and RPC modes the widget goes nowhere
		// and the subprocess per frame would be pure cost.
		if (ctx.mode !== "tui") return;
		const statusline = resolveStatusline();
		if (!statusline) {
			// Leaving pi's own footer in place beats replacing it with a blank row.
			ctx.ui.notify("starship-row: statusline.py not found, keeping pi's footer", "warning");
			return;
		}
		// Above the editor, not below it, so the row reads like a shell prompt: state first, then
		// the line you type on. `aboveEditor` is the default, and is stated here to say it is meant.
		ctx.ui.setWidget(
			WIDGET_KEY,
			(tui, _theme) => new StarshipRow(tui as RenderTarget, ctx, statusline),
			{ placement: "aboveEditor" },
		);
		ctx.ui.setFooter((_tui, _theme, footerData) => new ExtensionStatusFooter(footerData));
	});
}
