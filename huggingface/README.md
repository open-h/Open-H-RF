# `huggingface/`: the dataset's documents

`Open-H-RF/` is a clone of
[`nvidia/Open-H-RF`](https://huggingface.co/datasets/nvidia/Open-H-RF), the
dataset repo on the Hugging Face Hub, without its data. It is git-ignored:
`setup.sh` creates it and moves it.

Everything that reads the dataset documents (chiefly `stats/` and `site/`)
reads them from here (`DOCS` in `site/cards.py` and `stats/fetch_tree.py`).

## Why a sparse clone

The dataset repo tracks ~19,400 HDF5 files, about 39 TB, in git-LFS. A plain
`git clone` with git-lfs installed would try to download all of it. So
`setup.sh` clones with `GIT_LFS_SKIP_SMUDGE=1`, replaces the LFS filters in
the clone's config with ones that skip the download, and applies a `--no-cone` sparse checkout that leaves the
HDF5 files, videos and images out of the working tree.

That leaves about 125 files and a few MB: the READMEs, the pipeline YAMLs and
the CSVs. Git history still knows about every
HDF5 file (the LFS pointers are ordinary blobs), so `git log` and `git ls-tree`
see the whole dataset; only the working tree is trimmed.

It is not a submodule because git would check a submodule out by itself
(`git clone --recurse-submodules`, `git pull` with `submodule.recurse`), without
these guards.

## Setup

```bash
./huggingface/setup.sh              # check out the revision the site shows
./huggingface/setup.sh --update     # move it to the Hub's main
```

The revision the site shows is the one the scan in `stats/data/` was taken at,
recorded in `stats/data/source_revision.json`. `site/update.py` runs
`setup.sh --update` and brings the scan, the cards and the website along (see
`site/README.md`); committing `stats/data` records the new revision.

If the directory is missing or empty, run `setup.sh`.
