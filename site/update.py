"""Update the website to the latest state of the Hub repo.

Run this after merging a pull request into nvidia/Open-H-RF on Hugging Face. It moves
``huggingface/Open-H-RF``, the clone of the Hub repo's documents, to the Hub's main branch,
brings the scan in ``stats/data/`` to the same revision (reading only the HDF5 files that
are new or changed), turns the data cards and the scan into ``site/hub/``, and builds the
site into ``site/_site/`` for a look. Then it prints the commands that publish the update.

From the repository root::

    uv run --extra site python site/update.py          # after a merge on the Hub
    uv run --extra site python site/update.py --full   # after a change to the scan
    uv run --extra site python site/update.py --pr 77 --pr 78   # before those are merged

``--pr N`` shows open pull requests on the site before they are merged: their data cards
and figures, over main (see ``preview.py``). The next update without it goes back to main.

``--full`` reads every HDF5 file again, not only the new or changed ones; needed after a
change to what the scan (``stats/extract.py``) records. If either is
interrupted, run it again without ``--full``: the scan carries on where it stopped.

The statistics are not built while the scan lacks a file: a run that leaves files unread
(the Hub refused or timed out) stops at step 4, and the next run reads them again.
``--allow-partial`` builds the statistics without them instead.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import build
import cards
import corpus
import preview

ROOT = build.SITE.parent


def listed(ids: list[str], limit: int = 10) -> str:
    more = f" and {len(ids) - limit} more" if len(ids) > limit else ""
    return ", ".join(ids[:limit]) + more


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--full", action="store_true", help="rescan every HDF5 file")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="build the statistics without the HDF5 files the scan could not read",
    )
    parser.add_argument(
        "--pr",
        type=int,
        action="append",
        default=[],
        metavar="N",
        help="also show this open pull request (repeat for several)",
    )
    args = parser.parse_args()
    full = args.full

    print("1/5 Data cards: huggingface/Open-H-RF")
    subprocess.run(["./huggingface/setup.sh", "--update"], cwd=ROOT, check=True)
    revision = cards.git("rev-parse", "HEAD").strip()

    print(f"\n2/5 HDF5 files: stats/data at {revision[:10]}")
    refresh = [sys.executable, "stats/refresh_data.py", "--revision", revision]
    refresh += ["--full"] * full
    subprocess.run(refresh, cwd=ROOT, check=True)

    print("\n3/5 Data cards: site/hub/cards.json")
    shown = None
    if args.pr:
        print("  merging, locally, the pull requests")
        # Back to main however it ends, an interrupted merge too.
        try:
            shown = preview.merge(args.pr)
            changes = cards.update(shown)
        finally:
            preview.restore()
    else:
        changes = cards.update()
    for kind, ids in changes.items():
        if ids:
            print(f"  {kind}: {listed(ids)}")

    print("\n4/5 Statistics")
    corpus.main(args.allow_partial)

    print("\n5/5 Website")
    index = build.build(build.SITE / "_site")
    print(f"  {index['dataset_count']} datasets in site/_site")
    new = set(changes["added"] + changes["changed"])
    for record in index["datasets"]:
        if record["id"] in new:
            facets = {f: record[f] for f in build.FACETS + ("institution",)}
            print(f"  {record['id']}: {json.dumps(facets, ensure_ascii=False)}")

    # GitHub warns about a file over 50 MB and refuses one over 100 MB.
    ls = ["git", "ls-files", "--cached", "--others", "--exclude-standard", "stats/data", "site/hub"]
    for path in subprocess.run(ls, cwd=ROOT, capture_output=True, text=True).stdout.splitlines():
        size = (ROOT / path).stat().st_size if (ROOT / path).is_file() else 0
        if size > 50e6:
            print(f"  warning: {path} is {size / 1e6:.0f} MB; GitHub refuses a file over 100 MB")

    title = f"Open-H-RF {revision[:7]}"
    if shown:
        numbers = ", ".join(f"#{p['number']}" for p in shown["pull_requests"])
        title += f" with the open pull requests {numbers}"
        print(f"\nThe site shows {numbers} over main; an update without --pr goes back to main.")
    print(
        "\nNext:"
        "\n  1. Look at the site:  uv run --extra site python site/build.py --serve"
        "\n  2. If a dataset is classified wrongly, add an override to site/catalog.yaml"
        "\n     and look again. A new dataset needs a short name in plots/open_h_rf_datasets.py."
        "\n  3. Commit on a branch and open a pull request; the site deploys once it is merged:"
        "\n       git add stats/data site/hub site/catalog.yaml site/institution_filters.csv \\"
        "\n         plots/open_h_rf_datasets.py site/figures"
        f'\n       git commit -m "Update the website to {title}"'
    )


if __name__ == "__main__":
    main()
