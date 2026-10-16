# SPDX-License-Identifier: Apache-2.0
"""Display the computed reference maps as a PNG montage.

Reads the reference maps from `custom/computed_references/` in the zea HDF5 file
(`mvi`, `velocity_radial_avg` / `_min` / `_max`, `tube_mask`, plus the shared
`coordinates`) and renders, for each map, two orthogonal maximum-intensity
projections (x-z and y-z) on the true Cartesian geometry.

    uv run --project /path/to/Open-H-RF python display_references.py
"""

import argparse
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from zea import File

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus; override with --input.
DEFAULT_INPUT = "hf://nvidia/Open-H-RF/resolvestroke/phantom_flow/phantom_flow.hdf5"

# name, colormap, contrast limits (None = auto), signed (diverging max-|.| MIP)
# Columns left -> right; mask first.
MAPS = [
    ("tube_mask", None, (0, 2), False),
    ("mvi", "magma", None, False),
    ("velocity_radial_avg", "bwr", (-0.76, 0.76), True),
    ("velocity_radial_min", "bwr", (-0.76, 0.76), True),
    ("velocity_radial_max", "bwr", (-0.76, 0.76), True),
]
TUBE_CMAP = ListedColormap(["#101010", "#00c8ff", "#ffb000"])  # 0 bg, 1 = 4mm, 2 = 2mm


def mip(vol, axis, signed):
    """Maximum-intensity projection. Signed maps keep the value with the largest |.|."""
    if signed:
        score = np.where(np.isfinite(vol), np.abs(vol), -1.0)
        idx = np.expand_dims(np.argmax(score, axis=axis), axis)
        return np.take_along_axis(vol, idx, axis).squeeze(axis)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN columns -> NaN
        return np.nanmax(vol, axis=axis)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=DEFAULT_INPUT, help="zea HDF5 (hf:// or local path)")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    out = args.output or Path("phantom_flow_references_montage.png")

    with File(args.input) as f:
        # file.dataset(key) is zea's concurrent-read path (file[key] would read serially).
        ref = "custom/computed_references"
        coords = np.asarray(f.dataset(f"{ref}/coordinates")[...])  # (nz, ny, nx, 3) = [x, y, z] m
        data = {
            name: np.asarray(f.dataset(f"{ref}/{name}")[...]).astype(np.float32)
            for name, *_ in MAPS
        }

    x_mm = coords[0, 0, :, 0] * 1e3
    y_mm = coords[0, :, 0, 1] * 1e3
    z_mm = coords[:, 0, 0, 2] * 1e3
    ext_xz = [x_mm.min(), x_mm.max(), z_mm.max(), z_mm.min()]  # project out y
    ext_yz = [y_mm.min(), y_mm.max(), z_mm.max(), z_mm.min()]  # project out x

    # 2 rows (x-z / y-z MIP) x N columns (maps), landscape
    fig, axes = plt.subplots(2, len(MAPS), figsize=(3.3 * len(MAPS), 8.4), constrained_layout=True)
    for c, (name, cmap, clim, signed) in enumerate(MAPS):
        vol = data[name]
        cm = TUBE_CMAP.copy() if name == "tube_mask" else plt.get_cmap(cmap).copy()
        cm.set_bad("#101010")
        if clim is None:  # auto from positive finite values
            fin = vol[np.isfinite(vol)]
            fin = fin[fin > 0]
            vmin, vmax = (0.0, float(np.percentile(fin, 99))) if fin.size else (0.0, 1.0)
        else:
            vmin, vmax = clim
        rows = [
            (mip(vol, 1, signed), ext_xz, "x [mm]"),  # row 0: x-z (project out y)
            (mip(vol, 2, signed), ext_yz, "y [mm]"),
        ]  # row 1: y-z (project out x)
        for r, (img, ext, xlab) in enumerate(rows):
            ax = axes[r, c]
            im = ax.imshow(img, extent=ext, cmap=cm, vmin=vmin, vmax=vmax, aspect="equal")
            ax.set_xlabel(xlab)
        axes[0, c].set_title(name, fontsize=10)
        label = "label" if name == "tube_mask" else "value"
        fig.colorbar(
            im,
            ax=[axes[0, c], axes[1, c]],
            location="bottom",
            fraction=0.05,
            pad=0.02,
            label=label,
        )
    axes[0, 0].set_ylabel("x-z MIP\nz [mm]")
    axes[1, 0].set_ylabel("y-z MIP\nz [mm]")

    fig.suptitle(
        f"Computed reference maps — {Path(args.input).name}", fontsize=13, fontweight="bold"
    )
    fig.savefig(str(out), dpi=130)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
