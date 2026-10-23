"""Checks that every command a skill shows is read-only.

Skills are advice the agent follows, so the only way to promise they cannot change a
cluster is to allow-list what they may tell the agent to run. This check reads every
shell code block in SKILL.md and references/*.md, and every line of scripts/*, and
rejects anything that is not an allow-listed read-only command. The check fails closed:
whatever it cannot positively recognise as safe is a finding.
"""

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

import yaml

from tools.skillcheck.findings import Finding
from tools.skillcheck.frontmatter import parse_skill

MARKER = "> Proposed fix: review before running. The agent does not run this."
UNDO_PREFIX = "# Undo:"

FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})\s*(\S*)")
# Characters that separate words inside an argument, so `pods,secrets`, `{a,secrets}`
# and `/api/v1/namespaces/x/secrets` are all seen as mentioning the word `secrets`.
WORD_SPLIT = re.compile(r"""[\s,/{}=:;|&()<>"'`$]+""")
SECRET_WORDS = {"secret", "secrets"}
SECRET_PREFIXES = ("secret.", "secrets.")
# Global kubectl flags that take a separate value and may precede the subcommand.
VALUE_FLAGS_BEFORE_SUBCOMMAND = {"-n", "--namespace", "--request-timeout", "-v", "--v"}
VARIABLE_START = re.compile(r"[A-Za-z_{0-9@*#?!$-]")
SED_IN_PLACE = re.compile(r"^-[a-zA-Z]*i|^--in-place")
# sed's `w` (write file) and `e` (execute) commands and s///w, s///e flags.
SED_S_FLAGS = re.compile(r"s(.).*?\1.*?\1[a-zA-Z0-9]*[we]")
SED_WE_COMMAND = re.compile(r"(^|[;{}\n])\s*[\d$,/]*\s*[we](\s|;|$)")
AWK_DANGEROUS = re.compile(r"system\s*\(|getline|\bprint(f)?\b[^;}]*[>|]")


