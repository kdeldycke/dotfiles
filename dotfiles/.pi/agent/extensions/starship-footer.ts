/**
 * Replace pi's footer with the starship row the shell prompt and the Claude Code status line
 * already use, so all three read the same way.
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
 * starship modules. The cumulative token counts and the cache hit rate arrive as `PI_TOKENS` and
 * `PI_CACHE`, formatted the way pi formatted them: starship reports cache figures only for the
 * last call, where pi totalled them over the session. The context window size arrives as
 * `PI_CTXWINDOW`, since `claude_context` renders a percentage but never the window behind it.
 * The session name comes back through `CC_SESSION`, which the Claude Code row deliberately drops
 * because Claude Code prints it twice elsewhere; pi does not, so here it earns its place.
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
 * ## Refresh
 *
 * `render()` runs on every frame, and starship is a subprocess, so rendering cannot wait for it.
 * The component returns the last row it received and refreshes in the background, asking the TUI
 * to redraw only when the output actually changed. That last condition is what stops the loop:
 * a redraw that produced identical bytes requests nothing.
 */

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

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

/** Format a token count the way pi's footer did, so the row reads identically. */
function formatTokens(count: number): string {
	if (count < 1000) return count.toString();
	if (count < 10000) return `${(count / 1000).toFixed(1)}k`;
	if (count < 1000000) return `${Math.round(count / 1000)}k`;
	if (count < 10000000) return `${(count / 1000000).toFixed(1)}M`;
	return `${Math.round(count / 1000000)}M`;
}

interface Usage {
	input: number;
	output: number;
	cacheRead: number;
	cacheWrite: number;
	cost?: { total?: number };
}

interface Totals extends Usage {
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
	const totals: Totals = {
		input: 0,
		output: 0,
		cacheRead: 0,
		cacheWrite: 0,
		cost: { total: 0 },
	};
	let latest: Usage | undefined;
	for (const entry of ctx.sessionManager.getEntries()) {
		const found = entryUsage(entry);
		if (!found) continue;
		totals.input += found.usage.input ?? 0;
		totals.output += found.usage.output ?? 0;
		totals.cacheRead += found.usage.cacheRead ?? 0;
		totals.cacheWrite += found.usage.cacheWrite ?? 0;
		totals.cost.total += found.usage.cost?.total ?? 0;
		if (found.assistant) latest = found.usage;
	}
	return { totals, latest };
}

const SHED = ["PI_CACHE", "provider", "session", "PI_TOKENS"] as const;
/**
 * What to drop, in order, when the rendered row is wider than the terminal.
 *
 * Fixed width thresholds would not survive here: a pi model id runs from `opus` to
 * `qwen/qwen3.8-max` behind an `(openrouter)` prefix, so the same terminal fits everything for
 * one model and overflows for another. The component measures what starship actually returned
 * and sheds one more item until it fits, which needs no calibration and follows a model switch
 * on its own. Least perishable first: a cache rate and a provider name repeat every turn, while
 * the token totals are the reading that changes.
 */

type ShedItem = (typeof SHED)[number];

