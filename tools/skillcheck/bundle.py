"""Builds the k8s-skills plugin as the Claude plugin directory accepts it.

The bundle in the marketplace has the repository root as its source, so a directory
submission of it would carry the test kit and tooling: scripts the directory takes only
from Verified organizations. This writes the same plugin with only its manifest, icon,
README, LICENSE and skills, for the release workflow to publish on the `plugin` branch.
Any skill file of a type the directory refuses fails the build instead of the review.
"""

import re
import shutil
from pathlib import Path

from tools.skillcheck.discovery import skill_dirs
from tools.skillcheck.manifests import REPOSITORY
from tools.skillcheck.package import _is_junk

# File types the directory accepts from any publisher (text must not start with `#!`).
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
TOP_FILES = (".claude-plugin/plugin.json", ".claude-plugin/icon.png", "LICENSE")
BLOB = f"{REPOSITORY}/blob/main/"
# A Markdown link or an HTML image whose target is a repository path, not a URL or anchor.
RELATIVE_LINK = re.compile(r"\]\((?!https?:|mailto:|#)([^)]+)\)")
RELATIVE_IMAGE = re.compile(r'src="(?!https?:)([^"]+)"')


class BundleError(Exception):
    """Raised when the bundle cannot be built; `problems` holds one `<path>: <reason>` each."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def _refusal(path: Path) -> str | None:
    """Why the directory would refuse this skill file, or None if it accepts it."""
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return None
    if suffix not in TEXT_SUFFIXES:
        return "file type the plugin directory refuses"
    data = path.read_bytes()
    if data.startswith(b"#!"):
        return "starts with #!"
    if b"\0" in data:
        return "holds a NUL byte"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "not UTF-8 text"
    return None


def _readme(text: str) -> str:
    """The README with its repository links made absolute: the bundle has no docs or tests."""
    text = RELATIVE_IMAGE.sub(lambda m: f'src="{BLOB}{m[1]}?raw=true"', text)
    return RELATIVE_LINK.sub(lambda m: f"]({BLOB}{m[1]})", text)


def build_bundle(repo: Path, out: Path) -> list[Path]:
    """Write the plugin into the empty folder `out`; return the files written.

    Raises:
        BundleError: If `out` is not empty or a skill holds a file the directory refuses.
    """
    if out.exists() and any(out.iterdir()):
        raise BundleError([f"{out}: not empty"])
    copies: dict[Path, Path] = {repo / rel: Path(rel) for rel in TOP_FILES}
    problems = []
    for skill_dir in skill_dirs(repo):
        for path in sorted(skill_dir.rglob("*")):
            if not path.is_file() or _is_junk(path.relative_to(skill_dir)):
                continue
            rel = path.relative_to(repo)
            reason = _refusal(path)
            if reason:
                problems.append(f"{rel.as_posix()}: {reason}")
            copies[path] = rel
    if problems:
        raise BundleError(problems)
    written = []
    for source, rel in copies.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        written.append(target)
    readme = out / "README.md"
    readme.write_text(_readme((repo / "README.md").read_text(encoding="utf-8")), encoding="utf-8")
    written.append(readme)
    return written
