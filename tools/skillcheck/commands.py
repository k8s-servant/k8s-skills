"""Checks that every command a skill shows keeps to its tier.

Skills are advice the agent follows, so the only way to promise they cannot change a
cluster is to allow-list what they may tell the agent to run. This check reads every
fenced code block and every line of prose in SKILL.md and references/**/*.md, and every
line of scripts/**, and rejects anything that is not an allow-listed read-only command,
except in the marked ask-first and proposed-fix blocks described below.
The check fails closed: whatever it cannot positively recognise as safe is a finding.

Markdown is parsed with markdown-it-py (CommonMark), so what counts as a code block is
decided by a real renderer's rules, not ours. Proposed fixes (commands the agent must not
run, handed to a human) are exempt from everything except the Secret ban and the `# Undo:`
line. Ask-first blocks (commands the agent runs only after the user approves them) are
checked against the `ask_first` allow-list, and a change in one needs an `# Undo:` line. In prose (inline code and paragraph
lines) text counts as a command only when a program name is followed by a kubectl
command name or a flag, so mentions such as "the `kubectl` binary" are not findings.

Known limits (this is a guardrail against honest mistakes, not a sandbox; human review
covers deliberate obfuscation): a fix block may use any shell, so `sh -c`, `eval` or
nested quoting can hide a Secret name; `$[` arithmetic; backslash tricks in prose;
glob patterns such as `secre[t]s`; yq `load()`; `-v=9` logging; a prose command whose
second word is not a kubectl command name (fenced blocks are still checked in full).
"""

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

import yaml
from markdown_it import MarkdownIt

from tools.skillcheck.findings import Finding
from tools.skillcheck.frontmatter import parse_skill

MARKER = "> Proposed fix: review before running. The agent does not run this."
ASK_MARKER = "> Ask first: the agent runs this only after the user approves it."
ASK_MESSAGE = "not on the ask-first allow-list: "
ASK_UNDO_MESSAGE = "ask-first change needs an '# Undo:' line"
ASK_LANG_MESSAGE = "ask-first block needs a shell language"
# kubectl flags of the ask-first changes that take a value, so the value is not taken
# for the target object.
ASK_VALUE_FLAGS = {
    "-n",
    "--namespace",
    "-p",
    "--patch",
    "--type",
    "--replicas",
    "-c",
    "--container",
    "-o",
    "--output",
    "--current-replicas",
    "--resource-version",
}
UNDO_PREFIX = "# Undo:"

LANG = re.compile(r"[{.\s]*([A-Za-z0-9_+-]+)")
# Characters that separate words inside an argument, so `pods,secrets`, `{a,secrets}`
# and `/api/v1/namespaces/x/secrets` are all seen as mentioning the word `secrets`.
WORD_SPLIT = re.compile(r"""[\s,/{}=:;|&()<>"'`$]+""")
SECRET_WORDS = {"secret", "secrets"}
SECRET_PREFIXES = ("secret.", "secrets.")
VARIABLE_START = re.compile(r"[A-Za-z_{0-9@*#?!$-]")
# Short kubectl flag letters after the subcommand: those that take a value (the rest of
# the cluster is that value) and plain switches. Any other letter is a finding.
SHORT_VALUE = set("nolcLv")
SHORT_BOOL = set("ARph")
# Flags that make kubectl wait forever (watch, follow) or read local files (manifests,
# kustomize folders). An agent that runs them hangs or reads outside the cluster.
BLOCKING_SHORT = set("wfk")
BLOCKING_LONG = {"--watch", "--watch-only", "--follow", "--filename", "--kustomize"}
BLOCKING_MESSAGE = "flag would block or read local files: "
# Short flag letters of each filter that take a value.
FILTER_VALUE_LETTERS = {
    "grep": "eABC",
    "egrep": "eABC",
    "yq": "o",
    "sort": "kt",
    "head": "n",
    "tail": "n",
    "cut": "dfc",
    "column": "s",
}
FILTER_VALUE_LONG = {"--output-format": 1, "--arg": 2}
YQ_WORDS = {"eval", "e"}