/** Visible width of a rendered row, ignoring colour and counting wide glyphs as two columns. */
function visibleWidth(text: string): number {
	let width = 0;
	for (const char of text.replace(/\x1b\[[0-9;]*m/g, "")) {
		const code = char.codePointAt(0) ?? 0;
		const wide =
			(code >= 0x1100 && code <= 0x115f) ||
			(code >= 0x2e80 && code <= 0xa4cf) ||
			(code >= 0xac00 && code <= 0xd7a3) ||
			(code >= 0xf900 && code <= 0xfaff) ||
			(code >= 0xfe30 && code <= 0xfe6f) ||
			(code >= 0xff00 && code <= 0xff60) ||
			(code >= 0xffe0 && code <= 0xffe6) ||
			(code >= 0x1f300 && code <= 0x1f64f) ||
			(code >= 0x1f900 && code <= 0x1f9ff);
		width += wide ? 2 : 1;
	}
	return width;
}

/** Name the model the way pi's footer did, keeping the provider when there is room for it. */
function modelLabel(ctx: ExtensionContext, shed: ReadonlySet<ShedItem>): string {
	const model = ctx.model;
	if (!model) return "no-model";
	return shed.has("provider") ? model.id : `(${model.provider}) ${model.id}`;
}

/**
 * Build the payload in the shape Claude Code sends, so `statusline.py` needs no pi-specific code.
 *
 * `effort.level` is where pi's thinking level goes: the wrapper reads that field into `CC_FLAGS`,
 * which is the same slot Claude Code's reasoning effort occupies.
 */
function buildPayload(
	ctx: ExtensionContext,
	shed: ReadonlySet<ShedItem>,
): Record<string, unknown> {
	const { totals, latest } = collectUsage(ctx);
	const cwd = ctx.sessionManager.getCwd();
	const context = ctx.getContextUsage();
	const reasoning = (ctx.model as { reasoning?: unknown } | undefined)?.reasoning;
	const thinking = ctx.thinkingLevel;
	const sessionName = shed.has("session") ? undefined : ctx.sessionManager.getSessionName();

	return {
		hook_event_name: "Status",
		model: { id: ctx.model?.id ?? "", display_name: modelLabel(ctx, shed) },
		cwd,
		workspace: { current_dir: cwd, project_dir: cwd },
		session_name: sessionName || undefined,
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
function buildEnvironment(
	ctx: ExtensionContext,
	shed: ReadonlySet<ShedItem>,
): Record<string, string> {
	const { totals, latest } = collectUsage(ctx);
	const environment: Record<string, string> = {};

	const parts: string[] = [];
	if (totals.input) parts.push(`↑${formatTokens(totals.input)}`);
	if (totals.output) parts.push(`↓${formatTokens(totals.output)}`);
	if (totals.cacheRead) parts.push(`R${formatTokens(totals.cacheRead)}`);
	if (totals.cacheWrite) parts.push(`W${formatTokens(totals.cacheWrite)}`);
	if (parts.length && !shed.has("PI_TOKENS")) environment.PI_TOKENS = parts.join(" ");

	if (latest && !shed.has("PI_CACHE") && (totals.cacheRead > 0 || totals.cacheWrite > 0)) {
		const prompt = (latest.input ?? 0) + (latest.cacheRead ?? 0) + (latest.cacheWrite ?? 0);
		if (prompt > 0) {
			environment.PI_CACHE = `CH${(((latest.cacheRead ?? 0) / prompt) * 100).toFixed(1)}%`;
		}
	}

	const context = ctx.getContextUsage();
	if (context?.contextWindow) {
		// A trailing "?" marks a known window whose percentage is not: the gauge reads empty
		// there, where pi printed "?" in place of the number.
		const unknown = context.percent === null ? " ?" : "";
		environment.PI_CTXWINDOW = `/${formatTokens(context.contextWindow)}${unknown}`;
	}

	if (ctx.model?.provider === "kimi-coding") environment.PI_SUB = "(sub)";

	return environment;
}

class StarshipFooter {
	private lines: string[] = [];
	private signature = "";
	private lastRun = 0;
	private running = false;
	private disposed = false;
	private width = 0;
	private shed = 0;

	private readonly tui: RenderTarget;
	private readonly ctx: ExtensionContext;
	private readonly footerData: ReadonlyFooterDataProvider;
	private readonly statusline: string;

	// Plain assignment rather than TypeScript's constructor parameter properties: those need a
	// real transform, so they fail under any strip-only TypeScript loader.
	constructor(
		tui: RenderTarget,
		ctx: ExtensionContext,
		footerData: ReadonlyFooterDataProvider,
		statusline: string,
	) {
		this.tui = tui;
		this.ctx = ctx;
		this.footerData = footerData;
		this.statusline = statusline;
	}

	render(width: number): string[] {
		this.maybeRefresh(width);

		const rendered = this.lines.length > 0 ? [...this.lines] : [];
		// pi's footer devoted its last line to whatever other extensions publish through
		// ctx.ui.setStatus(). Replacing the footer would drop that line silently, with no error
		// to notice, so it is rebuilt here.
		const statuses = this.footerData.getExtensionStatuses();
		if (statuses.size > 0) {
			rendered.push(
				Array.from(statuses.entries())
					.sort(([a], [b]) => a.localeCompare(b))
					.map(([, text]) => text.replace(/[\r\n\t]/g, " ").replace(/ +/g, " ").trim())
					.join(" "),
			);
		}
		return rendered;
	}

	dispose(): void {
		this.disposed = true;
	}

	private maybeRefresh(width: number): void {
		// A resize invalidates how much was shed: the row may fit whole again, so start from nothing
		// shed and let the measurement decide, rather than staying trimmed for one narrow moment.
		if (width !== this.width) {
			this.width = width;
			this.shed = 0;
		}
		const shed = this.shedSet();
		const inputs = [buildPayload(this.ctx, shed), buildEnvironment(this.ctx, shed)];
		const signature = `${width} ${this.shed} ${JSON.stringify(inputs)}`;
		if (signature === this.signature && Date.now() - this.lastRun < STALE_MS) return;
		this.signature = signature;
		this.run(width);
	}

	private shedSet(): ReadonlySet<ShedItem> {
		return new Set(SHED.slice(0, this.shed));
	}

	private run(width: number): void {
		if (this.running || this.disposed) return;
		this.running = true;
		this.lastRun = Date.now();

		const shed = this.shedSet();
		const payload = buildPayload(this.ctx, shed);
		// pi hands the component its exact usable width, so it is stated rather than left to the
		// wrapper's COLUMNS reading, which subtracts a margin for the narrower box Claude Code draws.
		const child = spawn(this.statusline, ["--profile", PROFILE, "--terminal-width", String(width)], {
			env: { ...process.env, ...buildEnvironment(this.ctx, shed), COLUMNS: String(width) },
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
			const lines = output.replace(/\n+$/, "").split("\n");

			// Measure what came back instead of predicting it. Overflowing means pi truncates the row,
			// so drop the next item and render again. The retry is bounded by SHED's length.
			if (lines.some((line) => visibleWidth(line) > width) && this.shed < SHED.length) {
				this.shed += 1;
				this.signature = "";
				this.run(width);
				return;
			}

			if (lines.join("\n") === this.lines.join("\n")) return;
			this.lines = lines;
			// Only on a real change, or this redraw would request the next one forever.
			this.tui.requestRender();
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

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (_event, ctx) => {
		// Only the TUI has a footer to replace. In print and RPC modes setFooter is a no-op at
		// best, and the subprocess per frame would be pure cost.
		if (ctx.mode !== "tui") return;
		const statusline = resolveStatusline();
		if (!statusline) {
			// Leaving pi's own footer in place beats replacing it with a blank row.
			ctx.ui.notify("starship-footer: statusline.py not found, keeping pi's footer", "warning");
			return;
		}
		ctx.ui.setFooter((tui, _theme, footerData) =>
			new StarshipFooter(tui as RenderTarget, ctx, footerData, statusline),
		);
	});
}
