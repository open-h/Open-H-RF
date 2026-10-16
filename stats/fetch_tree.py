"""List every file in the Open-H-RF repo with its size.

``save`` writes the listing to ``data/tree.json`` and records the revision it is of in
``data/source_revision.json``. Read from the ``huggingface/Open-H-RF`` clone's git
when it has the revision, which takes a second; otherwise one API crawl of three or
four minutes. No file contents are downloaded either way.

A step of ``refresh_data.py``.
"""

from __future__ import annotations

import collections
import json
import subprocess
import time
from pathlib import Path

from huggingface_hub import HfApi
from scan_files import write_atomically

REPO = "nvidia/Open-H-RF"
OUT = Path(__file__).parent / "data" / "tree.json"
PROVENANCE_OUT = Path(__file__).parent / "data" / "source_revision.json"
# The Hub repo's documents and git history, cloned by huggingface/setup.sh.
DOCS = Path(__file__).resolve().parent.parent / "huggingface" / "Open-H-RF"


def fetch_tree(revision: str = "main") -> tuple[str, list[dict]]:
    """The commit ``revision`` is at, and the listing of its files.

    The Hub crawl is one paginated walk of ~19k entries and takes three or four
    minutes, so it prints progress.

    Each file's object identity (the LFS sha256, or the blob id for a non-LFS
    file) is recorded with its size, which lets ``refresh_data.py`` tell which
    files changed between two listings without crawling again.
    """
    api = HfApi()
    print(f"resolving {REPO}@{revision} ...", flush=True)
    # From the Hub even when the clone has it, so the commit is one on the Hub.
    commit_sha = api.dataset_info(REPO, revision=revision).sha
    print(f"source commit: {commit_sha}", flush=True)
    rows = listing_from_git(commit_sha)
    if rows is None:
        print(
            f"{DOCS.name} does not have it, so listing the repository on the Hub "
            "(no file contents are downloaded) ...",
            flush=True,
        )
        rows = listing_from_hub(api, commit_sha)
    # Sorted, so the file does not reorder between the two sources.
    rows.sort(key=lambda row: row["path"])

    files = [r for r in rows if r["type"] == "RepoFile"]
    total = sum(r["size"] or 0 for r in files)
    print(f"{len(files):,} files, {total / 1e12:.2f} TB", flush=True)
    return commit_sha, rows


def save(rows: list[dict], commit_sha: str, revision: str) -> None:
    """Write the listing, then the revision it is of, in that order: a recorded revision
    always comes with its listing."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(OUT, json.dumps(rows))
    record = {
        "repo_id": REPO,
        "repo_type": "dataset",
        "requested_revision": revision,
        "commit_sha": commit_sha,
    }
    write_atomically(PROVENANCE_OUT, json.dumps(record, indent=2) + "\n")
    print(f"listing of {commit_sha[:12]} -> {OUT}", flush=True)


def listing_from_hub(api, commit_sha):
    rows = []
    start = time.time()
    for entry in api.list_repo_tree(
        REPO, repo_type="dataset", revision=commit_sha, recursive=True, expand=True
    ):
        row = {"path": entry.path, "type": type(entry).__name__}
        size = getattr(entry, "size", None)
        lfs = getattr(entry, "lfs", None)
        row["size"] = lfs.size if lfs is not None else size
        row["lfs"] = lfs is not None
        row["identity"] = lfs.sha256 if lfs is not None else getattr(entry, "blob_id", None)
        rows.append(row)
        if len(rows) % 1000 == 0:
            print(f"  {len(rows):,} entries  ({time.time() - start:.0f}s)", flush=True)
    return rows


def listing_from_git(commit_sha):
    """The same listing from the clone's git, or None if it lacks the commit.

    Git holds an LFS file as a small pointer blob that names the sha256 and size of
    its content, which is what the Hub reports for it.
    """
    git = ["git", "-C", str(DOCS)]
    if subprocess.run(
        [*git, "cat-file", "-e", f"{commit_sha}^{{commit}}"], capture_output=True, check=False
    ).returncode:
        return None
    tree = subprocess.run(
        [*git, "ls-tree", "-r", "-t", "-l", "-z", commit_sha],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows, small = [], collections.defaultdict(list)
    for line in filter(None, tree.split("\0")):
        meta, path = line.split("\t", 1)
        _, kind, blob, size = meta.split()
        if kind == "tree":
            rows.append(
                {"path": path, "type": "RepoFolder", "size": None, "lfs": False, "identity": None}
            )
        else:
            rows.append(
                {
                    "path": path,
                    "type": "RepoFile",
                    "size": int(size),
                    "lfs": False,
                    "identity": blob,
                }
            )
            if int(size) < 1024:  # a pointer is about 130 bytes; identical files share one
                small[blob].append(rows[-1])

    # One ``<blob> blob <size>`` line and the content for each blob asked for, in order.
    asked = "".join(blob + "\n" for blob in small).encode()
    out = subprocess.run(
        [*git, "cat-file", "--batch"], input=asked, capture_output=True, check=True
    ).stdout
    at = 0
    for blob, same in small.items():
        end = out.index(b"\n", at)
        size = int(out[at:end].split()[2])
        content, at = out[end + 1 : end + 1 + size], end + 2 + size
        if content.startswith(b"version https://git-lfs"):
            pointer = dict(line.split(" ", 1) for line in content.decode().splitlines())
            for row in same:
                row.update(
                    lfs=True,
                    size=int(pointer["size"]),
                    identity=pointer["oid"].removeprefix("sha256:"),
                )
    print(f"listed {len(rows):,} entries from {DOCS.name}'s git", flush=True)
    return rows


if __name__ == "__main__":
    raise SystemExit("fetch_tree.py is a step of refresh_data.py; run that instead.")
