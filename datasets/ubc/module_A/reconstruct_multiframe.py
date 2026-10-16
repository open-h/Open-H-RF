#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Multi-frame reconstruction for the ubc/module_A dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/ubc/module_A

Reconstructs one temporal sequence -- the frames acquired at a single motor
plane -- with the same pipeline as ``reconstruct.py`` and writes the result as
an animated GIF.

As in ``reconstruct.py``, only zea's logical ``raw_data`` field and the
acquisition parameters are used. The stored reference images and the source
line RF are never loaded.

Usage:
    python reconstruct_multiframe.py
"""

import os

os.environ.setdefault("KERAS_BACKEND", "jax")
os.environ.setdefault("MPLBACKEND", "Agg")

from pathlib import Path

import numpy as np
import zea
from reconstruct import DISPLAY_FLOOR_DB, PARAMETERS, build_pipeline

HERE = Path(__file__).resolve().parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ACQUISITIONS = "hf://nvidia/Open-H-RF/ubc/module_A/acquisitions"
CASE_ID = "1.83"
PLANE = 10
N_FRAMES = 25
OUTPUT = HERE / "results" / f"reconstruct_{CASE_ID}_p{PLANE:02d}_f00-f{N_FRAMES - 1:02d}.gif"
FPS = 5


def sequence_paths():
    """Return the ordered acquisitions for one case and motor plane.

    Every acquisition is named from its case, plane and frame index, so the
    sequence is built rather than listed. That keeps it working when
    ``ACQUISITIONS`` is an ``hf://`` prefix instead of a local directory.
    """
    return [
        f"{ACQUISITIONS}/case_{CASE_ID}/ubc_swave_cirs_{CASE_ID}_p{PLANE:02d}_f{frame:02d}.hdf5"
        for frame in range(N_FRAMES)
    ]


def reconstruct_sequence(paths, pipeline=None):
    """Reconstruct every frame into a stack of scan-converted sectors."""
    zea.init_device()
    pipeline = pipeline or build_pipeline()

    sectors = []
    for index, path in enumerate(paths):
        with zea.File(path) as f:
            parameters = f.load_parameters(**PARAMETERS)
            raw_data = f.data.raw_data[0:1]

        inputs = pipeline.prepare_parameters(parameters)
        outputs = pipeline(
            **{pipeline.key: raw_data}, **inputs, fill_value=np.nan, return_numpy=True
        )
        sectors.append(np.squeeze(outputs[pipeline.output_key][0]))
        print(f"  f{index:02d}: {sectors[-1].shape}")

    return np.stack(sectors)


def main() -> None:
    paths = sequence_paths()
    print(f"Reconstructing {len(paths)} frames of case {CASE_ID}, plane {PLANE:02d}")
    sectors = reconstruct_sequence(paths)

    # to_8bit maps the dB range onto [0, 255] and sends the NaN samples outside
    # the fan to 0, so the sector sits on a black background.
    frames = zea.display.to_8bit(sectors, dynamic_range=(DISPLAY_FLOOR_DB, 0.0), pillow=False)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    zea.io_lib.save_video(frames, OUTPUT, fps=FPS)


if __name__ == "__main__":
    main()
