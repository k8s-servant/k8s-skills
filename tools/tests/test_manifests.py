"""Tests for the install-manifest generator: files derive from the skill list."""

import json
from pathlib import Path

from tools.skillcheck.__main__ import main
from tools.skillcheck.manifests import render_manifests

MARKET = Path(".claude-plugin/marketplace.json")


def make_repo(tmp_path: Path, skills: dict[str, str] | None = None, version: str = "0.0.0") -> Path:
    (tmp_path / ".release-please-manifest.json").write_text(json.dumps({".": version}))
    for name, desc in (skills or {}).items():
        folder = tmp_path / "skills" / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {desc}\nlicense: Apache-2.0\n---\n\n## When to use\n"
        )
    return tmp_path


def test_marketplace_has_bundle_then_one_entry_per_skill(tmp_path):
    repo = make_repo(tmp_path, {"k8s-b-x": "Use when b", "k8s-a-x": "Use when a"})
    plugins = json.loads(render_manifests(repo)[MARKET])["plugins"]
    assert [p["name"] for p in plugins] == ["k8s-skills", "k8s-a-x", "k8s-b-x"]
    assert plugins[1] == {
        "name": "k8s-a-x",
        "source": "./",
        "description": "Use when a",
        "skills": ["./skills/k8s-a-x"],
    }
    assert "skills" not in plugins[0]


def test_versions_follow_release_manifest(tmp_path):
    out = render_manifests(make_repo(tmp_path, version="1.2.3"))
    assert json.loads(out[Path("plugin.json")])["version"] == "1.2.3"
    assert json.loads(out[Path("gemini-extension.json")])["version"] == "1.2.3"


def test_output_is_stable(tmp_path):
    repo = make_repo(tmp_path, {"k8s-a-x": "Use when a"})
    first, second = render_manifests(repo), render_manifests(repo)
    assert first == second
    text = first[Path("plugin.json")]
    assert text.endswith("}\n") and '\n  "name"' in text
    assert list(json.loads(text)) == [
        "$schema", "name", "version", "description", "license", "repository", "keywords",
    ]  # fmt: skip
    assert list(json.loads(first[MARKET])) == ["name", "owner", "metadata", "plugins"]


def test_check_mode_detects_drift(tmp_path, capsys):
    repo = make_repo(tmp_path)
    assert main(["manifests", "--write", "--repo", str(repo)]) == 0
    make_repo(tmp_path, {"k8s-a-x": "Use when a"})
    assert main(["manifests", "--check", "--repo", str(repo)]) == 1
    assert (
        ".claude-plugin/marketplace.json is out of date: "
        "run python -m tools.skillcheck manifests --write"
    ) in capsys.readouterr().out


def test_write_then_check_passes(tmp_path):
    repo = make_repo(tmp_path, {"k8s-a-x": "Use when a"})
    assert main(["manifests", "--check", "--repo", str(repo)]) == 1
    assert main(["manifests", "--write", "--repo", str(repo)]) == 0
    assert main(["manifests", "--check", "--repo", str(repo)]) == 0
