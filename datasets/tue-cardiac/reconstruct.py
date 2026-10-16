#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the tue-cardiac dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/tue-cardiac

B-mode reconstruction of one track and frame of multi-transmit cardiac channel data.

Each file holds several tracks that vary the transmit encoding -- focused
fundamental and harmonic, wide, plane wave, diverging, Hadamard-coded and
random-coded. Pick one with TRACK and FRAME below; PIPELINE_FOR_TRACK names the
pipeline that goes with each.

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

import matplotlib.pyplot as plt
import numpy as np
import zea
from mpl_toolkits.axes_grid1 import make_axes_locatable
from zea import Config, File, Pipeline

HERE = Path(__file__).resolve().parent
PIPELINE_FOR_TRACK = {
    "focused_fund": "pipeline.yaml",
    "focused_harm": "pipeline_harmonic.yaml",
    "wide_fund": "pipeline.yaml",
    "wide_harm": "pipeline_harmonic.yaml",
    "planewave": "pipeline.yaml",
    "diverging": "pipeline.yaml",
    "hadamard": "pipeline_hadamard.yaml",
    "random": "pipeline_random.yaml",
}
TRACKS = tuple(PIPELINE_FOR_TRACK)

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/tue-cardiac/data/subject-012.hdf5"
TRACK = "focused_fund"  # one of TRACKS; must match CONFIG below
FRAME = 0
CONFIG = "hf://nvidia/Open-H-RF/tue-cardiac/pipelines/pipeline.yaml"
OUT = HERE / "assets" / f"{Path(ZEA_FILE).stem}_{TRACK}_frame-{FRAME:03d}.png"
DEVICE = None  # e.g. cpu, cuda:0, auto:1


def main():
    pipeline_path = CONFIG or HERE / "pipelines" / PIPELINE_FOR_TRACK[TRACK]
    OUT.parent.mkdir(parents=True, exist_ok=True)

    zea.init_device(device=DEVICE, verbose=False)
    config = Config.from_path(str(pipeline_path))
    pipeline = Pipeline.from_config(config)

    with File(str(ZEA_FILE)) as handle:
        labels = list(handle.track_labels)
        if TRACK not in labels:
            raise ValueError(f"track {TRACK!r} not found; available tracks: {labels}")
        track = handle.tracks[labels.index(TRACK)]
        n_frames = int(track.data.raw_data.shape[0])
        if not 0 <= FRAME < n_frames:
            raise ValueError(f"frame {FRAME} outside 0..{n_frames - 1}")
        parameters = track.load_parameters(**config.parameters)
        raw = track.data.raw_data[FRAME : FRAME + 1]

    inputs = pipeline.prepare_parameters(parameters)
    outputs = pipeline(**{pipeline.key: raw}, **inputs)
    image = np.asarray(outputs[pipeline.output_key])[0]
    dynamic_range = tuple(config.parameters.dynamic_range)

    # Scan conversion leaves pixels outside the polar sector undefined. Render
    # those expected out-of-sector values at the display floor.
    image = np.nan_to_num(
        image,
        nan=dynamic_range[0],
        neginf=dynamic_range[0],
        posinf=dynamic_range[1],
    )

    extent = np.asarray(parameters.extent_imshow) * 1e3
    zea.visualize.set_mpl_style()
    figure, axis = plt.subplots(figsize=(6, 6))
    rendered = axis.imshow(
        image,
        extent=extent,
        cmap="gray",
        vmin=dynamic_range[0],
        vmax=dynamic_range[1],
        aspect="equal",
    )
    axis.set_xlabel("Lateral (mm)")
    axis.set_ylabel("Depth (mm)")
    axis.set_title(f"{Path(ZEA_FILE).stem} — {TRACK} — frame {FRAME}")
    cax = make_axes_locatable(axis).append_axes("right", size="5%", pad=0.05)
    figure.colorbar(rendered, cax=cax, label="dB")
    figure.tight_layout()
    figure.savefig(OUT, dpi=150, bbox_inches="tight", metadata={})
    plt.close(figure)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
