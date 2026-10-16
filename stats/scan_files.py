"""Stream HDF5 metadata for every file in the dataset.

Opens each ``.hdf5`` over HTTP range requests and records its structure without
downloading the channel data (a few hundred kB of header and small scan arrays
per file, against payloads that run to tens of GB).

Uses a process pool: h5py serialises HDF5 calls behind one global lock, so
threads blocking on network reads inside it would not overlap.

Resumable: paths already in ``data/files/`` are skipped, so an interrupted run
can be relaunched. Only a bounded window of calls is queued, an interrupt drops
that queue, and the workers die with this process (see ``_die_with_parent``).

Stored per dataset: ``data/files/<dataset>.jsonl`` has a line per HDF5 file with
only what that file does not share with the rest of its folder, under a line with
what they share (see ``save``). Files side by side hold nearly the same, so this
is a tenth of the size of a whole record per line, and far from GitHub's 100 MB
limit for a file.

The scan streams from the revision ``fetch_tree.py`` recorded, so a push to the
Hub during an 80-minute scan cannot leave the output straddling two releases.

A step of ``refresh_data.py``.
"""

from __future__ import annotations

import collections
import json
import multiprocessing
import os
import posixpath
import signal
import sys
import time
import warnings
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import ExitStack
from itertools import groupby, islice
from pathlib import Path

HERE = Path(__file__).parent
REPO = "nvidia/Open-H-RF"
TREE = HERE / "data" / "tree.json"
OUT = HERE / "data" / "files"
ABORT_AFTER = 20  # consecutive failures from the start that mean "stop, it's the setup"


def _die_with_parent():
    """Ask the kernel to kill this worker when the parent dies.

    A worker whose parent is gone blocks on its queue forever, at no CPU cost,
    until someone finds it in ``ps``; a ``kill -9`` of the parent gives it no
    chance to clean up. Linux only; an orderly shutdown stops the workers the
    ordinary way.
    """
    if sys.platform != "linux":
        return
    try:
        import ctypes

        PR_SET_PDEATHSIG = 1
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGKILL)
    except Exception:  # noqa: BLE001 - no prctl is not a reason to fail the scan
        pass


def _init_worker():
    """Silence per-process import noise once, in the worker."""
    warnings.filterwarnings("ignore")
    _die_with_parent()
    sys.path.insert(0, str(HERE))
    os.environ.setdefault("ZEA_DISABLE_CACHE", "1")


def scan_one(path, revision):
    import zea
    from extract import extract

    t0 = time.time()
    try:
        # The revision is a keyword, not part of the path: zea takes
        # ``hf://org/repo/subpath`` and adds the ``datasets/`` prefix itself, so
        # spelling either of those into the URL silently addresses a repo that
        # does not exist.
        with zea.File(
            f"hf://{REPO}/{path}",
            revision=revision,
            validate=False,
            progress=False,
            cache=False,
        ) as f:
            rec = extract(f, path)
    except Exception as exc:  # noqa: BLE001 - record the failure and carry on
        rec = {
            "path": path,
            "subdataset": path.split("/")[0],
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }
    rec["scan_seconds"] = round(time.time() - t0, 2)
    return rec


def hdf5_paths(tree=TREE):
    """Every HDF5 path in the cached file listing."""
    rows = json.loads(tree.read_text())
    return [
        r["path"] for r in rows if r["type"] == "RepoFile" and r["path"].endswith((".hdf5", ".h5"))
    ]


def _flatten(rec):
    """A record as one flat dict: ``field`` and ``/key`` for the file, ``N.field`` and
    ``N./key`` for its track N, where a key is an HDF5 dataset listed in ``keys``."""
    flat = {}
    for name, value in rec.items():
        if name == "keys":
            flat.update({f"/{key}": v for key, v in value.items()})
        elif name == "tracks":
            for i, track in enumerate(value):
                flat.update({f"{i}.{k}": v for k, v in _flatten(track).items()})
        else:
            flat[name] = value
    return flat


def _unflatten(flat):
    rec = {"keys": {}, "tracks": []}
    for name, value in flat.items():
        obj = rec
        track, dot, rest = name.partition(".")
        if dot and track.isdigit():
            i = int(track)
            rec["tracks"] += [{"keys": {}} for _ in range(i + 1 - len(rec["tracks"]))]
            obj, name = rec["tracks"][i], rest
        if name.startswith("/"):
            obj["keys"][name[1:]] = value
        else:
            obj[name] = value
    return rec


def _line(row):
    return json.dumps(row, default=str, separators=(",", ":")) + "\n"


def _canon(value):
    return json.dumps(value, default=str, sort_keys=True)


def write_atomically(path, text):
    """Replace a file in one step, so that an interrupted write leaves the old one."""
    part = path.with_name(path.name + ".part")
    part.write_text(text)
    os.replace(part, path)


def records(output=OUT):
    """Every record in the scan, by path; a path scanned twice keeps its later record."""
    found = {}
    for shard in sorted(output.glob("*.jsonl")):
        shared = {}
        for line in shard.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:  # a torn last line is scanned again
                continue
            if "shared" in row:
                shared = row["shared"]
            else:
                rec = _unflatten({**shared, **row})
                found[rec["path"]] = rec
    return found


