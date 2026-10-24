"""Checks the shape of a skill: fixed sections, sources, and working relative links.

Every skill follows the same five sections so an agent (and a reviewer) always finds
the investigation steps and the proposed fix in the same place, and a skill that cites
no source or points at a missing file is advice nobody can verify or follow.
"""

from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt

from tools.skillcheck.findings import Finding
from tools.skillcheck.frontmatter import parse_skill

SECTIONS = ["When to use", "Investigate", "Read the results", "Proposed fix", "Sources"]
# Link targets that are not files in this repository.
EXTERNAL_PREFIXES = ("http://", "https://", "ftp://", "mailto:", "tel:", "data:", "#")


def _headings_and_links(
    text: str, first_line: int
) -> tuple[list[tuple[int, str]], list[tuple[int, str, str]]]:
    """Find the H2 headings and the links of a Markdown text.

    Args:
        text: The Markdown text.
        first_line: The file line number of the first line of `text`.

    Returns:
        The (line, title) of each H2, and the (line, section, href) of each link, where
        section is the title of the H2 the link sits under ("" before the first one).
    """
    headings: list[tuple[int, str]] = []
    links: list[tuple[int, str, str]] = []
    section = ""
    tokens = MarkdownIt("commonmark").parse(text)
    for i, token in enumerate(tokens):
        line = first_line + (token.map[0] if token.map else 0)
        if token.type == "heading_open" and token.tag == "h2":
            section = tokens[i + 1].content.strip()
            headings.append((line, section))
        elif token.type == "inline":
            for child in token.children or []:
                if child.type == "link_open":
                    links.append((line, section, str(child.attrGet("href") or "")))
    return headings, links


def _resolve(href: str, source: Path) -> Path | None:
    """Return the local file an href points at, or None if it is not a local file."""
    if href.lower().startswith(EXTERNAL_PREFIXES):
        return None
    target = unquote(href.split("#", 1)[0])
    return (source.parent / target).resolve() if target else None


def check_structure(skill_dir: Path) -> list[Finding]:
    """Check one skill's sections, Sources links, relative links and references.

    Args:
        skill_dir: A `<repo>/skills/<name>` folder.

    Returns:
        One Finding per broken rule, with paths relative to the repository root.

    Raises:
        ValueError: If SKILL.md has no frontmatter (the caller reports it).
    """
    root = skill_dir.parent.parent
    skill_file = skill_dir / "SKILL.md"
    _meta, body, first_line = parse_skill(skill_file)
    found: list[Finding] = []

    headings, links = _headings_and_links(body, first_line)
    rel_skill = skill_file.relative_to(root)
    if [title for _line, title in headings] != SECTIONS:
        found.append(Finding(rel_skill, 1, f"sections must be: {', '.join(SECTIONS)}"))
    if not any(s == "Sources" and h.startswith("https://") for _l, s, h in links):
        found.append(Finding(rel_skill, 1, "Sources must contain at least one https:// link"))

    linked: set[Path] = set()
    markdown_files = [skill_file, *sorted((skill_dir / "references").rglob("*.md"))]
    for md in markdown_files:
        if md == skill_file:
            file_links = links
        else:
            file_links = _headings_and_links(md.read_text(encoding="utf-8"), 1)[1]
        for line, _section, href in file_links:
            target = _resolve(href, md)
            if target is None:
                continue
            if md == skill_file:
                linked.add(target)
            if not target.exists():
                found.append(
                    Finding(
                        md.relative_to(root), line, f"broken relative link: {href.split('#')[0]}"
                    )
                )

    for ref in sorted((skill_dir / "references").rglob("*.md")):
        if ref.resolve() not in linked:
            found.append(Finding(ref.relative_to(root), 1, "reference not linked from SKILL.md"))
    return found