def load_allowlist(path: Path | None = None) -> dict:
    """Load the allow-list, by default the one shipped next to this module.

    Args:
        path: An alternative allowlist.yaml, mostly for tests.

    Returns:
        The parsed mapping with keys commands, kubectl_commands, filters, filter_flags,
        global_flags, global_flags_allowed and command_langs.
    """
    path = path or Path(__file__).with_name("allowlist.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass
class Block:
    """A fenced code block.

    Attributes:
        lang: The language word of the info string, "" if it has no usable word, or
            None when the fence has no info string at all.
        start_line: 1-based line of the opening fence; content line i is start_line + 1 + i.
        lines: The content lines, with any blockquote prefix removed.
        is_fix: True when the proposed-fix marker is the nearest non-blank line above.
        is_ask: True when the ask-first marker is the nearest non-blank line above.
    """

    lang: str | None
    start_line: int
    lines: list[str]
    is_fix: bool
    is_ask: bool = False


def _lines(text: str) -> list[str]:
    """Split text into lines the way markdown-it counts them.

    `str.splitlines()` also breaks on form feed, U+2028 and other separators that
    CommonMark treats as ordinary characters, which would shift every line index.
    """
    lines = re.sub(r"\r\n?", "\n", text).split("\n")
    return lines[:-1] if lines and lines[-1] == "" else lines


def _code_spans(token, start: int) -> list[tuple[int, str]]:
    """Return (line, content) for each inline code span of an inline token.

    The line is that of the span itself: the paragraph's first line plus the line
    breaks seen before it. Code spans fold their own line breaks into spaces, so a
    span after a multi-line span is reported a line or so early.
    """
    spans: list[tuple[int, str]] = []
    line = start
    for child in token.children or []:
        if child.type == "code_inline":
            spans.append((line, child.content))
        elif child.type in ("softbreak", "hardbreak"):
            line += 1
        else:
            line += child.content.count("\n")
    return spans


def _parse_markdown(
    md: str,
    first_line: int,
    keys: frozenset[str] = frozenset(),
    subcommands: frozenset[str] = frozenset(),
) -> tuple[list[Block], list[tuple[int, str]]]:
    """Find the code blocks and the prose commands of a Markdown text.

    Args:
        md: The Markdown text.
        first_line: The file line number of the first line of `md`.
        keys: The allow-listed program names that make prose a command.
        subcommands: The kubectl command names; prose is a command only when its second
            word is one of them.

    Returns:
        The fenced and indented code blocks, and (line, text) candidates from prose:
        inline code spans and lines of text that read as a command, with any `$ `
        prompt removed. A mention of a program name is not a candidate.
    """
    text = _lines(md)
    blocks: list[Block] = []
    prose: list[tuple[int, str]] = []
    for token in MarkdownIt("commonmark").parse(md):
        start = first_line + (token.map[0] if token.map else 0)
        if token.type == "fence":
            above = next((t.rstrip() for t in reversed(text[: token.map[0]]) if t.strip()), "")
            info = token.info.strip()
            lang = None
            if info:
                found = LANG.match(info)
                lang = found.group(1).lower() if found else ""
            is_fix = token.level == 0 and above == MARKER
            is_ask = token.level == 0 and above == ASK_MARKER
            blocks.append(Block(lang, start, _lines(token.content), is_fix, is_ask))
        elif token.type == "code_block":
            # Indented code has no language, so it is reported like an untyped fence.
            blocks.append(Block(None, start, _lines(token.content), False))
        elif token.type == "html_block":
            for offset, line in enumerate(_lines(token.content)):
                prose.append((start + offset, re.sub(r"<[^>]*>", "", line)))
        elif token.type == "inline":
            for offset, line in enumerate(token.content.split("\n")):
                prose.append((start + offset, line))
            prose += _code_spans(token, start)
    candidates = [(n, t.strip().removeprefix("$ ").strip()) for n, t in prose]
    return blocks, [(n, t) for n, t in candidates if _reads_as_command(t, keys, subcommands)]


def _reads_as_command(text: str, keys: frozenset[str], subcommands: frozenset[str]) -> bool:
    """True if a piece of prose is a command rather than a mention of a program.

    Prose in a Kubernetes repository names kubectl all the time ("the `kubectl`
    binary", a wrapped line starting "kubectl tool ..."), so a program name alone is
    not enough: the second word must be a kubectl command name, or a flag such as
    `-n`, which only ever follows the program in a command.
    """
    words = text.split(None, 2)
    if len(words) < 2 or words[0] not in keys:
        return False
    return words[1] in subcommands or words[1].startswith("-")


def extract_blocks(md: str, first_line: int = 1) -> list[Block]:
    """Find the fenced and indented code blocks of a Markdown text.

    Args:
        md: The Markdown text.
        first_line: The file line number of the first line of `md`.

    Returns:
        The blocks in order.
    """
    return _parse_markdown(md, first_line)[0]


def _strip_comment(line: str) -> str:
    """Cut a line at an unquoted `#` that starts a word, as the shell does.

    A trailing backslash inside a comment is only comment text, so it must not
    continue the line.
    """
    quote = None
    word_start = True
    i = 0
    while i < len(line):
        c = line[i]
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "\\":
            i += 1
        elif quote == '"':
            quote = None if c == '"' else quote
        elif c in "'\"":
            quote = c
        elif c == "#" and word_start:
            return line[:i]
        word_start = c.isspace() and quote is None
        i += 1
    return line


def _trailing_backslashes(line: str) -> int:
    return len(line) - len(line.rstrip("\\"))


def _embedded_commands(line: str, keys: set[str]) -> list[str]:
    """Find commands written inside a line of prose or output.

    A line counts as a command if an allow-listed program name appears in it as a
    whole word once quotes are removed (`"kubectl" delete`, `user@host:~$ kubectl`).
    Each candidate runs from that word to the end of the line. Backticks and
    parentheses are blanked first, since inline code and brackets are normal in prose.
    """
    line = line.replace("`", " ").replace("(", " ").replace(")", " ")
    stripped, origin = [], []
    for pos, c in enumerate(line):
        if c not in "'\"":
            stripped.append(c)
            origin.append(pos)
    plain = "".join(stripped)
    found: list[str] = []
    for key in keys:
        for hit in re.finditer(rf"(?<![\w-]){re.escape(key)}(?![\w-])", plain):
            start = origin[hit.start()]
            while start > 0 and line[start - 1] in "'\"":
                start -= 1
            found.append(line[start:])
    return found


def _commands_in(
    lines: list[str], first_line: int, mode: str, keys: set[str]
) -> list[tuple[int, str]]:
    """Turn raw lines into (line number, command) pairs.

    Which lines are commands is decided per raw line, before any joining:
    every line in `command` mode, only `$ ` lines in `console` mode, none in `other`
    mode. All remaining lines are scanned for embedded commands. Only command lines
    can continue: blank lines and comments are dropped, a leading `$ ` is removed,
    comments end the line (and its continuation), and an odd number of trailing
    backslashes joins the next line. The line number is that of the first line.
    """
    commands: list[tuple[int, str]] = []
    pending: list[str] = []
    start = 0
    for offset, raw in enumerate(lines):
        line = raw.strip()
        if not pending:
            is_command = mode == "command" or (mode == "console" and line.startswith("$ "))
            if not is_command:
                commands += [(first_line + offset, c) for c in _embedded_commands(line, keys)]
                continue
            if not line or line.startswith("#"):
                continue
            start = first_line + offset
            if line.startswith("$ "):
                line = line[2:].lstrip()
        line = _strip_comment(line).strip()
        if _trailing_backslashes(line) % 2 == 1:
            pending.append(line[:-1].strip())
            continue
        pending.append(line)
        commands.append((start, " ".join(p for p in pending if p)))
        pending = []
    if pending:
        commands.append((start, " ".join(p for p in pending if p)))
    return commands


def _mentions_secret(text: str) -> bool:
    """True if any word of the text names the Secret resource."""
    for word in WORD_SPLIT.split(text.lower()):
        if word in SECRET_WORDS or word.startswith(SECRET_PREFIXES):
            return True
    return False


def _expands(after_dollar: str, quote: str | None) -> bool:
    """True if a `$` followed by this character is an expansion or special quote."""
    if not after_dollar:
        return False
    if after_dollar in "({" or VARIABLE_START.match(after_dollar):
        return True
    return quote is None and after_dollar in "'\""


def _scan(command: str) -> list[list[str]] | str:
    """Split a command into pipe segments of words, as bash would see them.

    Words are returned with quotes resolved, so every later check sees the text bash
    would pass to the program. Anything where bash's result could differ from what is
    written (backslash escapes, `$'` and `$"` quoting, command substitution, brace
    expansion, variables) or that chains commands is rejected rather than interpreted.

    Args:
        command: One logical command line.

    Returns:
        The segments (lists of words), or "control" or "parse" naming the problem.
    """
    segments: list[list[str]] = [[]]
    word: list[str] = []
    in_word = False
    quote = None

    def flush() -> None:
        nonlocal word, in_word
        if in_word:
            segments[-1].append("".join(word))
        word, in_word = [], False

    i = 0
    while i < len(command):
        c = command[i]
        nxt = command[i + 1] if i + 1 < len(command) else ""
        i += 1
        if quote == "'":
            if c == "'":
                quote = None
            else:
                word.append(c)
            continue
        if c in "\\`":
            return "control"
        if c == "$" and _expands(nxt, quote):
            return "control"
        if quote == '"':
            if c == '"':
                quote = None
            else:
                word.append(c)
            continue
        if c in "'\"":
            quote, in_word = c, True
        elif c in "{}":
            return "control"
        elif c.isspace():
            flush()
        elif c == "|":
            if nxt and nxt in "|&":
                return "control"
            flush()
            segments.append([])
        elif c in ";&<>()":
            return "control"
        else:
            word.append(c)
            in_word = True
    if quote:
        return "parse"
    flush()
    return segments


def _is_flag(token: str) -> bool:
    return token.startswith("-") and token != "-"


def _output_problems(value: str) -> list[str]:
    """Reject `-o` formats that read a template from a local file (`jsonpath-file=...`)."""
    fmt = value.split("=", 1)[0]
    return [f"{BLOCKING_MESSAGE}-o {fmt}"] if fmt.endswith("-file") else []


def _check_flags(args: list[str], allowlist: dict) -> list[str]:
    """Check the flags of a kubectl command after its subcommand.

    Global flags must be on the allowed list. Short flags are walked letter by letter,
    so `-As https://example.com` is seen as `-A` plus `-s`; a letter that is neither a
    known switch nor a known value flag fails closed.
    """
    every, allowed = set(allowlist["global_flags"]), set(allowlist["global_flags_allowed"])
    problems: list[str] = []
    for i, token in enumerate(args):
        if token == "--":
            break
        following = "".join(args[i + 1 : i + 2])
        if token.startswith("--"):
            name = token.split("=", 1)[0]
            if name in every and name not in allowed:
                problems.append("global flag not allowed")
            if name in BLOCKING_LONG:
                problems.append(BLOCKING_MESSAGE + name)
            if name == "--output":
                problems += _output_problems(token.split("=", 1)[1] if "=" in token else following)
            if name == "--raw":
                value = token.split("=", 1)[1] if "=" in token else "".join(args[i + 1 : i + 2])
                if "%" in value:
                    problems.append("percent-encoding in a --raw path is not allowed")
        elif _is_flag(token) and not token[1:].isdigit():
            for pos, letter in enumerate(token[1:], start=2):
                flag = f"-{letter}"
                if flag in every and flag not in allowed:
                    problems.append("global flag not allowed")
                    break
                if letter in BLOCKING_SHORT:
                    problems.append(BLOCKING_MESSAGE + flag)
                    break
                if letter == "o":
                    problems += _output_problems(token[pos:].removeprefix("=") or following)
                if letter in SHORT_VALUE:
                    break
                if letter not in SHORT_BOOL:
                    problems.append(f"flag not allowed: {token}")
                    break
    return problems


def _check_kubectl(words: list[str], allowlist: dict) -> list[str]:
    """Check one kubectl invocation: subcommand, then flags."""
    listed = allowlist["commands"][words[0]]
    problems: list[str] = []
    every, allowed = set(allowlist["global_flags"]), set(allowlist["global_flags_allowed"])
    # Only -n/--namespace may come before the subcommand, as kubectl would otherwise
    # take the subcommand from a different place than we do.
    i = 1
    while i < len(words) and _is_flag(words[i]):
        token = words[i]
        if token in ("-n", "--namespace"):
            i += 2
        elif token.startswith("--namespace=") or (
            token.startswith("-n") and not token.startswith("--")
        ):
            i += 1
        else:
            name = token.split("=", 1)[0]
            if name in every and name not in allowed or token.startswith("-s"):
                problems.append("global flag not allowed")
            else:
                problems.append("only -n/--namespace may come before the subcommand")
            i += 1
    word = words[i] if i < len(words) else ""
    nxt = words[i + 1] if i + 1 < len(words) else ""
    if f"{word} {nxt}" in listed:
        i += 2
    elif word in listed:
        i += 1
    else:
        shown = f"{words[0]} {word}".strip()
        problems.append(f"not on the allow-list: {shown}")
        i += 1
    return problems + _check_flags(words[i:], allowlist)


def _check_filter(words: list[str], allowlist: dict) -> list[str]:
    """Check one filter after a pipe: only allow-listed flags, stdin only.

    The one positional a filter may have is its pattern or program (for grep, jq and
    yq); anything else would be a file to read or write.
    """
    name, args = words[0], words[1:]
    allowed = set(allowlist["filter_flags"].get(name, []))
    value_letters = FILTER_VALUE_LETTERS.get(name, "")
    problems: list[str] = []
    positional = 0
    pattern_given = False
    i = 0
    while i < len(args):
        token = args[i]
        i += 1
        if token.startswith("--") or (_is_flag(token) and len(token) > 1):
            if token == "--" or token[1:2] == "-" and token.split("=", 1)[0] not in allowed:
                problems.append(f"flag not allowed for {name}")
            elif token.startswith("--"):
                i += FILTER_VALUE_LONG.get(token.split("=", 1)[0], 0) if "=" not in token else 0
            elif name in {"head", "tail"} and token[1:].isdigit():
                pass
            else:
                for pos, letter in enumerate(token[1:], start=1):
                    if f"-{letter}" not in allowed:
                        problems.append(f"flag not allowed for {name}")
                        break
                    if letter in value_letters:
                        if letter == "e":
                            pattern_given = True
                        if pos == len(token) - 1:
                            i += 1
                        break
        elif name in {"grep", "egrep", "jq", "yq"}:
            if name == "yq" and token in YQ_WORDS and positional == 0:
                continue
            positional += 1
        else:
            problems.append(f"file argument not allowed for {name}")
    limit = 0 if pattern_given else 1
    if name in {"grep", "egrep", "jq", "yq"} and positional > limit:
        problems.append(f"file argument not allowed for {name}")
    return problems


def _check_command(command: str, allowlist: dict) -> list[str]:
    """Return the problems with one command line (Secret access is checked apart)."""
    segments = _scan(command)
    if segments == "control":
        return ["shell control not allowed"]
    if segments == "parse":
        return ["cannot parse command"]
    first = segments[0]
    problems: list[str] = []
    if not first or first[0] not in allowlist["commands"]:
        problems.append(f"not on the allow-list: {command}")
    else:
        problems += _check_kubectl(first, allowlist)
    for words in segments[1:]:
        if not words or words[0] not in allowlist["filters"]:
            problems.append(f"pipe must lead to an allow-listed filter: {command}")
        else:
            problems += _check_filter(words, allowlist)
    return list(dict.fromkeys(problems))


def _secret_problems(command: str) -> list[str]:
    """Check a command for Secret access, on the raw text and on the quote-resolved words."""
    if _mentions_secret(command):
        return ["Secret access is not allowed"]
    try:
        words = shlex.split(command)
    except ValueError:
        return []
    return ["Secret access is not allowed"] if any(_mentions_secret(w) for w in words) else []


def _ask_subcommand(words: list[str], allowlist: dict) -> tuple[str, int] | None:
    """Find the ask-first subcommand of a kubectl invocation.

    Only -n/--namespace may come before the subcommand, as in `_check_kubectl`.

    Returns:
        The subcommand and the index of the first word after it, or None when the
        words are not kubectl followed by an ask-first subcommand.
    """
    if not words or words[0] != "kubectl":
        return None
    i = 1
    while i < len(words) and _is_flag(words[i]):
        token = words[i]
        if token in ("-n", "--namespace"):
            i += 2
        elif token.startswith("--namespace=") or (
            token.startswith("-n") and not token.startswith("--")
        ):
            i += 1
        else:
            return None
    listed = allowlist["ask_first"]["kubectl"]
    two = " ".join(words[i : i + 2])
    if two in listed:
        return two, i + 2
    if i < len(words) and words[i] in listed:
        return words[i], i + 1
    return None


def _check_exec(args: list[str], ask_first: dict) -> bool:
    """True if `kubectl exec` args run one allow-listed read-only program in a pod."""
    if "--" not in args:
        return False
    split = args.index("--")
    before, program = args[:split], args[split + 1 :]
    flags, i, pods = ask_first["exec_flags"], 0, 0
    while i < len(before):
        token = before[i]
        name = token.split("=", 1)[0]
        if not _is_flag(token):
            pods += 1
        elif name not in flags:
            return False
        elif "=" not in token:
            i += 1
        i += 1
    if pods != 1 or not program or program[0] not in ask_first["in_pod"]:
        return False
    allowed = ask_first["in_pod_flags"].get(program[0])
    if allowed is not None and any(_is_flag(a) and a not in allowed for a in program[1:]):
        return False
    exact = ask_first["in_pod_args"].get(program[0])
    if exact is not None and any(a not in exact for a in program[1:]):
        return False
    for arg in program[1:]:
        if "://" in arg and not arg.lower().startswith(tuple(ask_first["url_schemes"])):
            return False
    # wget writes a file unless told to print to stdout.
    return program[0] != "wget" or bool(set(program[1:]) & set(ask_first["wget_needs_one_of"]))


def _target(args: list[str]) -> str:
    """The first argument that is neither a flag nor a flag's value: the object changed."""
    i = 0
    while i < len(args):
        token = args[i]
        if token in ASK_VALUE_FLAGS:
            i += 2
            continue
        if not _is_flag(token):
            return token
        i += 1
    return ""


def _check_change(subcommand: str, args: list[str], ask_first: dict) -> bool:
    """True if an ask-first change stays narrow: one named object, a visible change."""
    for token in args:
        if token == "--":
            break
        name = token.split("=", 1)[0]
        if name in ask_first["wide_change_flags"] or (
            not token.startswith("--") and token[:2] in ask_first["wide_change_flags"]
        ):
            return False
    if subcommand in ("patch", "scale"):
        kind = _target(args).split("/", 1)[0].split(".", 1)[0].lower()
        if kind not in ask_first["workload_kinds"]:
            return False
    if subcommand == "taint":
        specs = [t for t in args if ":" in t and not _is_flag(t) and not t.endswith("-")]
        if any(t.rsplit(":", 1)[1] not in ask_first["taint_effects"] for t in specs):
            return False
    return True


def _check_ask_command(command: str, allowlist: dict) -> list[str]:
    """Return the problems with one command in an ask-first block.

    A command on the main allow-list passes as it is. Otherwise it must be kubectl with
    an ask-first subcommand: exec in the form `exec POD [flags] -- PROGRAM [args]`, or a
    change command whose flags pass the same checks as a read-only command.
    """
    if not _check_command(command, allowlist):
        return []
    rejected = [ASK_MESSAGE + command]
    segments = _scan(command)
    if isinstance(segments, str):
        return rejected
    found = _ask_subcommand(segments[0], allowlist)
    if found is None:
        return rejected
    subcommand, rest = found
    args = segments[0][rest:]
    if subcommand == "exec":
        if not _check_exec(args, allowlist["ask_first"]):
            return rejected
        problems: list[str] = []
    elif not _check_change(subcommand, args, allowlist["ask_first"]):
        return rejected
    else:
        problems = _check_flags(args, allowlist)
    for words in segments[1:]:
        if not words or words[0] not in allowlist["filters"]:
            problems.append(f"pipe must lead to an allow-listed filter: {command}")
        else:
            problems += _check_filter(words, allowlist)
    return list(dict.fromkeys(problems))


def _is_ask_change(command: str, allowlist: dict) -> bool:
    """True if the command is an ask-first change (any ask-first subcommand but exec)."""
    segments = _scan(command)
    if isinstance(segments, str):
        return False
    found = _ask_subcommand(segments[0], allowlist)
    return found is not None and found[0] != "exec"


def _ask_secret_problems(command: str, allowlist: dict) -> list[str]:
    """Secret access in an ask-first command: Secret words, environment and token reads."""
    # Brackets also separate words here, so an IPv6 host such as `[fd00:ec2::254]` is seen.
    text = command.lower()
    words = set(WORD_SPLIT.split(text.replace("[", " ").replace("]", " ")))
    ask_first = allowlist["ask_first"]
    if (
        _secret_problems(command)
        or words & set(ask_first["secret_words"])
        or any(part in text for part in ask_first["secret_substrings"])
    ):
        return ["Secret access is not allowed"]
    return []


def _check_lines(
    block_lines: list[str], first_line: int, kind: str, allowlist: dict, mode: str
) -> list[tuple[int, str]]:
    """Check the commands of one block or script; return (line, message) pairs.

    Args:
        block_lines: The raw lines.
        first_line: File line number of the first of them.
        kind: "fix" for a proposed-fix block (only the Secret ban applies), "ask" for an
            ask-first block (the ask-first allow-list and a stricter Secret ban apply),
            or "normal".
        allowlist: The allow-list mapping.
        mode: "command" (every line is a command), "console" (only `$ ` lines are),
            or "other" (non-shell blocks: only embedded commands count).
    """
    problems: list[tuple[int, str]] = []
    if kind in ("fix", "ask"):
        for offset, raw in enumerate(block_lines):
            if not raw.strip().startswith(UNDO_PREFIX):
                continue
            # The agent may run an ask-first undo, so it gets the stricter check.
            if (kind == "fix" and _mentions_secret(raw)) or (
                kind == "ask" and _ask_secret_problems(raw, allowlist)
            ):
                problems.append((first_line + offset, "Secret access is not allowed"))
    keys = set(allowlist["commands"])
    for line_no, command in _commands_in(block_lines, first_line, mode, keys):
        if kind == "ask":
            problems += [(line_no, m) for m in _ask_secret_problems(command, allowlist)]
            problems += [(line_no, m) for m in _check_ask_command(command, allowlist)]
            continue
        problems += [(line_no, m) for m in _secret_problems(command)]
        if kind != "fix":
            problems += [(line_no, m) for m in _check_command(command, allowlist)]
    return list(dict.fromkeys(problems))


def _kind(block: Block) -> str:
    """The rules a block is checked under: "fix", "ask" or "normal"."""
    return "fix" if block.is_fix else "ask" if block.is_ask else "normal"


def check_commands(skill_dir: Path, allowlist: dict) -> list[Finding]:
    """Check every command in one skill folder against the allow-list.

    Args:
        skill_dir: A `<repo>/skills/<name>` folder.
        allowlist: The mapping from `load_allowlist()`.

    Returns:
        One Finding per problem, with paths relative to the repository root.
    """
    root = skill_dir.parent.parent
    found: list[Finding] = []

    def add(path: Path, line: int | None, message: str) -> None:
        found.append(Finding(path.relative_to(root), line, message))

    def read(path: Path) -> str:
        data = path.read_bytes()
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            add(path, None, "file is not valid UTF-8")
            return data.decode("utf-8", errors="replace")

    def check_markdown(path: Path, text: str, first_line: int) -> None:
        blocks, prose = _parse_markdown(
            text,
            first_line,
            frozenset(allowlist["commands"]),
            frozenset(allowlist["kubectl_commands"]),
        )
        for block in blocks:
            if block.lang is None:
                add(path, block.start_line, "fenced block needs a language")
                continue
            is_command_lang = block.lang in allowlist["command_langs"]
            has_undo = any(ln.strip().startswith(UNDO_PREFIX) for ln in block.lines)
            if is_command_lang and block.is_fix and not has_undo:
                add(path, block.start_line, "proposed fix needs an '# Undo:' line")
            if block.is_ask and not is_command_lang:
                add(path, block.start_line, ASK_LANG_MESSAGE)
            if is_command_lang and block.is_ask and not has_undo:
                keys = set(allowlist["commands"])
                mode_ = "console" if block.lang == "console" else "command"
                commands = _commands_in(block.lines, block.start_line + 1, mode_, keys)
                if any(_is_ask_change(c, allowlist) for _, c in commands):
                    add(path, block.start_line, ASK_UNDO_MESSAGE)
            mode = "other"
            if is_command_lang:
                mode = "console" if block.lang == "console" else "command"
            for line_no, message in _check_lines(
                block.lines, block.start_line + 1, _kind(block), allowlist, mode
            ):
                add(path, line_no, message)
        for line_no, command in prose:
            for message in _secret_problems(command) + _check_command(command, allowlist):
                add(path, line_no, message)

    skill_file = skill_dir / "SKILL.md"
    if skill_file.is_file():
        text = read(skill_file)
        try:
            _meta, body, body_line = parse_skill(skill_file)
        except ValueError:
            # The frontmatter check reports this; scan the whole file so nothing hides.
            body, body_line = text, 1
        except UnicodeDecodeError:
            body, body_line = text, 1
        check_markdown(skill_file, body, body_line)

    for ref in sorted((skill_dir / "references").rglob("*.md")):
        if ref.is_file():
            check_markdown(ref, read(ref), 1)

    for script in sorted((skill_dir / "scripts").rglob("*")):
        if script.is_file():
            for line_no, message in _check_lines(
                read(script).splitlines(), 1, "normal", allowlist, "command"
            ):
                add(script, line_no, message)
    return found
