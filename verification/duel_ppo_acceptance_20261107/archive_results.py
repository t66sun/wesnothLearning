"""Copy immutable evidence from the one completed #227 experiment."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def archive(acceptance: Path, output: Path) -> None:
    run = acceptance / "source/runs/duel_ppo_comparison_20261106"
    assert (acceptance / "driver.exit").read_text().strip() == "0"
    assert (acceptance / "SOURCE_COMMIT").read_text().strip() == (
        "43325b33696de4db8ee546e1c6bedb7230a73b37"
    )
    output.mkdir(parents=True, exist_ok=False)
    files = sorted(path for path in run.rglob("*") if path.is_file())
    inventory = []
    for path in files:
        entry = {"path": str(path.relative_to(run)), "bytes": path.stat().st_size,
                 "sha256": sha256(path)}
        if path.is_symlink():
            entry["symlink_target"] = str(path.readlink())
        inventory.append(entry)
    write_json(output / "RUN_FILES_SHA256.json", inventory)
    print(f"Indexed {len(files)} files / {sum(x['bytes'] for x in inventory)} bytes", flush=True)

    full = output / "complete-run.tar.gz"
    with tarfile.open(full, "w:gz", compresslevel=1) as bundle:
        bundle.add(run, arcname="run")
    print(f"Archived complete run: {full.stat().st_size} bytes", flush=True)

    metadata = output / "raw-metadata.tar.gz"
    with tarfile.open(metadata, "w:gz", compresslevel=1) as bundle:
        for path in files:
            if path.suffix in (".json", ".jsonl", ".log"):
                bundle.add(path, arcname="run/" + str(path.relative_to(run)), recursive=False)
        for name in ("SOURCE_COMMIT", "driver.exit", "driver.log", "launcher.txt",
                     "root-fixture-tests.log"):
            path = acceptance / name
            if path.exists():
                bundle.add(path, arcname="acceptance/" + name, recursive=False)

    recorded = output / "recorded"
    recorded.mkdir()
    readable = ["result.json", "bc-endpoint.json", "input-audit.json",
                "mc-diagnostics.json", "launch.json", "evaluation/roles.json",
                "evaluation/summary.json"]
    readable += [str(path.relative_to(run)) for path in sorted(run.glob("*-exit.json"))]
    for name in readable:
        target = recorded / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run / name, target)
    for name in ("SOURCE_COMMIT", "driver.exit", "driver.log", "launcher.txt",
                 "root-fixture-tests.log"):
        if (acceptance / name).exists():
            shutil.copyfile(acceptance / name, recorded / name)

    identity = {
        "execution_source_commit": (acceptance / "SOURCE_COMMIT").read_text().strip(),
        "execution_source_archive": str(acceptance / "source.tar"),
        "execution_source_archive_sha256": sha256(acceptance / "source.tar"),
        "run": str(run),
        "files": len(files), "uncompressed_bytes": sum(x["bytes"] for x in inventory),
        "archives": [{"path": str(path), "bytes": path.stat().st_size,
                      "sha256": sha256(path)} for path in (full, metadata)],
        "scope": "Byte-preserved post-run archive; no games, training, or input rewrites.",
    }
    write_json(output / "ARCHIVES.json", identity)
    print(json.dumps(identity), flush=True)


if __name__ == "__main__":
    archive(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
