# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the twente-microbubblesim dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/twente-microbubblesim

B-mode reconstruction of simulated plane-wave microbubble channel data.

Each file holds one track per transmit pulse (REF, DPT, L1.7, ...), and each
track has its own pipeline in ``pipeline/``; ``PULSE`` picks one. The
pipeline's ``parameters.t_peak`` is that pulse's beamforming timing reference,
copied from the file's ``track_<i>_t_peak`` custom element (identical in every
file). The simulated bubble positions are drawn on top as ground truth.

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
import zea
from zea import Config, File, Pipeline

HERE = Path(__file__).parent

PULSE_NAMES = ("DPT", "L1.7", "L2.5", "L3.4", "LDC", "LUC")
PULSE_NAMES += ("REF", "S1.7", "S2.5", "S3.4", "SDC", "SUC")

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
PULSE = "REF"  # transmit pulse to reconstruct; one of PULSE_NAMES
TRACK = PULSE_NAMES.index(PULSE)
ZEA_FILE = "hf://nvidia/Open-H-RF/twente-microbubblesim/data/Monodispers/RFDATA00002.hdf5"
CONFIG = HERE / "pipeline" / f"pipeline_track_{TRACK}_{PULSE}.yaml"
FRAME = 0
OUT = HERE / "assets" / f"{Path(ZEA_FILE).parent.name}_{PULSE}.png"
HF_CONFIG = f"hf://nvidia/Open-H-RF/twente-microbubblesim/pipeline/{CONFIG.name}"


def main():
    zea.init_device()
    config = Config.from_path(str(CONFIG))

    with File(ZEA_FILE) as f:
        track = f.tracks[TRACK]
        parameters = track.load_parameters(**config.parameters)
        raw = track.data.raw_data[FRAME : FRAME + 1, parameters.selected_transmits]
        depth = float(f.custom["domain_depth"].data)
        bubble_x = f.custom["bubble_x"].data
        bubble_z = f.custom["bubble_z"].data

    pipeline = Pipeline.from_config(config)
    outputs = pipeline(data=raw, **pipeline.prepare_parameters(parameters))
    bmode = keras.ops.convert_to_numpy(outputs[pipeline.output_key])[0]
    image = zea.display.to_8bit(bmode, dynamic_range=parameters.dynamic_range)

    # Plot in cm; the depth axis runs to the simulated domain depth.
    x_min, x_max = (x * 100 for x in config.parameters.xlims)
    z_max = depth * 100
    zea.visualize.set_mpl_style()
    fig, ax = plt.subplots(figsize=(5, 12), constrained_layout=True)
    ax.imshow(
        image,
        cmap="gray",
        aspect="auto",
        extent=(x_min, x_max, z_max, 0),
        interpolation="nearest",
        vmin=0,
        vmax=255,
    )
    ax.scatter(
        bubble_x * 100,
        bubble_z * 100,
        facecolors="none",
        edgecolors="red",
        linewidths=0.8,
        s=28,
        label="Bubble ground truth",
    )
    ax.legend(loc="upper right")
    ax.set_xlabel("Lateral position x [cm]")
    ax.set_ylabel("Depth z [cm]")
    ax.set_title(f"{Path(ZEA_FILE).parent.name} — {PULSE} — {Path(ZEA_FILE).stem}")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(z_max, 0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    print(f"raw {raw.shape} -> B-mode {bmode.shape}; saved {OUT}")


if __name__ == "__main__":
    main()
