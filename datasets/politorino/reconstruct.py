# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the politorino dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/politorino

B-mode reconstruction of high-frame-rate fascicle tracking channel data, with
the stored fascicle tracking overlaid: the superficial and deep aponeuroses as
lines, and the fascicle as 10 independent segments.

Tracking is stored at several rates (25, 50 and 125 fps); ``FPS`` selects one
and ``TRACK_INDEX`` picks a sample within it. ``FRAME`` picks which frame of
the acquisition is reconstructed.

Some subjects were recorded mirrored and need a horizontal flip to match the
others; those subjects are listed in ``FLIPPED_SUBJECTS`` below, confirmed by
visual inspection and an automatic metric. The flip is applied to both the
reconstruction and the overlay so the two stay registered.

Requires zea>=0.1.6 (https://github.com/tue-bmd/zea), the library that does the
ultrasound processing here, together with one of its Keras backends (JAX,
PyTorch or TensorFlow). Installation instructions are at
https://zea.readthedocs.io/en/latest/installation.html.

Usage:
    python reconstruct.py
"""

import os

os.environ.setdefault("KERAS_BACKEND", "jax")
os.environ.setdefault("MPLBACKEND", "Agg")

from pathlib import Path

import keras
import matplotlib.pyplot as plt
import numpy as np
import zea
from zea.ops import Beamform, EnvelopeDetect, LogCompress, Normalize

HERE = Path(__file__).parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/politorino/data/PAT02/PAT02_w1.hdf5"
OUT = HERE / "assets" / "PAT02_w1_reconstructed.png"
SAVE_PIPELINE = None  # Optionally write the pipeline to a reusable pipeline.yaml
FRAME = 0
FPS = 50  # tracking rate to overlay: 25, 50 or 125
TRACK_INDEX = 0  # which tracking sample within that rate

# Subjects recorded mirrored, which need a horizontal flip to match the others
# (confirmed by visual inspection + an automatic metric).
FLIPPED_SUBJECTS = {"PAT01", "PAT04", "PAT05"}

# The reconstruction lands this many rows deeper than the stored B-mode: the
# two share a grid but not a time-zero convention. Tracking coordinates are in
# stored-image pixels, so they need the same shift. The value is the peak of
# the vertical cross-correlation between the reconstruction and the stored
# DAS image.
DEPTH_OFFSET_PX = 55


def main():
    zea.init_device()

    subject_id = Path(ZEA_FILE).stem.split("_")[0]
    flip = subject_id in FLIPPED_SUBJECTS
    if flip:
        print(f"Horizontal flip applied (subject {subject_id})")

    with zea.File(str(ZEA_FILE)) as f:
        raw = np.expand_dims(f.data.raw_data[FRAME, :, :, :], 0)

        # The stored image's own coordinate grid defines the imaging FOV. Pin
        # the reconstruction to it so both land on the same pixels, which is
        # what lets the tracking overlay transfer across.
        coords = f.data.image_das.coordinates[FRAME, :, :, :]
        n_rows, n_cols = coords.shape[0], coords.shape[1]
        params = f.load_parameters(
            grid_size_x=n_cols,
            grid_size_z=n_rows,
            xlims=[float(coords[..., 0].min()), float(coords[..., 0].max())],
            zlims=[float(coords[..., 2].min()), float(coords[..., 2].max())],
            n_ch=raw.shape[-1],
            selected_transmits="all",
        )

        def tracking(name):
            return getattr(f.metadata, f"tracking_{FPS}fps_{name}")

        t = np.asarray(tracking("faslen").timestamps)[TRACK_INDEX]
        print(f"Tracking sample {TRACK_INDEX} ({FPS} fps) -> t={t:.4f}s")

        def sample(name):
            return np.asarray(tracking(name).samples)[TRACK_INDEX]

        x_px = sample("x")
        y_px = sample("y")
        super_coef = sample("super_coef")
        deep_coef = sample("deep_coef")
        faslen = sample("faslen")
        alpha = sample("alpha")

    print(f"raw_data: {raw.shape}")

    pipeline = zea.Pipeline(
        operations=[
            Beamform(beamformer="delay_and_sum"),
            EnvelopeDetect(),
            Normalize(),
            LogCompress(),
        ]
    )
    if SAVE_PIPELINE is not None:
        pipeline.to_yaml(str(SAVE_PIPELINE))
        print(f"Saved pipeline recipe to {SAVE_PIPELINE}")

    inputs = pipeline.prepare_parameters(params)
    # keras.ops.convert_to_numpy (not np.array) so the output tensor is pulled
    # off the device regardless of backend -- e.g. PyTorch needs an explicit
    # .cpu(), which np.array would not do.
    bmode = keras.ops.convert_to_numpy(pipeline(data=raw, **inputs)["data"])[0]
    if flip:
        bmode = np.fliplr(bmode)
    print(f"Reconstructed: {bmode.shape}")

    # Tracking is stored in stored-image pixel indices; map it onto the
    # reconstruction's millimetre axes.
    x_mm_min, x_mm_max = params.xlims[0] * 1e3, params.xlims[1] * 1e3
    z_mm_min, z_mm_max = params.zlims[0] * 1e3, params.zlims[1] * 1e3

    def col_to_mm(col):
        col = np.asarray(col, dtype=float)
        if flip:
            col = (n_cols - 1) - col
        return x_mm_min + col * (x_mm_max - x_mm_min) / (n_cols - 1)

    def row_to_mm(row):
        row = np.asarray(row, dtype=float) + DEPTH_OFFSET_PX
        return z_mm_min + row * (z_mm_max - z_mm_min) / (n_rows - 1)

    zea.visualize.set_mpl_style()
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(
        bmode,
        cmap="gray",
        vmin=-60,
        vmax=0,
        extent=[x_mm_min, x_mm_max, z_mm_max, z_mm_min],
        aspect="equal",
    )

    # Aponeuroses are stored as (slope, intercept) of y = slope * x + intercept
    # in pixel space. Evaluate at the image edges, then convert both ends.
    edges_px = np.array([0.0, n_cols - 1.0])
    for coef, color, label in (
        (super_coef, "cyan", "Superficial aponeurosis"),
        (deep_coef, "yellow", "Deep aponeurosis"),
    ):
        ax.plot(
            col_to_mm(edges_px),
            row_to_mm(coef[0] * edges_px + coef[1]),
            "-",
            color=color,
            linewidth=2,
            label=label,
        )

    # Fascicle: each row of x/y is one segment, stored as [start, end].
    xs = x_px.reshape(-1, 2)
    ys = y_px.reshape(-1, 2)
    for i in range(xs.shape[0]):
        ax.plot(
            col_to_mm(xs[i]),
            row_to_mm(ys[i]),
            "o-",
            color="lime",
            markersize=4,
            linewidth=1.5,
            label="Fascicle (segments)" if i == 0 else None,
        )

    title = (
        f"{Path(ZEA_FILE).stem} — B-mode + tracking ({FPS} fps, t={t:.3f}s)\n"
        f"faslen={float(faslen):.1f}  alpha={float(alpha):.2f}"
    )
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Lateral [mm]")
    ax.set_ylabel("Axial depth [mm]")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(OUT), dpi=150, bbox_inches="tight")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
