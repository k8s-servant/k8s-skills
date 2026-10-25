"""Tests for the install-manifest generator: files derive from the skill list."""

import json
from pathlib import Path

from tools.skillcheck.__main__ import main
from tools.skillcheck.manifests import render_manifests

MARKET = Path(".claude-plugin/marketplace.json")
RELEASE = Path("release-please-config.json")


def make_repo(tmp_path: Path, skills: dict[str, str] | None = None, version: str = "0.0.0") -> Path:
    (tmp_path / ".release-please-manifest.json").write_text(json.dumps({".": version}))
    config = {"release-type": "simple", "packages": {".": {"package-name": "k8s-skills"}}}
    (tmp_path / RELEASE).write_text(json.dumps(config))
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
        "source": "./skills/k8s-a-x",
        "description": "Use when a",
    }
    assert plugins[0]["source"] == "./"


def test_each_plugin_has_its_own_claude_plugin_json(tmp_path):
    out = render_manifests(make_repo(tmp_path, {"k8s-a-x": "Use when a"}, version="1.2.3"))
    bundle = json.loads(out[Path(".claude-plugin/plugin.json")])
    assert bundle["name"] == "k8s-skills" and bundle["version"] == "1.2.3"
    assert "skills" not in bundle  # the bundle finds every skill under skills/
    one = json.loads(out[Path("skills/k8s-a-x/.claude-plugin/plugin.json")])
    assert one["name"] == "k8s-a-x" and one["description"] == "Use when a"
    assert one["skills"] == ["./"]  # the plugin root is the skill folder
    assert one["version"] == "1.2.3"


def test_release_please_bumps_every_versioned_manifest(tmp_path):
    out = render_manifests(make_repo(tmp_path, {"k8s-b-x": "Use when b", "k8s-a-x": "Use when a"}))
    versioned = sorted(rel.as_posix() for rel, text in out.items() if "version" in json.loads(text))
    config = json.loads(out[RELEASE])
    extra = config["packages"]["."]["extra-files"]
    assert [f["path"] for f in extra] == versioned
    assert all(f == {"type": "json", "path": f["path"], "jsonpath": "$.version"} for f in extra)
    assert config["release-type"] == "simple"  # the rest of the config is kept
    assert config["packages"]["."]["package-name"] == "k8s-skills"


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


def broken(tmp_path: Path, text: str | None) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo = make_repo(tmp_path)
    folder = repo / "skills" / "k8s-a-x"
    folder.mkdir(parents=True)
    if text is not None:
        (folder / "SKILL.md").write_text(text)
    return repo


def test_broken_skills_are_reported_not_crashed(tmp_path, capsys):
    cases = {
        None: "No such file",
        "no frontmatter\n": "no YAML frontmatter",
        "---\nname: k8s-a-x\n---\n": "description must be a non-empty string",
        "---\ndescription: 5\n---\n": "description must be a non-empty string",
    }
    for i, (text, reason) in enumerate(cases.items()):
        repo = broken(tmp_path / str(i), text)
        assert main(["manifests", "--write", "--repo", str(repo)]) == 1
        out = capsys.readouterr().out
        assert "skills/k8s-a-x/SKILL.md: " in out and reason in out
        assert "run python -m tools.skillcheck check for details" in out
        assert not (repo / "plugin.json").exists()


def test_hidden_folders_ignored_and_description_stripped(tmp_path):
    repo = make_repo(tmp_path, {"k8s-a-x": "Use when a"})
    (repo / "skills" / "__pycache__").mkdir()
    (repo / "skills" / ".hidden").mkdir()
    (repo / "skills" / "k8s-a-x" / "SKILL.md").write_text(
        "---\nname: k8s-a-x\ndescription: |\n  Use when a\n---\n"
    )
    plugins = json.loads(render_manifests(repo)[MARKET])["plugins"]
    assert [p["name"] for p in plugins] == ["k8s-skills", "k8s-a-x"]
    assert plugins[1]["description"] == "Use when a"