def load_allowlist(path: Path | None = None) -> dict:
    """Load the allow-list, by default the one shipped next to this module.

    Args:
        path: An alternative allowlist.yaml, mostly for tests.

    Returns:
        The parsed mapping with keys commands, filters, forbidden_flags, command_langs.
    """
    path = path or Path(__file__).with_name("allowlist.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass
class Block:
    """A fenced code block.

    Attributes:
        lang: The first word of the info string, or None when the fence has none.
        start_line: 1-based line of the opening fence; content line i is start_line + 1 + i.
        lines: The raw content lines.
        is_fix: True when the proposed-fix marker is the nearest non-blank line above.
    """

    lang: str | None
    start_line: int
    lines: list[str]
    is_fix: bool


def extract_blocks(md: str, first_line: int = 1) -> list[Block]:
    """Find the fenced code blocks of a Markdown text.

    Args:
        md: The Markdown text.
        first_line: The file line number of the first line of `md`.

    Returns:
        The blocks in order. An unclosed block runs to the end of the text.
    """
    text = md.splitlines()
    blocks: list[Block] = []
    i = 0
    while i < len(text):
        opened = FENCE_OPEN.match(text[i])
        if not opened:
            i += 1
            continue
        fence, lang = opened.group(1), opened.group(2)
        above = next((t.strip() for t in reversed(text[:i]) if t.strip()), "")
        content: list[str] = []
        j = i + 1
        while j < len(text):
            stripped = text[j].strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                break
            content.append(text[j])
            j += 1
        blocks.append(Block(lang.lower() or None, first_line + i, content, above == MARKER))
        i = j + 1
    return blocks


def _logical_commands(block_lines: list[str], first_line: int) -> list[tuple[int, str]]:
    """Turn raw lines into (line number, command) pairs.

    Blank lines and comments are dropped, a leading `$ ` prompt is removed and
    backslash continuations are joined. The line number is that of the first line.
    """
    commands: list[tuple[int, str]] = []
    pending: list[str] = []
    start = 0
    for offset, raw in enumerate(block_lines):
        line = raw.strip()
        if not pending and (not line or line.startswith("#")):
            continue
        if not pending:
            start = first_line + offset
            if line.startswith("$ "):
                line = line[2:].lstrip()
        if line.endswith("\\"):
            pending.append(line[:-1].strip())
            continue
        pending.append(line)
        commands.append((start, " ".join(p for p in pending if p)))
        pending = []
    if pending:
        commands.append((start, " ".join(p for p in pending if p)))
    return commands


def _mentions_secret(command: str) -> bool:
    """True if any word of the command names the Secret resource."""
    for word in WORD_SPLIT.split(command.lower()):
        if word in SECRET_WORDS or word.startswith(SECRET_PREFIXES):
            return True
    return False


def _split_pipeline(command: str) -> list[str] | str:
    """Split a command at single pipes, rejecting other shell control.

    Scans the raw text rather than relying on shlex so that control characters are
    caught even without surrounding spaces. Single quotes make everything literal;
    double quotes still allow `$(` and backticks, as in a real shell.

    Returns:
        The pipe segments, or the string "control" or "parse" naming the problem.
    """
    segments: list[str] = []
    current: list[str] = []
    quote = None
    i = 0
    while i < len(command):
        c = command[i]
        nxt = command[i + 1] if i + 1 < len(command) else ""
        if quote == "'":
            if c == "'":
                quote = None
        elif c == "\\":
            current.append(c + nxt)
            i += 2
            continue
        elif c == "`" or (c == "$" and (nxt == "(" or VARIABLE_START.match(nxt))):
            # Command substitution and variable expansion can hide a verb or a
            # resource from this check, so neither is allowed outside single quotes.
            return "control"
        elif quote == '"':
            if c == '"':
                quote = None
        elif c in "'\"":
            quote = c
        elif c in ";&<>()":
            return "control"
        elif c == "|":
            if nxt == "|":
                return "control"
            segments.append("".join(current))
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    if quote:
        return "parse"
    segments.append("".join(current))
    return segments


def _is_flag(token: str) -> bool:
    return token.startswith("-") and token != "-"


def _forbidden_flag(tokens: list[str], forbidden: list[str]) -> str | None:
    """Return the first forbidden flag used, in `--flag`, `--flag=value` or `-fvalue` form."""
    for token in tokens:
        if not _is_flag(token):
            continue
        for flag in forbidden:
            if token == flag or token.startswith(flag + "="):
                return flag
            # A short flag may carry its value directly: -shttps://example.com
            if not flag.startswith("--") and not token.startswith("--") and token.startswith(flag):
                return flag
    return None


def _subcommand(tokens: list[str]) -> tuple[str, str | None]:
    """Find kubectl's subcommand: the first word, and the word after it if any.

    Only global flags can come before the subcommand; flags that take a separate
    value are skipped with their value. Anything unknown ends up as a word that is
    not on the allow-list, so a surprise fails closed.
    """
    rest = iter(tokens[1:])
    word = None
    for token in rest:
        if token in VALUE_FLAGS_BEFORE_SUBCOMMAND:
            next(rest, None)
        elif not _is_flag(token):
            word = token
            break
    if word is None:
        return "", None
    second = next((t for t in rest if not _is_flag(t)), None)
    return word, second


def _check_filter(tokens: list[str]) -> str | None:
    """Return a problem with a filter invocation that could write, execute or block."""
    name, args = tokens[0], tokens[1:]
    flags = [a for a in args if _is_flag(a)]
    positional = [a for a in args if not _is_flag(a)]
    if name in {"sed", "yq"} and any(SED_IN_PLACE.match(f) or f == "--inplace" for f in flags):
        return f"{name} in-place edit not allowed"
    if name in {"tail", "head"} and any(
        re.match(r"-[a-zA-Z0-9]*[fF]", f) or f.startswith("--follow") for f in flags
    ):
        return f"{name} --follow blocks forever"
    if name == "sort" and any(
        re.match(r"-[a-zA-Z]*o", f) or f.startswith("--output") for f in flags
    ):
        return "sort --output writes a file"
    if name == "uniq" and len(positional) > 1:
        return "uniq with an output file writes a file"
    if name in {"sed", "awk"} and any(f in {"-f", "--file"} for f in flags):
        return f"{name} -f reads its program from a file"
    if name == "sed" and any(
        SED_S_FLAGS.search(a) or SED_WE_COMMAND.search(a) for a in args if not _is_flag(a)
    ):
        return "sed script could write a file or run a command"
    if name == "awk" and any(AWK_DANGEROUS.search(a) for a in positional):
        return "awk program could write a file or run a command"
    return None


def _check_command(command: str, allowlist: dict) -> list[str]:
    """Return the problems with one non-fix command line (secrets are checked apart)."""
    segments = _split_pipeline(command)
    if segments == "control":
        return ["shell control not allowed"]
    if segments == "parse":
        return ["cannot parse command"]
    try:
        parts = [shlex.split(s) for s in segments]
    except ValueError:
        return ["cannot parse command"]

    problems: list[str] = []
    first = parts[0]
    allowed = allowlist["commands"]
    if not first or first[0] not in allowed:
        problems.append(f"not on the allow-list: {command}")
    else:
        word, second = _subcommand(first)
        listed = allowed[first[0]]
        two = f"{word} {second}" if second else None
        if not (two in listed or word in listed):
            shown = f"{first[0]} {two or word}".strip()
            problems.append(f"not on the allow-list: {shown}")
        flag = _forbidden_flag(first, allowlist["forbidden_flags"])
        if flag:
            problems.append(f"forbidden flag {flag}")
    for tokens in parts[1:]:
        if not tokens or tokens[0] not in allowlist["filters"]:
            problems.append(f"pipe must lead to an allow-listed filter: {command}")
            continue
        problem = _check_filter(tokens)
        if problem:
            problems.append(problem)
    return problems


def _check_lines(
    block_lines: list[str], first_line: int, is_fix: bool, allowlist: dict
) -> list[tuple[int, str]]:
    """Check the commands of one block or script; return (line, message) pairs."""
    problems: list[tuple[int, str]] = []
    for line_no, command in _logical_commands(block_lines, first_line):
        if _mentions_secret(command):
            problems.append((line_no, "Secret access is not allowed"))
        if not is_fix:
            problems += [(line_no, m) for m in _check_command(command, allowlist)]
    return problems


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

    def add(path: Path, line: int, message: str) -> None:
        found.append(Finding(path.relative_to(root), line, message))

    def check_markdown(path: Path, text: str, first_line: int) -> None:
        for block in extract_blocks(text, first_line):
            if block.lang is None:
                add(path, block.start_line, "fenced block needs a language")
                continue
            if block.lang not in allowlist["command_langs"]:
                continue
            if block.is_fix and not any(
                line.strip().startswith(UNDO_PREFIX) for line in block.lines
            ):
                add(path, block.start_line, "proposed fix needs an '# Undo:' line")
            for line_no, message in _check_lines(
                block.lines, block.start_line + 1, block.is_fix, allowlist
            ):
                add(path, line_no, message)

    skill_file = skill_dir / "SKILL.md"
    if skill_file.is_file():
        try:
            _meta, body, body_line = parse_skill(skill_file)
        except ValueError:
            # The frontmatter check reports this; scan the whole file so nothing hides.
            body, body_line = skill_file.read_text(encoding="utf-8"), 1
        check_markdown(skill_file, body, body_line)

    for ref in sorted((skill_dir / "references").glob("*.md")):
        check_markdown(ref, ref.read_text(encoding="utf-8"), 1)

    for script in sorted((skill_dir / "scripts").glob("*")):
        if script.is_file():
            text = script.read_text(encoding="utf-8", errors="replace")
            for line_no, message in _check_lines(text.splitlines(), 1, False, allowlist):
                add(script, line_no, message)
    return found
