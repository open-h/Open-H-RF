"""Per-file metadata extraction for the Open-H-RF dataset.

Everything here reads HDF5 metadata plus the scan arrays (focus distances, delays,
apodizations), so a file is characterised without reading the (often multi-GB)
``raw_data`` payload.
"""

from __future__ import annotations

import h5py
import numpy as np

# Above this many chunks, get_storage_size() costs more than the number is
# worth (it walks the whole chunk index over the network).
MAX_CHUNKS_FOR_STORAGE_SIZE = 20_000

# Scalar strings are kept up to this many characters; some files store whole
# documents in one, such as a 4 kB NRRD header.
MAX_TEXT = 200

# HDF5 filter ids we expect to see on zea data.
FILTER_NAMES = {
    "32001": "blosc",
    "32015": "zstd",
    "32004": "lz4",
    "307": "bzip2",
    "1": "gzip",
    "2": "shuffle",
    "32008": "bitshuffle",
}


def _scalar(group, key):
    """Read a scalar dataset, returning a plain Python value (or None)."""
    ds = group.get(key)
    if ds is None or not isinstance(ds, h5py.Dataset):
        return None
    try:
        val = ds[()]
    except Exception:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", "replace")
    if isinstance(val, np.generic):
        val = val.item()
    if isinstance(val, np.ndarray):
        if val.size == 0:
            return None
        val = val.reshape(-1)[0]
        if isinstance(val, bytes):
            return val.decode("utf-8", "replace")
    return val


def _str_or_array(group, key):
    """Read a field that may be a scalar string or a per-frame string array."""
    ds = group.get(key)
    if ds is None or not isinstance(ds, h5py.Dataset):
        return None
    try:
        val = ds[()]
    except Exception:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", "replace")
    if isinstance(val, np.ndarray) and val.size:
        first = val.reshape(-1)[0]
        return first.decode("utf-8", "replace") if isinstance(first, bytes) else str(first)
    return str(val) if val is not None else None


def _filters(ds):
    """The filter names of a dataset."""
    out = []
    for fid, _ in getattr(ds, "_filters", {}).items():
        out.append(FILTER_NAMES.get(str(fid), str(fid)))
    if ds.compression and ds.compression not in out:
        out.append(ds.compression)
    return out


def _datasets(f):
    """Every dataset in the file as ``{path: [dtype, shape]}``; scalars get their
    value too, text cut at ``MAX_TEXT``. Walks the links; ``visititems`` would also read
    each object's attributes, at ten times the range requests.
    """
    found = {}

    def visit(name, link):
        obj = f[name]
        if isinstance(obj, h5py.Dataset):
            dtype = "string" if h5py.check_string_dtype(obj.dtype) else str(obj.dtype)
            # An empty dataset has no shape at all.
            found[name] = [dtype, list(obj.shape or ())]
            if obj.shape == ():
                value = _scalar(f, name)
                if isinstance(value, str) and len(value) > MAX_TEXT:
                    value = value[:MAX_TEXT] + "…"
                found[name].append(value)

    f.visititems_links(visit)
    return found


def transmit_kinds(focus_distances):
    """Count the transmits of each kind, from their focus distances.

    zea stores ``inf`` (or 0) for plane waves, a positive distance for a focused
    transmit and a negative one for a diverging wave (virtual source behind the
    array). Kinds with no transmits are left out.
    """
    fd = np.asarray(focus_distances, dtype=np.float64).reshape(-1)
    counts = {
        "plane": np.isinf(fd) | (fd == 0),
        "diverging": np.isfinite(fd) & (fd < 0),
        "focused": np.isfinite(fd) & (fd > 0),
    }
    return {kind: int(hits.sum()) for kind, hits in counts.items() if hits.any()}


def classify_transmit(focus_distances):
    """Map focus distances onto a transmit scheme label: the one kind of transmit in
    the track (see ``transmit_kinds``), ``mixed`` when there are several and
    ``unknown`` when there are none."""
    if focus_distances is None:
        return "unknown"
    kinds = transmit_kinds(focus_distances)
    if not kinds:
        return "unknown"
    if len(kinds) > 1:
        return "mixed"
    return next(iter(kinds))


