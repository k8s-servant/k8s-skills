"""Generates the install manifests for each agent from the skill list.

The skills folders are the single source of truth: marketplace entries and versions are
derived, never hand-edited, so an install path cannot drift from what the repository
ships. `--check` fails CI when a committed file is stale.
"""

import json
from pathlib import Path

from tools.skillcheck.frontmatter import parse_skill

NAME = "k8s-skills"
BUNDLE_DESCRIPTION = "All k8s-skills: read-only Kubernetes skills for any AI agent"
DESCRIPTION = "Read-only Kubernetes troubleshooting skills for any AI agent"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
REPOSITORY = "https://github.com/k8s-servant/k8s-skills"
STALE = "{path} is out of date: run python -m tools.skillcheck manifests --write"


def _dump(data: dict) -> str:
    """Serialize with 2-space indent and a trailing newline, keeping key order."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def render_manifests(repo: Path) -> dict[Path, str]:
    """Render every generated manifest.

    Args:
        repo: Repository root holding `skills/` and `.release-please-manifest.json`.

    Returns:
        Relative path to file text.

    Raises:
        ValueError: If a SKILL.md cannot be parsed or lacks a description.
    """
    manifest = json.loads((repo / ".release-please-manifest.json").read_text(encoding="utf-8"))
    version = manifest["."]
    skills_dir = repo / "skills"
    folders = sorted(p for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []
    plugins: list[dict] = [{"name": NAME, "source": "./", "description": BUNDLE_DESCRIPTION}]
    for folder in folders:
        meta, _, _ = parse_skill(folder / "SKILL.md")
        plugins.append(
            {
                "name": folder.name,
                "source": "./",
                "description": meta["description"],
                "skills": [f"./skills/{folder.name}"],
            }
        )
    marketplace = {
        "name": NAME,
        "owner": {"name": "k8s-servant"},
        "metadata": {"description": DESCRIPTION},
        "plugins": plugins,
    }
    plugin = {
        "$schema": SCHEMA,
        "name": NAME,
        "version": version,
        "description": DESCRIPTION,
        "license": "Apache-2.0",
        "repository": REPOSITORY,
        "keywords": ["kubernetes", "k8s", "sre", "troubleshooting", "agent-skills"],
    }
    gemini = {"name": NAME, "version": version, "description": DESCRIPTION}
    return {
        Path(".claude-plugin/marketplace.json"): _dump(marketplace),
        Path("plugin.json"): _dump(plugin),
        Path("gemini-extension.json"): _dump(gemini),
    }


def write_manifests(repo: Path) -> int:
    """Write the generated files into the repository."""
    for rel, text in render_manifests(repo).items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return 0


def check_manifests(repo: Path) -> int:
    """Report each stale or missing generated file; return 1 if any."""
    stale = [
        rel
        for rel, text in render_manifests(repo).items()
        if not (repo / rel).is_file() or (repo / rel).read_text(encoding="utf-8") != text
    ]
    for rel in stale:
        print(STALE.format(path=rel.as_posix()))
    return 1 if stale else 0
