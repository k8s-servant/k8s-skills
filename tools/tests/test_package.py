"""Tests for release packaging: one reproducible zip per skill plus checksums."""

import zipfile
from pathlib import Path

from tools.skillcheck.__main__ import main
from tools.skillcheck.package import package_skills


def make_repo(tmp_path: Path) -> Path:
    for name in ("k8s-b-x", "k8s-a-x"):
        folder = tmp_path / "skills" / name
        (folder / "references").mkdir(parents=True)
        (folder / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
        (folder / "references" / "notes.md").write_text("notes\n")
    return tmp_path


def test_zip_per_skill_with_folder_prefix(tmp_path):
    repo = make_repo(tmp_path / "repo")
    out = tmp_path / "dist"
    zips = package_skills(repo, out)
    assert [z.name for z in zips] == ["k8s-a-x.zip", "k8s-b-x.zip"]
    with zipfile.ZipFile(out / "k8s-a-x.zip") as zf:
        assert zf.namelist() == ["k8s-a-x/SKILL.md", "k8s-a-x/references/notes.md"]
        assert {i.date_time for i in zf.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    sums = (out / "SHA256SUMS").read_text().splitlines()
    assert [line.split("  ")[1] for line in sums] == ["k8s-a-x.zip", "k8s-b-x.zip"]


def test_zips_are_reproducible(tmp_path):
    repo = make_repo(tmp_path / "repo")
    package_skills(repo, tmp_path / "one")
    package_skills(repo, tmp_path / "two")
    for name in ("k8s-a-x.zip", "k8s-b-x.zip", "SHA256SUMS"):
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes()


def test_package_subcommand(tmp_path):
    repo = make_repo(tmp_path / "repo")
    assert main(["package", "--out", str(tmp_path / "dist"), "--repo", str(repo)]) == 0
    assert (tmp_path / "dist" / "k8s-b-x.zip").is_file()


def test_dotfiles_and_pycache_are_not_packaged(tmp_path):
    repo = make_repo(tmp_path / "repo")
    folder = repo / "skills" / "k8s-a-x"
    (folder / ".DS_Store").write_text("x")
    (folder / "scripts" / "__pycache__").mkdir(parents=True)
    (folder / "scripts" / "__pycache__" / "x.pyc").write_text("x")
    (folder / ".hidden").mkdir()
    (folder / ".hidden" / "notes.md").write_text("x")
    package_skills(repo, tmp_path / "dist")
    with zipfile.ZipFile(tmp_path / "dist" / "k8s-a-x.zip") as zf:
        assert zf.namelist() == ["k8s-a-x/SKILL.md", "k8s-a-x/references/notes.md"]