def save(recs, output=OUT):
    """Write the scan as one file per dataset, a folder at a time: a line with the fields
    that all of the folder's files share, ``{"shared": {...}}``, then a line per file with
    the rest. A file's record is its line and the shared line above it, flattened as
    ``_flatten`` does. The scan appends whole records under an empty shared line."""
    datasets = collections.defaultdict(list)
    for rec in recs:
        # The path first and the rest sorted, so an unchanged file writes the same line.
        row = sorted(_flatten(rec).items(), key=lambda kv: (kv[0] != "path", kv[0]))
        datasets[rec["path"].split("/")[0]].append(dict(row))
    output.mkdir(parents=True, exist_ok=True)
    for shard in output.glob("*.jsonl"):
        if shard.stem not in datasets:
            shard.unlink()

    def folder(row):
        # A failed file's record holds other fields, so it goes in a group of its own.
        return posixpath.dirname(row["path"]), "error" in row

    for name, rows in datasets.items():
        lines = []
        rows.sort(key=lambda row: (folder(row), row["path"]))
        for _, group in groupby(rows, folder):
            group = list(group)
            common = {k: _canon(v) for k, v in group[0].items() if k != "path"}
            for row in group[1:]:
                common = {k: c for k, c in common.items() if k in row and _canon(row[k]) == c}
            lines.append({"shared": {k: group[0][k] for k in common}})
            lines += [{k: v for k, v in row.items() if k not in common} for row in group]
        write_atomically(output / f"{name}.jsonl", "".join(map(_line, lines)))


def already_scanned(output=OUT):
    """The paths already scanned successfully, so a rerun can resume.

    Failed records are dropped from the file: a failure is usually transient (a
    network blip, or an environment that cannot open the files at all), and
    remembering it would make the rerun that fixes the cause skip every file it
    could not read the first time. An unreadable file costs one retry per run.
    """
    if not output.exists():
        return set()

    found = records(output)
    good = [rec for rec in found.values() if not rec.get("error")]
    if len(good) < len(found):
        print(
            f"dropped {len(found) - len(good):,} failed records; they will be scanned again",
            flush=True,
        )
    # Also folds in whatever an interrupted run appended.
    save(good, output)
    return {rec["path"] for rec in good}


def scan(revision, workers=8, limit=None, output=OUT):
    """Stream HDF5 metadata for every file not yet in ``output``.

    One scan at a time: ``save`` replaces the shards that another one would be appending to.
    """
    paths = hdf5_paths()
    done = already_scanned(output)
    todo = [p for p in paths if p not in done]
    if limit:
        todo = todo[:limit]
    print(f"{len(paths)} files total, {len(done)} already scanned, {len(todo)} to go", flush=True)
    if not todo:
        return 0

    output.mkdir(parents=True, exist_ok=True)
    start = time.time()
    n_done = n_err = 0
    queued = iter(todo)
    in_flight = {}
    # Enough queued to keep every worker busy across a slow file. Submitting all
    # 19k up front would make a Ctrl+C wait while ``shutdown`` drains the queue.
    window = workers * 4

    pool = ProcessPoolExecutor(max_workers=workers, initializer=_init_worker)
    try:
        with ExitStack() as stack:
            shards = {}
            for path in islice(queued, window):
                in_flight[pool.submit(scan_one, path, revision)] = path
            while in_flight:
                finished, _ = wait(in_flight, return_when=FIRST_COMPLETED)
                for future in finished:
                    del in_flight[future]
                    # Top the window back up before handling the result, so the
                    # workers are never idle while this process writes a line.
                    for path in islice(queued, 1):
                        in_flight[pool.submit(scan_one, path, revision)] = path

                    rec = future.result()
                    name = rec["path"].split("/")[0]
                    if name not in shards:
                        # Line buffered, so an interrupted run keeps every record
                        # already written.
                        shard = (output / f"{name}.jsonl").open("a", buffering=1)
                        shards[name] = stack.enter_context(shard)
                        shards[name].write(_line({"shared": {}}))
                    shards[name].write(_line(_flatten(rec)))
                    n_done += 1
                    n_err += "error" in rec
                    # Nothing readable in the first batch means the environment
                    # cannot open these files at all (a broken h5py or zea, no
                    # credentials, no network). Stop now instead of after 40 minutes.
                    if n_done == ABORT_AFTER and n_err == n_done:
                        raise SystemExit(
                            f"\nAborting: all {n_done} files attempted so far failed, "
                            f"which points at the environment. Last error:\n\n"
                            f"    {rec['error']}\n\n"
                            "Fix the cause and re-run; failed records are scanned again."
                        )
                    if n_done % 50 == 0:
                        rate = n_done / (time.time() - start)
                        eta = (len(todo) - n_done) / rate / 60
                        print(
                            f"{n_done}/{len(todo)}  {rate:.2f} files/s  "
                            f"eta {eta:.1f} min  errors {n_err}",
                            flush=True,
                        )
    finally:
        # Not the ``with`` form: ``shutdown(wait=True)`` would drain every queued
        # call before returning.
        pool.shutdown(wait=False, cancel_futures=True)
        # The interpreter joins the workers on exit, which would block on whatever
        # files are mid-stream. Their results are discarded either way, and an
        # unfinished path is just rescanned next run. On the ordinary path the
        # workers are idle by here.
        for child in multiprocessing.active_children():
            child.kill()

    save(records(output).values(), output)
    print(f"done: {n_done} scanned, {n_err} errors, {(time.time() - start) / 60:.1f} min")
    return n_done


if __name__ == "__main__":
    raise SystemExit("scan_files.py is a step of refresh_data.py; run that instead.")
