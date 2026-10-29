"""Generates the install manifests for each agent from the skill list.

The skills folders are the single source of truth: marketplace entries and versions are
derived, never hand-edited, so an install path cannot drift from what the repository
ships. `--check` fails CI when a committed file is stale.
"""

import json
from pathlib import Path

from tools.skillcheck.discovery import skill_dirs
from tools.skillcheck.frontmatter import parse_skill

NAME = "k8s-skills"
BUNDLE_DESCRIPTION = "All k8s-skills: Kubernetes troubleshooting skills that read first and ask before changing anything"
DESCRIPTION = (
    "Kubernetes troubleshooting skills for any AI agent: read first, ask before changing anything"
)
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
REPOSITORY = "https://github.com/k8s-servant/k8s-skills"
# Fields every Claude plugin.json shares, for the directory listing.
ABOUT = {
    "author": {"name": "k8s-servant", "url": "https://github.com/k8s-servant"},
    "homepage": REPOSITORY,
    "repository": REPOSITORY,
    "license": "Apache-2.0",
}
RELEASE_CONFIG = Path("release-please-config.json")
# Opt-in plugins that ship hooks, not skills: listed only when their folder exists.
HOOK_PLUGINS = {
    "k8s-secret-guard": (
        "Optional hook for Claude Code that blocks shell commands reading Kubernetes Secrets "
        "or cloud secret stores (kubectl, helm, Key Vault, Secrets Manager, Secret Manager). "
        "A best-effort second layer: read-only RBAC stays the guarantee"
    ),
}
STALE = "{path} is out of date: run python -m tools.skillcheck manifests --write"


class ManifestError(Exception):
    """Raised when skills cannot be listed; `problems` holds one `<path>: <reason>` each."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


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
        ManifestError: If any SKILL.md is missing, unparseable or lacks a description.
    """
    manifest = json.loads((repo / ".release-please-manifest.json").read_text(encoding="utf-8"))
    version = manifest["."]
    plugins: list[dict] = [{"name": NAME, "source": "./", "description": BUNDLE_DESCRIPTION}]
    skill_plugins: dict[Path, str] = {}
    problems: list[str] = []
    for folder in skill_dirs(repo):
        path = (folder / "SKILL.md").relative_to(repo).as_posix()
        try:
            meta, _, _ = parse_skill(folder / "SKILL.md")
        except (OSError, ValueError) as exc:
            problems.append(f"{path}: {exc}")
            continue
        description = meta.get("description")
        if not isinstance(description, str) or not description.strip():
            problems.append(f"{path}: description must be a non-empty string")
            continue
        source = f"./skills/{folder.name}"
        plugins.append({"name": folder.name, "source": source, "description": description.strip()})
        # Each skill folder is its own plugin root, so its plugin.json points at "./".
        one = {
            "name": folder.name,
            "version": version,
            "description": description.strip(),
            **ABOUT,
            "skills": ["./"],
        }
        skill_plugins[Path(f"skills/{folder.name}/.claude-plugin/plugin.json")] = _dump(one)
    if problems:
        raise ManifestError(problems)
    for name, description in HOOK_PLUGINS.items():
        if not (repo / "plugins" / name).is_dir():
            continue
        plugins.append({"name": name, "source": f"./plugins/{name}", "description": description})
        one = {"name": name, "version": version, "description": description, **ABOUT}
        skill_plugins[Path(f"plugins/{name}/.claude-plugin/plugin.json")] = _dump(one)
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
    bundle = {"name": NAME, "version": version, "description": DESCRIPTION, **ABOUT}
    files = {
        Path(".claude-plugin/marketplace.json"): _dump(marketplace),
        Path(".claude-plugin/plugin.json"): _dump(bundle),
        **skill_plugins,
        Path("plugin.json"): _dump(plugin),
        Path("gemini-extension.json"): _dump(gemini),
    }
    files[RELEASE_CONFIG] = _release_config(repo, files)
    return files


def _release_config(repo: Path, files: dict[Path, str]) -> str:
    """release-please's config, with `extra-files` listing every manifest that has a version."""
    config = json.loads((repo / RELEASE_CONFIG).read_text(encoding="utf-8"))
    versioned = sorted(
        rel.as_posix() for rel, text in files.items() if "version" in json.loads(text)
    )
    config["packages"]["."]["extra-files"] = [
        {"type": "json", "path": path, "jsonpath": "$.version"} for path in versioned
    ]
    return _dump(config)


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