def extract(f, path):
    """Extract a flat metadata record from an open zea/h5py file."""
    rec = {"path": path, "subdataset": path.split("/")[0]}

    attrs = dict(f.attrs)
    for key in ("description", "us_machine", "zea_version", "timestamp", "date"):
        val = attrs.get(key)
        if isinstance(val, bytes):
            val = val.decode("utf-8", "replace")
        if val is not None:
            rec[f"attr_{key}"] = val if isinstance(val, str) else str(val)
    rec["attr_keys"] = sorted(attrs.keys())
    # The whole layout: the keys outside tracks/ here, each track's under the track.
    layout = _datasets(f)
    rec["keys"] = {k: v for k, v in layout.items() if not k.startswith("tracks/")}

    # ---- metadata group -------------------------------------------------
    md = f.get("metadata")
    if md is not None:
        rec["credit"] = _scalar(md, "credit")
        rec["has_text_report"] = "text_report" in md
        rec["has_ecg"] = "ecg" in md
        rec["has_probe_pose"] = "probe_pose" in md
        rec["has_voice_narration"] = "voice_narration" in md
        subj = md.get("subject")
        if subj is not None:
            for key in ("id", "type", "sex", "genetic_strain"):
                rec[f"subject_{key}"] = _scalar(subj, key)
            for key in ("age", "weight", "fat_percentage", "bmi"):
                rec[f"subject_{key}"] = _scalar(subj, key)
        ann = md.get("annotations")
        if ann is not None:
            for key in ("anatomy", "view", "label", "image_quality"):
                rec[f"annot_{key}"] = _str_or_array(ann, key)
            rec["annot_keys"] = sorted(ann.keys())
        rec["metadata_keys"] = sorted(md.keys())

    # ---- probe group ----------------------------------------------------
    pr = f.get("probe")
    if pr is not None:
        rec["probe_name"] = _scalar(pr, "name")
        rec["probe_type"] = _scalar(pr, "type")
        rec["probe_center_frequency"] = _scalar(pr, "probe_center_frequency")
        rec["probe_bandwidth_percent"] = _scalar(pr, "probe_bandwidth_percent")
        rec["element_width"] = _scalar(pr, "element_width")
        rec["element_height"] = _scalar(pr, "element_height")
        geo = pr.get("probe_geometry")
        if isinstance(geo, h5py.Dataset):
            rec["probe_n_el"] = int(geo.shape[0])
            try:
                g = np.asarray(geo[()], dtype=np.float64)
                rec["probe_aperture_x"] = float(np.ptp(g[:, 0]))
                rec["probe_aperture_y"] = float(np.ptp(g[:, 1])) if g.shape[1] > 1 else 0.0
                rec["probe_aperture_z"] = float(np.ptp(g[:, 2])) if g.shape[1] > 2 else 0.0
                # Pitch: median nearest-neighbour spacing along the array order.
                if g.shape[0] > 1:
                    d = np.linalg.norm(np.diff(g, axis=0), axis=1)
                    d = d[d > 0]
                    if d.size:
                        rec["probe_pitch"] = float(np.median(d))
                # 3D (matrix / ring) arrays occupy more than one plane.
                nonzero_axes = int(sum(np.ptp(g[:, i]) > 1e-6 for i in range(g.shape[1])))
                rec["probe_geometry_axes"] = nonzero_axes
            except Exception:
                pass

    rec["has_metrics"] = bool(len(f.get("metrics", {}) or {}))
    rec["has_custom"] = "custom" in f
    rec["has_track_schedule"] = "track_schedule" in f

    # ---- tracks ---------------------------------------------------------
    tracks_grp = f.get("tracks")
    track_names = sorted(tracks_grp.keys()) if tracks_grp is not None else []
    rec["n_tracks"] = len(track_names)
    tracks = []
    for tname in track_names:
        tg = tracks_grp[tname]
        t = {"name": tname, "label": _scalar(tg, "label")}
        t["transmit_only"] = bool(_scalar(tg, "transmit_only") or False)
        prefix = f"tracks/{tname}/"
        t["keys"] = {k[len(prefix) :]: v for k, v in layout.items() if k.startswith(prefix)}

        data = tg.get("data")
        if data is not None:
            t["data_keys"] = sorted(data.keys())
            raw = data.get("raw_data")
            if isinstance(raw, h5py.Dataset):
                t["raw_shape"] = list(raw.shape)
                t["raw_dtype"] = str(raw.dtype)
                t["raw_chunks"] = list(raw.chunks) if raw.chunks else None
                t["raw_filters"] = _filters(raw)
                t["raw_nbytes"] = int(np.prod(raw.shape) * raw.dtype.itemsize)
                # Shape and chunking come free from the object header, but
                # get_storage_size() sums every chunk record in the chunk index:
                # ~30 s over HTTP for a dataset with 160k chunks, and over 15 min
                # for one of 30k whose index is spread through the file. Skip it
                # for heavily chunked datasets, which then have no compression ratio.
                n_chunks = (
                    int(np.prod([-(-a // b) for a, b in zip(raw.shape, raw.chunks)]))
                    if raw.chunks
                    else 1
                )
                t["raw_n_chunks"] = n_chunks
                if n_chunks <= MAX_CHUNKS_FOR_STORAGE_SIZE:
                    try:
                        t["raw_storage_size"] = int(raw.id.get_storage_size())
                    except Exception:
                        t["raw_storage_size"] = None
                else:
                    t["raw_storage_size"] = None

        scan = tg.get("scan")
        if scan is not None:
            t["scan_keys"] = sorted(scan.keys())
            for key in ("sampling_frequency", "sound_speed"):
                t[key] = _scalar(scan, key)
            for key in ("center_frequency", "demodulation_frequency"):
                val = scan.get(key)
                if isinstance(val, h5py.Dataset):
                    arr = np.asarray(val[()], dtype=np.float64).reshape(-1)
                    t[key] = float(arr[0]) if arr.size else None
            t0 = scan.get("t0_delays")
            if isinstance(t0, h5py.Dataset) and len(t0.shape) == 2:
                t["n_tx"] = int(t0.shape[0])
                t["n_el"] = int(t0.shape[1])
            fd = scan.get("focus_distances")
            if isinstance(fd, h5py.Dataset):
                arr = np.asarray(fd[()], dtype=np.float64).reshape(-1)
                t["transmit_scheme"] = classify_transmit(arr)
                t["transmit_kinds"] = transmit_kinds(arr)
                finite = arr[np.isfinite(arr) & (arr != 0)]
                t["focus_distance_median"] = float(np.median(finite)) if finite.size else None
                t["n_focus"] = int(arr.size)
            # Transmit apodization tells plane-wave from synthetic-aperture and
            # reveals coded (Hadamard-style) excitation via negative weights.
            apod = scan.get("tx_apodizations")
            if isinstance(apod, h5py.Dataset) and np.prod(apod.shape) <= 20_000_000:
                try:
                    a = np.asarray(apod[()], dtype=np.float64)
                    active = np.count_nonzero(np.abs(a) > 1e-6, axis=-1)
                    t["tx_active_el_median"] = float(np.median(active))
                    t["tx_active_el_min"] = int(active.min())
                    t["tx_active_el_max"] = int(active.max())
                    t["tx_has_negative_apod"] = bool((a < -1e-6).any())
                    t["tx_aperture_fraction"] = float(np.median(active) / a.shape[-1])
                except Exception:
                    pass

            # Transmit timing: PRF from the transmit-to-transmit interval, frame
            # rate from the total time of one frame's worth of transmits.
            ttnt = scan.get("time_to_next_transmit")
            if isinstance(ttnt, h5py.Dataset) and np.prod(ttnt.shape) <= 20_000_000:
                try:
                    dt = np.asarray(ttnt[()], dtype=np.float64)
                    flat = dt.reshape(-1)
                    flat = flat[np.isfinite(flat) & (flat > 0)]
                    if flat.size:
                        t["prf"] = float(1.0 / np.median(flat))
                    if dt.ndim == 2 and dt.shape[1] > 0:
                        per_frame = np.nansum(dt, axis=1)
                        per_frame = per_frame[np.isfinite(per_frame) & (per_frame > 0)]
                        if per_frame.size:
                            t["frame_rate"] = float(1.0 / np.median(per_frame))
                except Exception:
                    pass

            init = scan.get("initial_times")
            if isinstance(init, h5py.Dataset):
                try:
                    arr = np.asarray(init[()], dtype=np.float64).reshape(-1)
                    if arr.size:
                        t["initial_time_median"] = float(np.median(arr))
                except Exception:
                    pass

            for key in ("polar_angles", "azimuth_angles"):
                ang = scan.get(key)
                if isinstance(ang, h5py.Dataset):
                    arr = np.asarray(ang[()], dtype=np.float64).reshape(-1)
                    if arr.size:
                        t[f"{key}_span"] = float(np.ptp(arr))
                        t[f"{key}_n_unique"] = int(np.unique(np.round(arr, 6)).size)
        tracks.append(t)
    rec["tracks"] = tracks
    return rec
