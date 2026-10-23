"""Checks that every command a skill shows is read-only.

Skills are advice the agent follows, so the only way to promise they cannot change a
cluster is to allow-list what they may tell the agent to run. This check reads every
shell code block in SKILL.md and references/*.md, and every line of scripts/*, and
rejects anything that is not an allow-listed read-only command. The check fails closed:
whatever it cannot positively recognise as safe is a finding.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from tools.skillcheck.findings import Finding
from tools.skillcheck.frontmatter import parse_skill

MARKER = "> Proposed fix: review before running. The agent does not run this."
UNDO_PREFIX = "# Undo:"

FENCE_OPEN = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
# Blockquote and list-item prefixes that may sit in front of a fence.
CONTAINER_PREFIX = re.compile(r"^\s*(?:>\s?|(?:[-*+]|\d+[.)])\s+)*")
QUOTE_PREFIX = re.compile(r"^\s*(?:>\s?)+")
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
SHORT_BOOL = set("ARpwfh")
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
        The parsed mapping with keys commands, filters, forbidden_flags, command_langs.
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
    """

    lang: str | None
    start_line: int
    lines: list[str]
    is_fix: bool


def extract_blocks(md: str, first_line: int = 1) -> list[Block]:
    """Find the fenced code blocks of a Markdown text.

    Fences inside blockquotes and list items count, as a renderer would show them.

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
        opened = FENCE_OPEN.match(CONTAINER_PREFIX.sub("", text[i]))
        if not opened:
            i += 1
            continue
        fence, info = opened.group(2), opened.group(3).strip()
        quoted = QUOTE_PREFIX.match(text[i]) is not None
        above = next((t.rstrip() for t in reversed(text[:i]) if t.strip()), "")
        content: list[str] = []
        j = i + 1
        while j < len(text):
            stripped = CONTAINER_PREFIX.sub("", text[j]).strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                break
            content.append(QUOTE_PREFIX.sub("", text[j]) if quoted else text[j])
            j += 1
        lang = None
        if info:
            found = LANG.match(info)
            lang = found.group(1).lower() if found else ""
        blocks.append(Block(lang, first_line + i, content, above == MARKER))
        i = j + 1
    return blocks


def _trailing_backslashes(line: str) -> int:
    return len(line) - len(line.rstrip("\\"))


def _logical_commands(block_lines: list[str], first_line: int) -> list[tuple[int, str, bool]]:
    """Turn raw lines into (line number, command, had_prompt) triples.

    Blank lines and comments are dropped, a leading `$ ` prompt is removed and
    backslash continuations are joined (an odd number of trailing backslashes
    continues; an even number is escaped backslashes). The line number is that of the
    first line.
    """
    commands: list[tuple[int, str, bool]] = []
    pending: list[str] = []
    start, prompted = 0, False
    for offset, raw in enumerate(block_lines):
        line = raw.strip()
        if not pending and (not line or line.startswith("#")):
            continue
        if not pending:
            start, prompted = first_line + offset, line.startswith("$ ")
            if prompted:
                line = line[2:].lstrip()
        if _trailing_backslashes(line) % 2 == 1:
            pending.append(line[:-1].strip())
            continue
        pending.append(line)
        commands.append((start, " ".join(p for p in pending if p), prompted))
        pending = []
    if pending:
        commands.append((start, " ".join(p for p in pending if p), prompted))
    return commands


def _mentions_secret(text: str) -> bool:
    """True if any word of the text names the Secret resource."""
    for word in WORD_SPLIT.split(text.lower()):
        if word in SECRET_WORDS or word.startswith(SECRET_PREFIXES):
            return True
    return False


def _scan(command: str, strict: bool) -> list[list[str]] | str:
    """Split a command into pipe segments of words, as bash would see them.

    Words are returned with quotes resolved, so every later check sees the text bash
    would pass to the program. Anything where bash's result could differ from what is
    written (backslash escapes, `$'` and `$"` quoting, command substitution, brace
    expansion, variables) is rejected rather than interpreted.

    Args:
        command: One logical command line.
        strict: True for commands the agent would run. False for proposed fixes,
            where control operators and variables are tolerated and only used to
            split words.

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
        if c == "$":
            if nxt == "(" or (quote is None and nxt in "'\""):
                return "control"
            if nxt == "{" or (strict and VARIABLE_START.match(nxt)):
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
        elif c == "|" or c in ";&<>()":
            if strict and c != "|":
                return "control"
            if strict and nxt == "|":
                return "control"
            flush()
            if c == "|" or not strict:
                segments.append([])
            if c == "|" and nxt == "|":
                i += 1
        else:
            word.append(c)
            in_word = True
    if quote:
        return "parse"
    flush()
    return segments


