/**
 * Apply Claude Code's `Bash(...)` deny rules to pi's `bash` tool.
 *
 * ## Why an extension
 *
 * pi has no permission layer: it runs every tool call the model issues and never asks first (its
 * `docs/security.md`, pi `0.99.1`). The deny rules in `~/.claude/settings.json` stop Claude Code
 * and nothing else, so in pi the same list was an instruction the model was free to ignore. A
 * `tool_call` handler runs before the tool and can block it. A blocked call runs no part of its
 * command, which is how Claude Code treats a denied compound command too.
 *
 * A call that a `codemode` script issues reaches the same handler as a nested call, so a script is
 * no way around the rules. A command the user types after `!` is a `user_bash` event, which this
 * extension does not handle: the rules are for the model.
 *
 * ## One list for both agents
 *
 * The rules are read from the Claude Code settings file and are not copied here, so a rule added
 * there applies in pi from the next command. Only the `permissions.deny` entries of the form
 * `Bash(...)` are read. The `ask` and `allow` entries change nothing in pi.
 *
 * A pattern keeps its Claude Code meaning. `*` matches any run of characters. A trailing ` *`, or
 * the older `:*`, makes the pattern a prefix that ends on a word boundary: `Bash(rm *)` matches
 * `rm` and `rm -rf build`, and never `rmdir`.
 *
 * When the settings file is missing or does not parse, every `bash` call is blocked and the reason
 * names the file. The other choice is a guard that stops with no notice, and that failure is the
 * worse one.
 *
 * ## What a rule is matched against
 *
 * The command line is split into simple commands, and each one is matched as its words joined by
 * one space, with the directory part of the command name removed. The split follows the shell
 * grammar far enough to find every place a command starts: after `;`, `&&`, `||`, `|` and a
 * newline, in a subshell or a brace group, in `$( )`, backticks and `<( )`, and after a reserved
 * word that takes a command, like `if`, `then` or `do`. Quoted text, comments and heredoc bodies
 * name no command, with one exception: a substitution still runs in a double-quoted string and
 * under an unquoted heredoc delimiter.
 *
 * Three more steps cover what the split alone misses:
 *
 * - A leading `NAME=value` word is skipped.
 * - The command that `command`, `env`, `xargs` and the other {py:data}`WRAPPERS` run is matched
 *   too. So is the script of `bash -c` and `eval`, and the command of `find -exec`.
 * - The global options of `git` are skipped, so `git -C {path} reset --hard` matches
 *   `Bash(git reset --hard *)`. The instructions tell the model to use `-C`, and a rule that
 *   `-C` defeats would never apply.
 *
 * ## What it does not see
 *
 * The extension corrects the habits of the model. It is no security boundary: it reads the text
 * of the command and runs nothing, so it cannot see a command name that a variable or a
 * substitution supplies, a script file that `bash` runs, or a deletion done from `python -c`. pi
 * runs with the user's own permissions, and only a sandbox or a container limits what a command
 * can reach.
 */

import { readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

/** A leading `NAME=value` word sets a variable for the command after it and names no command. */
const ASSIGNMENT = /^[A-Za-z_][A-Za-z0-9_]*\+?=/;

/** The `find` primaries that run the command spelled after them, up to a `;` or `+` word. */
const FIND_EXEC = /^-(?:exec|execdir|ok|okdir)$/;

/** The global options of `git` that take their value in the next word. */
const GIT_VALUED_OPTIONS = [
	"-C",
	"-c",
	"--attr-source",
	"--config-env",
	"--git-dir",
	"--namespace",
	"--super-prefix",
	"--work-tree",
];

/** A heredoc delimiter: one word, in which a quoted part can hold a space. */
const HEREDOC_DELIMITER = /(?:'[^']*'|"[^"]*"|\\.|[^\s;&|<>()'"\\])*/y;

/**
 * The reserved words the shell expects a command after, so the word that follows one is a command
 * name. `time` is here as the keyword, which takes `-p` alone, and among the {py:data}`WRAPPERS`
 * as the program of the same name, which a path or another wrapper reaches.
 */
const KEYWORDS = new Set(["!", "do", "elif", "else", "if", "then", "time", "until", "while"]);

/** Every redirection operator, longest first, with the `&` of `&>` in front. */
const REDIRECTION = /&?(?:<<<|<<-?|<>|<&|>>|>\||>&|<|>)/y;

/** Where Claude Code keeps the user's permission rules, the one list both agents follow. */
const SETTINGS_PATH = join(homedir(), ".claude", "settings.json");

/** The shells that run the script their `-c` option carries. */
const SHELLS = new Set(["bash", "dash", "ksh", "sh", "zsh"]);

/**
 * The commands that run the command their arguments spell, each with its options that take a
 * value in the next word. Any other word that starts with `-` is an option with no value.
 */
const WRAPPERS = new Map<string, readonly string[]>([
	["builtin", []],
	["command", []],
	["env", ["-C", "-P", "-u", "--chdir", "--unset"]],
	["exec", ["-a"]],
	["nice", ["-n", "--adjustment"]],
	["nohup", []],
	["stdbuf", ["-e", "-i", "-o", "--error", "--input", "--output"]],
	["time", ["-f", "-o", "--format", "--output"]],
	["timeout", ["-k", "-s", "--kill-after", "--signal"]],
	[
		"xargs",
		[
			"-E",
			"-I",
			"-J",
			"-L",
			"-P",
			"-R",
			"-S",
			"-a",
			"-d",
			"-n",
			"-s",
			"--arg-file",
			"--delimiter",
			"--max-args",
			"--max-chars",
			"--max-procs",
		],
	],
]);

interface DenyRule {
	/** The rule as the settings file spells it, quoted back in the block reason. */
	source: string;
	matcher: RegExp;
}

interface Heredoc {
	delimiter: string;
	/** An unquoted delimiter leaves the body open to command substitution. */
	expands: boolean;
	/** `<<-` strips the leading tabs of each line, the delimiter line included. */
	stripsTabs: boolean;
}

/** Whether `char` ends a word, the end of the input included. */
function endsWord(char: string | undefined): boolean {
	return char === undefined || " \t\r\n;&|)".includes(char);
}

/**
 * Split a command line into its simple commands, each one a list of words with the quoting removed.
 *
 * `asText` reads the source as expandable text instead, the body of an unquoted heredoc or of an
 * arithmetic expansion: nothing in it is a command but what a substitution runs.
 */
function simpleCommands(source: string, asText = false): string[][] {
	const commands: string[][] = [];
	let pos = 0;

	/**
	 * The index of the `)` that closes the `((` at `open`, or -1 when the two do not form an
	 * arithmetic context. Bash decides the same way: the inner pair must close right before the
	 * outer one, or the text is two nested subshells.
	 */
	function arithmeticEnd(open: number): number {
		let depth = 0;
		for (let index = open + 1; index < source.length; index++) {
			if (source[index] === "(") depth++;
			else if (source[index] === ")" && --depth === 0) return source[index + 1] === ")" ? index + 1 : -1;
		}
		return -1;
	}

	/** Consume the substitution at `pos`, collect the commands it runs, and return a stand-in. */
	function substitution(): string {
		if (source[pos] === "`") {
			// Between backticks the shell first drops a backslash that quotes `\`, `` ` `` or `$`, then
			// reads what is left as a command list.
			let body = "";
			for (pos++; pos < source.length && source[pos] !== "`"; pos++) {
				if (source[pos] === "\\" && ["\\", "`", "$"].includes(source[pos + 1])) pos++;
				body += source[pos];
			}
			pos++;
			commands.push(...simpleCommands(body));
			return "$()";
		}
		const end = source[pos + 2] === "(" ? arithmeticEnd(pos + 1) : -1;
		if (end === -1) {
			pos += 2;
			list(")");
			return "$()";
		}
		commands.push(...simpleCommands(source.slice(pos + 3, end - 1), true));
		pos = end + 1;
		return "$(())";
	}

	/** Read expandable text up to `closer`, or to the end of the input when there is none. */
	function text(closer?: '"'): string {
		let value = "";
		while (pos < source.length) {
			const char = source[pos];
			if (char === closer) {
				pos++;
				break;
			}
			if (char === "\\") {
				value += source[pos + 1] ?? "";
				pos += 2;
			} else if (char === "`" || (char === "$" && source[pos + 1] === "(")) {
				value += substitution();
			} else {
				value += char;
				pos++;
			}
		}
		return value;
	}

	/**
	 * Read a command list up to `closer`, or to the end of the input when there is none. A `data`
	 * list holds words that are no commands, like the items of an array literal, and still collects
	 * the substitutions among them.
	 */
	function list(closer?: ")", data = false): void {
		let words: string[] = [];
		let word: string | undefined;
		// A word with no quoting in it, the only kind the shell reads as a keyword or a descriptor.
		let bare = true;
		// The next word is the target of a redirection and no argument.
		let redirected = false;
		// The last word was the `time` keyword, so `-p` is its option and no command.
		let timed = false;
		// How many `case` statements are open, and whether the words that come next are a pattern.
		let cases = 0;
		let pattern = false;
		const heredocs: Heredoc[] = [];

		const add = (chunk: string, quoted = false) => {
			word = (word ?? "") + chunk;
			if (quoted) bare = false;
		};

		const endWord = () => {
			if (word === undefined) return;
			const first = bare && words.length === 0;
			if (redirected) {
				redirected = false;
			} else if (first && cases > 0 && word === "esac") {
				cases--;
				pattern = false;
			} else if (first && (KEYWORDS.has(word) || (timed && word === "-p"))) {
				timed = word === "time";
			} else if (bare && word === "in" && words.length === 2 && words[0] === "case") {
				// `case WORD in` is complete: the patterns come next.
				words = [];
				cases++;
				pattern = true;
			} else {
				words.push(word);
			}
			word = undefined;
			bare = true;
		};

		const endCommand = () => {
			endWord();
			redirected = false;
			timed = false;
			// The words of a `case` pattern name no command.
			if (words.length > 0 && !data && !pattern) commands.push(words);
			words = [];
		};

		/** Consume a redirection operator, and the delimiter too when it starts a heredoc. */
		const redirection = () => {
			// The digits right before an operator are its file descriptor.
			if (word !== undefined && bare && /^\d+$/.test(word)) word = undefined;
			endWord();
			REDIRECTION.lastIndex = pos;
			const operator = REDIRECTION.exec(source)?.[0] ?? source[pos];
			pos += operator.length;
			if (operator !== "<<" && operator !== "<<-") {
				redirected = true;
				return;
			}
			while (source[pos] === " " || source[pos] === "\t") pos++;
			HEREDOC_DELIMITER.lastIndex = pos;
			const raw = HEREDOC_DELIMITER.exec(source)?.[0] ?? "";
			pos += raw.length;
			const delimiter = raw.replace(/['"\\]/g, "");
			heredocs.push({ delimiter, expands: delimiter === raw, stripsTabs: operator === "<<-" });
		};

		/** Skip the body of a heredoc, down to the line that holds its delimiter. */
		const heredocBody = (heredoc: Heredoc) => {
			let body = "";
			while (pos < source.length) {
				const start = pos;
				const end = source.indexOf("\n", pos);
				const line = source.slice(pos, end === -1 ? source.length : end);
				pos = end === -1 ? source.length : end + 1;
				const content = heredoc.stripsTabs ? line.replace(/^\t+/, "") : line;
				if (content === heredoc.delimiter) break;
				if (closer && content.startsWith(`${heredoc.delimiter})`)) {
					// In `$( )`, bash also takes a delimiter that the closing parenthesis follows.
					pos = start + line.length - content.length + heredoc.delimiter.length;
					break;
				}
				body += `${line}\n`;
			}
			if (heredoc.expands) commands.push(...simpleCommands(body, true));
		};

		const parenthesis = () => {
			if (pattern) {
				// A `case` pattern can open with a parenthesis of its own.
				pos++;
				return;
			}
			if (source[pos + 1] === ")" && (word !== undefined || words.length > 0)) {
				// `name()` defines a function: the words before it name no command.
				word = undefined;
				words = [];
				pos += 2;
				return;
			}
			if (word !== undefined) {
				// Joined to a word, it opens an array literal or a glob qualifier: words, and no commands.
				pos++;
				list(")", true);
				add("()", true);
				return;
			}
			// A subshell, or `(( ))`, which evaluates arithmetic.
			const end = source[pos + 1] === "(" ? arithmeticEnd(pos) : -1;
			if (end === -1) {
				pos++;
				list(")");
			} else {
				commands.push(...simpleCommands(source.slice(pos + 2, end - 1), true));
				pos = end + 1;
			}
		};

		while (pos < source.length) {
			const char = source[pos];
			const next = source[pos + 1];
			if (char === ")") {
				endWord();
				pos++;
				if (pattern) {
					// It closes a `case` pattern, whose words name no command.
					words = [];
					pattern = false;
					continue;
				}
				if (closer) break;
				// Nothing opened it. It counts as a separator, so the words before it stay a command.
				endCommand();
				continue;
			}
			if (char === "\\") {
				// A backslash before a newline joins two lines. Before anything else it quotes it.
				if (next !== "\n") add(next ?? "", true);
				pos += 2;
			} else if (char === "'") {
				const end = source.indexOf("'", pos + 1);
				add(source.slice(pos + 1, end === -1 ? source.length : end), true);
				pos = end === -1 ? source.length : end + 1;
			} else if (char === '"') {
				pos++;
				add(text('"'), true);
			} else if (char === "$" && next === "'") {
				// ANSI-C quoting, where a backslash can quote the closing quote.
				let value = "";
				for (pos += 2; pos < source.length && source[pos] !== "'"; pos++) {
					if (source[pos] === "\\") pos++;
					value += source[pos] ?? "";
				}
				pos++;
				add(value, true);
			} else if (char === "`" || (char === "$" && next === "(")) {
				add(substitution(), true);
			} else if ((char === "<" || char === ">") && next === "(") {
				pos += 2;
				list(")");
				add("<()", true);
			} else if (char === "<" || char === ">" || (char === "&" && next === ">")) {
				redirection();
			} else if (char === "#" && word === undefined) {
				const end = source.indexOf("\n", pos);
				pos = end === -1 ? source.length : end;
			} else if (char === " " || char === "\t" || char === "\r") {
				endWord();
				pos++;
			} else if (char === "\n") {
				endCommand();
				pos++;
				for (const heredoc of heredocs.splice(0)) heredocBody(heredoc);
			} else if (char === ";" || char === "&" || char === "|") {
				endCommand();
				pos++;
				if (char === ";" && cases > 0 && (source[pos] === ";" || source[pos] === "&")) {
					// `;;`, `;&` and `;;&` end a `case` clause: a pattern comes next.
					pos += source.startsWith(";&", pos) ? 2 : 1;
					pattern = true;
				}
			} else if (char === "(") {
				parenthesis();
			} else if ((char === "{" || char === "}") && word === undefined && endsWord(next)) {
				// A brace on its own opens or closes a group, and a command starts after it.
				endCommand();
				pos++;
			} else {
				add(char);
				pos++;
			}
		}
		endCommand();
	}

	if (asText) text();
	else list();
	return commands;
}

/** The words left after the leading options. `valued` lists the options that take the next word. */
function afterOptions(args: readonly string[], valued: readonly string[]): string[] {
	let index = 0;
	while (index < args.length && args[index].startsWith("-") && args[index] !== "-") {
		if (args[index] === "--") return args.slice(index + 1);
		index += valued.includes(args[index]) ? 2 : 1;
	}
	return args.slice(index);
}

/** The script a shell runs from its `-c` option: the first operand after it. */
function shellScript(args: readonly string[]): string | undefined {
	const option = args.findIndex((arg) => /^-[a-zA-Z]*c[a-zA-Z]*$/.test(arg));
	return option === -1 ? undefined : args.slice(option + 1).find((arg) => !/^[-+]/.test(arg));
}

/**
 * Every command a simple command runs: itself, then each command it hands to a wrapper, to a
 * shell, to `eval` or to `find -exec`. The name of each command loses its directory part.
 */
function unwrap(words: readonly string[]): string[][] {
	const start = words.findIndex((word) => !ASSIGNMENT.test(word));
	if (start === -1) return [];
	const name = words[start].slice(words[start].lastIndexOf("/") + 1);
	const args = words.slice(start + 1);
	const found = [[name, ...args]];
	const valued = WRAPPERS.get(name);

	if (name === "git") {
		found.push(["git", ...afterOptions(args, GIT_VALUED_OPTIONS)]);
	} else if (valued && !(name === "command" && /^-[a-zA-Z]*[vV]/.test(args[0] ?? ""))) {
		// `command -v` and `command -V` describe a command and run nothing. `timeout` puts a
		// duration before the command.
		found.push(...unwrap(afterOptions(args, valued).slice(name === "timeout" ? 1 : 0)));
	} else if (SHELLS.has(name) || name === "eval") {
		const script = name === "eval" ? args.join(" ") : shellScript(args);
		for (const inner of simpleCommands(script ?? "")) found.push(...unwrap(inner));
	} else if (name === "find") {
		for (let index = 0; index < args.length; index++) {
			if (!FIND_EXEC.test(args[index])) continue;
			let end = index + 1;
			while (end < args.length && args[end] !== ";" && args[end] !== "+") end++;
			found.push(...unwrap(args.slice(index + 1, end)));
			index = end;
		}
	}
	return found;
}

/** Compile the pattern of one `Bash(...)` rule. The module docstring states what it matches. */
function ruleMatcher(pattern: string): RegExp {
	const prefix = / \*$|:\*$/.exec(pattern);
	const literal = (prefix ? pattern.slice(0, prefix.index) : pattern)
		.trim()
		.split(/\s+/)
		.join(" ")
		.split("*")
		.map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
		.join(".*");
	return new RegExp(`^${literal}${prefix ? "(?: .*)?" : ""}$`, "s");
}

/** The `Bash(...)` deny rules of a parsed Claude Code settings file. */
function denyRules(settings: unknown): DenyRule[] {
	const deny = (settings as { permissions?: { deny?: unknown } } | null)?.permissions?.deny;
	const rules: DenyRule[] = [];
	for (const entry of Array.isArray(deny) ? deny : []) {
		const pattern = typeof entry === "string" ? /^Bash\((.+)\)$/s.exec(entry)?.[1] : undefined;
		if (pattern) rules.push({ source: entry, matcher: ruleMatcher(pattern) });
	}
	return rules;
}

/** The first rule a command line breaks, with the command that broke it. */
function firstDenied(source: string, rules: readonly DenyRule[]): { rule: DenyRule; command: string } | undefined {
	for (const words of simpleCommands(source)) {
		for (const candidate of unwrap(words)) {
			const command = candidate.join(" ");
			const rule = rules.find(({ matcher }) => matcher.test(command));
			if (rule) return { rule, command };
		}
	}
	return undefined;
}

export default function (pi: ExtensionAPI) {
	let cache: { mtimeMs: number; rules: DenyRule[] } | undefined;

	/** The rules, parsed again when the settings file changes, so an edit applies to the next command. */
	const loadRules = (): DenyRule[] => {
		const { mtimeMs } = statSync(SETTINGS_PATH);
		if (cache?.mtimeMs !== mtimeMs) {
			cache = { mtimeMs, rules: denyRules(JSON.parse(readFileSync(SETTINGS_PATH, "utf8"))) };
		}
		return cache.rules;
	};

	pi.on("tool_call", async (event) => {
		if (event.toolName !== "bash") return undefined;
		const command = (event.input as { command?: unknown }).command;
		if (typeof command !== "string") return undefined;

		let rules: DenyRule[];
		try {
			rules = loadRules();
		} catch (error) {
			const cause = error instanceof Error ? error.message : String(error);
			return {
				block: true,
				reason: `Cannot read the deny rules in ${SETTINGS_PATH}: ${cause}. No shell command runs until that file parses.`,
			};
		}

		const denied = firstDenied(command, rules);
		if (!denied) return undefined;
		const matched = denied.command.length > 120 ? `${denied.command.slice(0, 120)}...` : denied.command;
		return {
			block: true,
			reason:
				`The deny rule \`${denied.rule.source}\` in ${SETTINGS_PATH} blocks this call: it matches \`${matched}\`. ` +
				"No part of the call ran. Do not try the same command in another form. " +
				'The "Shell commands" section of your instructions gives the replacement to use. ' +
				"If it gives none, ask the user to run the command.",
		};
	});
}
