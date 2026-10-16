"""Show open pull requests of the Hub repo on the site before they are merged.

``update.py --pr N`` runs this once the clone is at the Hub's main and the scan is up
to date with it. It merges the pull requests into main locally, ``cards.py`` reads the data
cards as they will be once merged, and the clone goes back on main afterwards.

The merge exists only here, so nothing may depend on its commit: the scan in ``stats/data``,
the revision it records and the explorer's download script all stay at main, which has the
same HDF5 files because a pull request that changes one is refused. Each figure a pull
request adds or changes is downloaded from that pull request's commit, which is on the Hub.
"""

from __future__ import annotations

import os
import subprocess

from huggingface_hub import HfApi

from cards import DOCS, REPO, git

HDF5 = (".hdf5", ".h5")
# What the clone's sparse checkout leaves out (SPARSE_PATTERNS in huggingface/setup.sh):
# these are downloaded from the Hub, so each must come from a commit that is on it.
NOT_CHECKED_OUT = (
    ".hdf5",
    ".h5",
    ".mp4",
    ".png",
    ".gif",
    ".jpg",
    ".jpeg",
    ".webp",
    ".npy",
    ".npz",
    ".zip",
    ".mat",
)


def tree(revision: str) -> dict[str, str]:
    """Every file at a revision, with its blob id."""
    listing = git("ls-tree", "-rz", revision).split("\0")
    return {e.split("\t", 1)[1]: e.split()[2] for e in listing if e}


def changed(old: dict[str, str], new: dict[str, str]) -> list[str]:
    return sorted(p for p in old.keys() | new.keys() if old.get(p) != new.get(p))


def merge(numbers: list[int]) -> dict:
    """Merge the pull requests into the checked-out main, for ``cards.update``.

    Returns the base (main's commit), the pull requests, which of them each added or
    changed file comes from, and the files they removed. Leaves the clone on the merge,
    or partway to it if this fails; the caller puts it back on main with ``restore`` in
    either case.
    """
    # Never materialise LFS content, as huggingface/setup.sh.
    os.environ["GIT_LFS_SKIP_SMUDGE"] = "1"
    api = HfApi()
    base = git("rev-parse", "HEAD").strip()
    base_tree = tree(base)
    pulls = []
    for number in dict.fromkeys(numbers):
        details = api.get_discussion_details(REPO, number, repo_type="dataset")
        if not details.is_pull_request:
            raise SystemExit(f"#{number} is a discussion, not a pull request")
        if details.status == "merged":
            raise SystemExit(f"PR #{number} is merged: main has it, so leave it out")
        if details.status not in ("open", "draft"):
            raise SystemExit(f"PR #{number} is {details.status}")
        git("fetch", "-q", "origin", details.git_reference)
        commit = git("rev-parse", "FETCH_HEAD").strip()
        # Its own changes: from where it branched off main, which may be behind main.
        fork = git("merge-base", base, commit).strip()
        data = [p for p in changed(tree(fork), tree(commit)) if p.endswith(HDF5)]
        if data:
            raise SystemExit(
                f"PR #{number} changes HDF5 files ({', '.join(data[:3])}"
                f"{' ...' if len(data) > 3 else ''}). A preview reads the data at main, "
                "so it cannot show those; wait for the merge."
            )
        pulls.append({"number": number, "title": details.title, "commit": commit})
        print(f"  #{number} {details.title} ({commit[:7]})")

    # Detached, which leaves the main branch at the Hub's main.
    git("checkout", "-q", "--detach")
    merged = subprocess.run(
        [
            "git",
            "-C",
            str(DOCS),
            "-c",
            "user.name=Open-H-RF site preview",
            "-c",
            "user.email=preview@localhost",
            "merge",
            "-q",
            "--no-ff",
            "--no-edit",
            *[p["commit"] for p in pulls],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if merged.returncode:
        conflicts = git("diff", "--name-only", "--diff-filter=U").split()
        detail = f": {', '.join(conflicts)}" if conflicts else f"\n{merged.stdout}{merged.stderr}"
        raise SystemExit(f"The pull requests do not merge cleanly into main{detail}")

    merge_tree = tree("HEAD")
    trees = {p["number"]: tree(p["commit"]) for p in pulls}
    files, removed = {}, []
    for path in changed(base_tree, merge_tree):
        if path not in merge_tree:
            removed.append(path)
            continue
        # A binary file is never merged line by line, so it is the file of exactly one pull
        # request. A text file may be a merge of several, and is read from the checkout.
        source = next((n for n, t in trees.items() if t.get(path) == merge_tree[path]), None)
        if source is not None:
            files[path] = source
        elif path.lower().endswith(NOT_CHECKED_OUT):
            raise SystemExit(f"{path} in the merge is in none of the pull requests")
    return {"base": base, "pull_requests": pulls, "files": files, "removed": removed}


def restore() -> None:
    """Put the clone back on main, where huggingface/setup.sh --update left it."""
    git("reset", "-q", "--hard")
    git("checkout", "-q", "main")
