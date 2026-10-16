"""Refresh the cached scan of the dataset.

Re-lists ``nvidia/Open-H-RF``, records the revision it listed, and streams the
HDF5 metadata for every file that needs it. ``site/update.py`` runs it.

The tip of the repo is checked first, and a repo that has not moved ends the
refresh in a second. A new revision rarely rewrites the whole dataset, so the
HDF5 objects at the old and new revisions are compared by their LFS sha256 and
only the files whose content changed are scanned again (a full rescan takes
about 80 minutes).

    python refresh_data.py              # bring the cache up to date with main
    python refresh_data.py --full       # rescan every file from scratch
"""

from __future__ import annotations

import argparse
import json
import shutil
import time

import fetch_tree
import scan_files
from huggingface_hub import HfApi, RepoFile

SCAN = scan_files.OUT


def recorded_revision() -> str | None:
    """The ``nvidia/Open-H-RF`` commit the cached scan was taken from."""
    if not fetch_tree.PROVENANCE_OUT.exists():
        return None
    return json.loads(fetch_tree.PROVENANCE_OUT.read_text()).get("commit_sha")


def manifest(rows: list[dict]) -> dict[str, str] | None:
    """path -> immutable object identity of each HDF5 file in a listing, or None for a
    listing too old to carry identities."""
    found = {}
    for row in rows:
        if row.get("type") != "RepoFile" or not row["path"].endswith((".hdf5", ".h5")):
            continue
        if row.get("identity") is None:
            return None
        found[row["path"]] = row["identity"]
    return found


def hdf5_manifest(revision: str) -> dict[str, str]:
    """The same from a crawl of the repo at ``revision``, for when the cached listing
    cannot give it. Prints progress; the crawl takes about a minute."""
    print(f"  listing HDF5 objects at {revision[:12]} ...", flush=True)
    found = {}
    seen = 0
    start = time.time()
    for entry in HfApi().list_repo_tree(
        fetch_tree.REPO, repo_type="dataset", revision=revision, recursive=True, expand=True
    ):
        seen += 1
        if seen % 5000 == 0:
            print(f"    {seen:,} entries  ({time.time() - start:.0f}s)", flush=True)
        if not isinstance(entry, RepoFile) or not entry.path.endswith((".hdf5", ".h5")):
            continue
        found[entry.path] = entry.lfs.sha256 if entry.lfs is not None else entry.blob_id
    print(f"    {len(found):,} HDF5 objects  ({time.time() - start:.0f}s)", flush=True)
    return found


def prune_changed(old: dict[str, str], new: dict[str, str]) -> int:
    """Drop the cached records whose HDF5 object changed between two listings.

    A record read from identical bytes is still good, so a file is kept when its
    LFS sha256 (or blob id, for a non-LFS file) is the same. Returns how many were
    dropped; ``scan_files.scan`` fills those back in.
    """
    still_valid = {path for path, identity in new.items() if old.get(path) == identity}

    found = scan_files.records()
    kept = [rec for path, rec in found.items() if path in still_valid]
    scan_files.save(kept)
    dropped = len(found) - len(kept)
    print(f"{len(kept):,} cached records still valid, {dropped:,} to rescan", flush=True)
    return dropped


def archive_scan() -> None:
    """Keep the previous scan as ``files.stale`` instead of deleting it."""
    if not SCAN.exists():
        return
    stale = SCAN.with_name("files.stale")
    shutil.rmtree(stale, ignore_errors=True)
    SCAN.replace(stale)
    print(f"previous scan moved to {stale.name}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--revision",
        default="main",
        help="Dataset revision to refresh to (default: the tip of main).",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Parallel scan processes. Above ~8 the Hub rate-limits and "
        "net throughput drops (default: 8).",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Scan at most this many files (for a smoke test).",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="Rescan every file, keeping nothing from the cached scan.",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Carry on scanning at the recorded revision without re-listing the "
        "repo, after an interrupted or failed scan.",
    )
    args = ap.parse_args()

    previous = recorded_revision()

    if args.resume:
        if previous is None:
            raise SystemExit(
                "Nothing to resume: no revision is recorded, so there is no scan in "
                "progress.\nRun without --resume."
            )
        if args.full:
            raise SystemExit("--resume and --full contradict each other.")
        print(f"resuming the scan at {previous}", flush=True)
        scan_files.scan(previous, workers=args.workers, limit=args.limit)
        print(f"\ncache now at {previous}")
        return

    # A scan of unknown revision cannot be compared with any listing, so refuse
    # before any network work.
    if SCAN.exists() and previous is None and not args.full:
        raise SystemExit(
            "data/files/ was scanned at an unknown revision, so it cannot be "
            "tied to any commit.\n"
            "Re-run with --full to rescan from scratch (~80 min, resumable; the old "
            "scan is kept as data/files.stale)."
        )

    print(f"refreshing the cached scan of {fetch_tree.REPO}", flush=True)
    if previous:
        print(f"cache is at {previous}", flush=True)

    # If the repo has not moved, no HDF5 object has changed: skip the re-listing,
    # which would only confirm every cached record, and just fill in whatever an
    # interrupted run left unscanned.
    if previous and not args.full and fetch_tree.OUT.exists():
        try:
            tip = HfApi().dataset_info(fetch_tree.REPO, revision=args.revision).sha
        except Exception as exc:  # noqa: BLE001 - an unreachable Hub re-lists as before
            print(
                f"could not reach the Hub to check for a newer revision "
                f"({type(exc).__name__}: {exc}); re-listing.",
                flush=True,
            )
        else:
            if tip == previous:
                print(
                    f"{args.revision} is still {previous[:12]}; nothing on the Hub "
                    "has changed, so the re-listing is skipped.",
                    flush=True,
                )
                if not scan_files.scan(previous, workers=args.workers, limit=args.limit):
                    print("cache is complete and current; nothing to do.")
                print(f"\ncache now at {previous}")
                return
            print(f"remote {args.revision} is at {tip}", flush=True)

    revision, rows = fetch_tree.fetch_tree(args.revision)

    if args.full:
        archive_scan()
    elif previous and previous != revision:
        print(f"comparing HDF5 objects {previous[:12]} -> {revision[:12]}", flush=True)
        # The cached listing is the cheap side of the comparison; it is of ``previous``
        # until fetch_tree.save below replaces it.
        old = manifest(json.loads(fetch_tree.OUT.read_text())) if fetch_tree.OUT.exists() else None
        prune_changed(old if old is not None else hdf5_manifest(previous), manifest(rows))
    else:
        print("cache already at this revision; filling in anything unscanned.", flush=True)
    # Recorded only now. Once the new revision is recorded, a run that finds main unchanged
    # skips the comparison, so an interrupted comparison must leave the old one recorded.
    fetch_tree.save(rows, revision, args.revision)

    scan_files.scan(revision, workers=args.workers, limit=args.limit)
    print(f"\ncache now at {revision}")


if __name__ == "__main__":
    main()
