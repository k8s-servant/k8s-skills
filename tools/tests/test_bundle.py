"""Tests for the directory bundle: the k8s-skills plugin with only the files a plugin needs."""

from pathlib import Path

import pytest

from tools.skillcheck.__main__ import main
from tools.skillcheck.bundle import BundleError, build_bundle


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / ".claude-plugin").mkdir(parents=True)
    (tmp_path / ".claude-plugin" / "plugin.json").write_text('{"name": "k8s-skills"}\n')
    (tmp_path / ".claude-plugin" / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text("{}\n")
    (tmp_path / "README.md").write_text("# k8s-skills\n")
    (tmp_path / "LICENSE").write_text("Apache License\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "run.sh").write_text("#!/usr/bin/env bash\n")
    for name in ("k8s-b-x", "k8s-a-x"):
        folder = tmp_path / "skills" / name
        (folder / "references").mkdir(parents=True)
        (folder / ".claude-plugin").mkdir()
        (folder / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
        (folder / "references" / "notes.md").write_text("notes\n")
        (folder / ".claude-plugin" / "plugin.json").write_text("{}\n")
    return tmp_path


def listing(out: Path) -> list[str]:
    return sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())


def test_bundle_holds_the_plugin_manifest_icon_readme_license_and_skills(tmp_path):
    repo = make_repo(tmp_path / "repo")
    out = tmp_path / "bundle"
    build_bundle(repo, out)
    assert listing(out) == [
        ".claude-plugin/icon.png",
        ".claude-plugin/plugin.json",
        "LICENSE",
        "README.md",
        "skills/k8s-a-x/SKILL.md",
        "skills/k8s-a-x/references/notes.md",
        "skills/k8s-b-x/SKILL.md",
        "skills/k8s-b-x/references/notes.md",
    ]
    assert (out / ".claude-plugin" / "plugin.json").read_text() == '{"name": "k8s-skills"}\n'


def test_bundle_skips_dotfiles_and_pycache(tmp_path):
    repo = make_repo(tmp_path / "repo")
    folder = repo / "skills" / "k8s-a-x"
    (folder / ".DS_Store").write_text("x")
    (folder / "references" / "__pycache__").mkdir()
    (folder / "references" / "__pycache__" / "x.pyc").write_text("x")
    build_bundle(repo, tmp_path / "bundle")
    assert not [f for f in listing(tmp_path / "bundle") if "DS_Store" in f or "pycache" in f]


def test_bundle_refuses_a_file_type_the_directory_refuses(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / "skills" / "k8s-a-x" / "check.sh").write_text("kubectl get pods\n")
    with pytest.raises(BundleError, match="skills/k8s-a-x/check.sh"):
        build_bundle(repo, tmp_path / "bundle")


def test_bundle_refuses_a_text_file_that_starts_with_a_shebang(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / "skills" / "k8s-a-x" / "references" / "run.txt").write_text("#!/bin/sh\n")
    with pytest.raises(BundleError, match="references/run.txt"):
        build_bundle(repo, tmp_path / "bundle")


def test_bundle_refuses_an_output_folder_that_is_not_empty(tmp_path):
    repo = make_repo(tmp_path / "repo")
    out = tmp_path / "bundle"
    out.mkdir()
    (out / "stale.md").write_text("x")
    with pytest.raises(BundleError, match="not empty"):
        build_bundle(repo, out)


def test_bundle_subcommand(tmp_path):
    repo = make_repo(tmp_path / "repo")
    out = tmp_path / "bundle"
    assert main(["bundle", "--out", str(out), "--repo", str(repo)]) == 0
    assert (out / "skills" / "k8s-b-x" / "SKILL.md").is_file()


def test_bundle_subcommand_reports_a_refused_file(tmp_path, capsys):
    repo = make_repo(tmp_path / "repo")
    (repo / "skills" / "k8s-a-x" / "check.sh").write_text("x\n")
    assert main(["bundle", "--out", str(tmp_path / "bundle"), "--repo", str(repo)]) == 1
    assert "skills/k8s-a-x/check.sh" in capsys.readouterr().out


def test_bundle_points_readme_links_at_the_repository(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / "README.md").write_text(
        '<img src="docs/assets/demo.svg">\n'
        "[guide](CONTRIBUTING.md#cloud-scenarios), [site](https://example.com), [up](#top)\n"
    )
    build_bundle(repo, tmp_path / "bundle")
    blob = "https://github.com/k8s-servant/k8s-skills/blob/main/"
    assert (tmp_path / "bundle" / "README.md").read_text() == (
        f'<img src="{blob}docs/assets/demo.svg?raw=true">\n'
        f"[guide]({blob}CONTRIBUTING.md#cloud-scenarios), [site](https://example.com), [up](#top)\n"
    )
