#!/usr/bin/env python3
"""Create a deterministic, minimal source archive for the one-pod study runner."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


SCHEMA = "pixieology.fae_tax_epistemics.source_bundle.v1"
ROOT_FILES = (
    "README.md",
    "pyproject.toml",
    "pixieology.config.json",
    "pixie_env.py",
    "fae_tax_epistemics.py",
    "run_fae_tax_epistemics.py",
    "tests/test_fae_tax_epistemics.py",
)
ALLOWED_SUFFIXES = {".json", ".md", ".py", ".sbatch", ".sh", ".yaml", ".yml"}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files(repo_root: Path) -> list[Path]:
    candidates = [repo_root / name for name in ROOT_FILES]
    for directory in (
        repo_root / "fae_bench",
        repo_root / "experiments" / "fae_tax_epistemics_v1",
    ):
        candidates.extend(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and path.suffix in ALLOWED_SUFFIXES
            and "__pycache__" not in path.parts
        )
    unique = sorted(
        {path.resolve() for path in candidates if path.is_file()},
        key=lambda path: path.relative_to(repo_root).as_posix(),
    )
    missing = [name for name in ROOT_FILES if not (repo_root / name).is_file()]
    if missing:
        raise FileNotFoundError("required source files are missing: " + ", ".join(missing))
    return unique


def _tar_info(name: str, size: int, *, executable: bool = False) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = size
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o755 if executable else 0o644
    return info


def build_archive(repo_root: Path, destination: Path) -> Path:
    root = repo_root.expanduser().resolve()
    output = destination.expanduser().resolve()
    if output.exists() or output.with_suffix(output.suffix + ".sha256").exists():
        raise FileExistsError(f"refusing to overwrite source bundle or sidecar: {output}")
    files = source_files(root)
    rows = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    source_manifest = (
        json.dumps(
            {"schema": SCHEMA, "file_count": len(rows), "files": rows},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".partial")
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
                with tarfile.open(fileobj=zipped, mode="w|") as archive:
                    archive.addfile(
                        _tar_info("Pixieology/SOURCE_MANIFEST.json", len(source_manifest)),
                        io.BytesIO(source_manifest),
                    )
                    for path in files:
                        payload = path.read_bytes()
                        relative = path.relative_to(root).as_posix()
                        executable = path.suffix in {".sh", ".sbatch"}
                        archive.addfile(
                            _tar_info(
                                f"Pixieology/{relative}",
                                len(payload),
                                executable=executable,
                            ),
                            io.BytesIO(payload),
                        )
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    digest = sha256_file(output)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="utf-8"
    )
    return output


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repo-root", type=Path, required=True)
    result.add_argument("--destination", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        archive = build_archive(args.repo_root, args.destination)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(
        json.dumps(
            {
                "archive": str(archive),
                "sha256": sha256_file(archive),
                "sidecar": str(archive.with_suffix(archive.suffix + ".sha256")),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