def _is_flag(token: str) -> bool:
    return token.startswith("-") and token != "-"


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
        if token.startswith("--"):
            name = token.split("=", 1)[0]
            if name in every and name not in allowed:
                problems.append("global flag not allowed")
            if name == "--raw":
                value = token.split("=", 1)[1] if "=" in token else "".join(args[i + 1 : i + 2])
                if "%" in value:
                    problems.append("percent-encoding in a --raw path is not allowed")
        elif _is_flag(token) and not token[1:].isdigit():
            for letter in token[1:]:
                flag = f"-{letter}"
                if flag in every and flag not in allowed:
                    problems.append("global flag not allowed")
                    break
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
    """Return the problems with one non-fix command line (secrets are checked apart)."""
    segments = _scan(command, strict=True)
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
    """Check a command for Secret access, on the raw text and on the resolved words."""
    if _mentions_secret(command):
        return ["Secret access is not allowed"]
    segments = _scan(command, strict=False)
    if isinstance(segments, str):
        # Obfuscated or unparseable text cannot be shown to be free of Secret access.
        return ["shell control not allowed"] if segments == "control" else ["cannot parse command"]
    if any(_mentions_secret(w) for words in segments for w in words):
        return ["Secret access is not allowed"]
    return []


def _check_lines(
    block_lines: list[str], first_line: int, is_fix: bool, allowlist: dict, lang: str | None
) -> list[tuple[int, str]]:
    """Check the commands of one block or script; return (line, message) pairs.

    Which lines count as commands depends on the language: everything in a command
    language, only `$ ` lines in `console` (the rest is output), and for any other
    language only lines that start with an allow-listed program, so a command cannot
    hide in a block that looks like plain text.
    """
    problems: list[tuple[int, str]] = []
    if is_fix:
        for offset, raw in enumerate(block_lines):
            if raw.strip().startswith(UNDO_PREFIX) and _mentions_secret(raw):
                problems.append((first_line + offset, "Secret access is not allowed"))
    for line_no, command, prompted in _logical_commands(block_lines, first_line):
        starts_command = command.split(None, 1)[0] in allowlist["commands"]
        if lang == "console" and not (prompted or starts_command):
            continue
        other_lang = lang not in (None, "console") and lang not in allowlist["command_langs"]
        if other_lang and not starts_command:
            continue
        problems += [(line_no, m) for m in _secret_problems(command)]
        if not is_fix:
            problems += [(line_no, m) for m in _check_command(command, allowlist)]
    return list(dict.fromkeys(problems))


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
        for block in extract_blocks(text, first_line):
            if block.lang is None:
                add(path, block.start_line, "fenced block needs a language")
                continue
            is_command_lang = block.lang in allowlist["command_langs"]
            has_undo = any(ln.strip().startswith(UNDO_PREFIX) for ln in block.lines)
            if is_command_lang and block.is_fix and not has_undo:
                add(path, block.start_line, "proposed fix needs an '# Undo:' line")
            for line_no, message in _check_lines(
                block.lines, block.start_line + 1, block.is_fix, allowlist, block.lang
            ):
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
                read(script).splitlines(), 1, False, allowlist, None
            ):
                add(script, line_no, message)
    return found
