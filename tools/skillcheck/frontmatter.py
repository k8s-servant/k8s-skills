"""Checks the YAML frontmatter of each SKILL.md against the portable skill format.

Keeping to the common subset of fields means every skill loads the same way in any
agent that reads the Agent Skills format, not only in one product.
"""

import re
from pathlib import Path

import yaml

from tools.skillcheck.findings import Finding

ALLOWED_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RESERVED_WORDS = ("claude", "anthropic")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_COMPATIBILITY = 500
MAX_LINES = 500


def parse_skill(path: Path) -> tuple[dict, str, int]:
    """Split a SKILL.md into its frontmatter and body.

    Args:
        path: The SKILL.md file.

    Returns:
        The parsed frontmatter, the body text, and the 1-based line number where
        the body starts.

    Raises:
        ValueError: If the file has no frontmatter block, or it is not a mapping.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("no YAML frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("no YAML frontmatter")
    try:
        meta = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML frontmatter: {exc}") from exc
    if meta is None or not isinstance(meta, dict):
        raise ValueError("no YAML frontmatter")
    return meta, "\n".join(lines[end + 1 :]), end + 2


def check_frontmatter(skill_dir: Path) -> list[Finding]:
    """Check one skill folder's SKILL.md frontmatter and length.

    Args:
        skill_dir: A `<repo>/skills/<name>` folder.

    Returns:
        One Finding per broken rule, with paths relative to the repository root.
    """
    skill_file = skill_dir / "SKILL.md"
    rel = skill_dir.relative_to(skill_dir.parent.parent) / "SKILL.md"

    def finding(message: str) -> Finding:
        return Finding(rel, 1, message)

    try:
        meta, _body, _line = parse_skill(skill_file)
    except ValueError as exc:
        return [finding(str(exc))]

    found: list[Finding] = []
    for field in meta:
        if field not in ALLOWED_FIELDS:
            found.append(finding(f"field not portable: {field}"))

    name = meta.get("name")
    if not isinstance(name, str) or not name:
        found.append(finding("name missing"))
    else:
        if name != skill_dir.name:
            found.append(finding(f"name must equal folder name {skill_dir.name}"))
        if not name.startswith("k8s-"):
            found.append(finding("name must start with k8s-"))
        if not NAME_PATTERN.match(name) or len(name) > MAX_NAME:
            found.append(finding(f"name must match {NAME_PATTERN.pattern} (max {MAX_NAME})"))
        for word in RESERVED_WORDS:
            if word in name:
                found.append(finding(f"name contains reserved word: {word}"))

    description = meta.get("description")
    if not isinstance(description, str) or not description:
        found.append(finding("description missing"))
    else:
        if not description.startswith("Use when"):
            found.append(finding("description must start with 'Use when'"))
        if len(description) > MAX_DESCRIPTION:
            found.append(finding(f"description longer than {MAX_DESCRIPTION} characters"))

    if meta.get("license") != "Apache-2.0":
        found.append(finding("license must be Apache-2.0"))

    compatibility = meta.get("compatibility")
    if compatibility is not None and (
        not isinstance(compatibility, str) or len(compatibility) > MAX_COMPATIBILITY
    ):
        found.append(finding(f"compatibility must be a string of at most {MAX_COMPATIBILITY}"))

    found += _check_metadata(meta.get("metadata"), finding)

    if len(skill_file.read_text(encoding="utf-8").splitlines()) > MAX_LINES:
        found.append(finding(f"SKILL.md longer than {MAX_LINES} lines"))
    return found


def _check_metadata(metadata: object, finding) -> list[Finding]:
    """Check that metadata is a string map with the verification fields."""
    if not isinstance(metadata, dict):
        return [
            finding("metadata.verified-with missing"),
            finding("metadata.verified-on missing"),
        ]
    found = []
    # YAML turns an unquoted 2026-10-23 into a date; require quotes so it stays a string.
    if not all(isinstance(v, str) for v in metadata.values()):
        found.append(finding("metadata values must be strings (quote dates)"))
    for key in ("verified-with", "verified-on"):
        if key not in metadata:
            found.append(finding(f"metadata.{key} missing"))
    verified_on = metadata.get("verified-on")
    if isinstance(verified_on, str) and not DATE_PATTERN.match(verified_on):
        found.append(finding("metadata.verified-on must be YYYY-MM-DD"))
    return found
