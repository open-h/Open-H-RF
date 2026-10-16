#!/usr/bin/env bash
# Clone / refresh nvidia/Open-H-RF into huggingface/Open-H-RF without pulling its
# ~39 TB of LFS payload.
#
#   ./huggingface/setup.sh             check it out at the revision the site shows
#   ./huggingface/setup.sh --update    move it to the Hub's main
#
# The clone is git-ignored and not a submodule, so no git command run in this
# repo (`git clone --recurse-submodules`, `git pull` with submodule.recurse, ...)
# can start a multi-terabyte download. Populate it with this script only. The
# revision the site shows is the one the scan in
# stats/data/ was taken at (stats/data/source_revision.json).
set -euo pipefail

SUB="huggingface/Open-H-RF"
URL="https://huggingface.co/datasets/nvidia/Open-H-RF"
RECORDED="stats/data/source_revision.json"
ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
cd "$ROOT"

# Never materialise LFS content, even if git-lfs is installed.
export GIT_LFS_SKIP_SMUDGE=1

case "${1:-}" in
  "") UPDATE=0 ;;
  --update) UPDATE=1 ;;
  *) echo "usage: $0 [--update]" >&2; exit 2 ;;
esac

# Files we never want in the working tree. Everything the Hub stores in LFS is
# one of these; the docs (README.md, pipeline*.yaml, *.csv) are plain git blobs
# and stay.
SPARSE_PATTERNS=$'/*\n!*.hdf5\n!*.h5\n!*.mp4\n!*.png\n!*.gif\n!*.jpg\n!*.jpeg\n!*.webp\n!*.npy\n!*.npz\n!*.zip\n!*.mat\n'

configure_repo() {
  # Make LFS a no-op inside the clone. Set only when git-lfs is installed: git
  # treats a process filter it cannot execute as fatal, down to a plain
  # `git status`. Without git-lfs the pointer files are checked out verbatim
  # anyway. Re-run this script after installing git-lfs.
  if command -v git-lfs >/dev/null 2>&1; then
    git -C "$SUB" config filter.lfs.smudge "git-lfs smudge --skip -- %f"
    git -C "$SUB" config filter.lfs.process "git-lfs filter-process --skip"
    git -C "$SUB" config filter.lfs.clean "git-lfs clean -- %f"
    git -C "$SUB" config filter.lfs.required false
  else
    git -C "$SUB" config --unset-all filter.lfs.smudge || true
    git -C "$SUB" config --unset-all filter.lfs.process || true
    git -C "$SUB" config --unset-all filter.lfs.clean || true
  fi
  git -C "$SUB" config lfs.fetchexclude "*"

  git -C "$SUB" sparse-checkout init --no-cone
  printf '%s' "$SPARSE_PATTERNS" \
    > "$(git -C "$SUB" rev-parse --path-format=absolute --git-path info/sparse-checkout)"
  git -C "$SUB" sparse-checkout reapply
}

FRESH=0
if [[ ! -e "$SUB/.git" ]]; then
  echo "==> cloning $URL into $SUB (documents only, no LFS payload)"
  git clone --no-checkout "$URL" "$SUB"
  FRESH=1
fi

configure_repo

if (( UPDATE )); then
  echo "==> fetching the Hub's main"
  git -C "$SUB" fetch origin main
  TARGET=origin/main
else
  TARGET="$(sed -n 's/.*"commit_sha": *"\([0-9a-f]*\)".*/\1/p' "$RECORDED" 2>/dev/null || true)"
  if [[ -z "$TARGET" ]]; then
    echo "==> $RECORDED records no revision; checking out the Hub's main"
    TARGET=origin/main
  elif ! git -C "$SUB" cat-file -e "$TARGET^{commit}" 2>/dev/null; then
    echo "==> fetching the Hub's main for $TARGET"
    git -C "$SUB" fetch origin main
  fi
fi

# On a branch, which site/preview.py merges off and returns to.
if (( FRESH )); then
  # A --no-checkout clone has no index yet; -f fills it in.
  git -C "$SUB" checkout -q -f -B main "$TARGET"
else
  git -C "$SUB" checkout -q -B main "$TARGET"
fi

echo "==> $SUB @ $(git -C "$SUB" rev-parse --short HEAD) ($(find "$SUB" -path "$SUB/.git" -prune -o -type f -print | wc -l) files, $(du -sh --apparent-size "$SUB" | cut -f1))"
