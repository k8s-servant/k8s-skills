"""Builds the release zips: one `<skill>.zip` per skill plus a `SHA256SUMS` file.

Archives must be byte-for-byte reproducible so a rebuilt release can be verified
against the published checksums: entries are sorted, timestamps are fixed and file
modes are normalised.
"""

import hashlib
import zipfile
from pathlib import Path

from tools.skillcheck.discovery import skill_dirs

# The earliest timestamp the zip format can store.
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _write_zip(skill_dir: Path, target: Path) -> None:
    """Write one skill folder as a zip whose entries live under `<skill>/`."""
    files = sorted(p for p in skill_dir.rglob("*") if p.is_file())
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(f"{skill_dir.name}/{path.relative_to(skill_dir).as_posix()}")
            info.date_time = FIXED_TIME
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def package_skills(repo: Path, out: Path) -> list[Path]:
    """Zip every skill of `repo` into `out` and write `SHA256SUMS`; return the zips."""
    out.mkdir(parents=True, exist_ok=True)
    zips = []
    for skill_dir in skill_dirs(repo):
        target = out / f"{skill_dir.name}.zip"
        _write_zip(skill_dir, target)
        zips.append(target)
    sums = "".join(f"{hashlib.sha256(z.read_bytes()).hexdigest()}  {z.name}\n" for z in zips)
    (out / "SHA256SUMS").write_text(sums)
    return zips
