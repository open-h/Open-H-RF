# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the waterloo-muscle dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/waterloo-muscle

B-mode reconstruction of plane-wave muscle channel data (UW-MuscleRF).

Requires zea>=0.1.6 (https://github.com/tue-bmd/zea), the library that does the
ultrasound processing here, together with one of its Keras backends (JAX,
PyTorch or TensorFlow). Installation instructions are at
https://zea.readthedocs.io/en/latest/installation.html.

Usage:
    python reconstruct.py

@ LITMUS Research Group, University of Waterloo, 2026.
"""

import os

os.environ.setdefault("KERAS_BACKEND", "jax")
os.environ.setdefault("MPLBACKEND", "Agg")

from pathlib import Path

import matplotlib.pyplot as plt
import zea
from zea import File, Pipeline
from zea.ops import (
    BandPassFilter,
    Beamform,
    Cast,
    Demodulate,
    EnvelopeDetect,
    LogCompress,
    Normalize,
)

HERE = Path(__file__).parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/waterloo-muscle/data/Acq_p35_Calf_left_calf_lateral_longitudinal_relaxed_pressure.hdf5"
CONFIG = HERE / "pipeline.yaml"
OUT = HERE / "assets" / "reconstruct_output.png"
HF_CONFIG = "hf://nvidia/Open-H-RF/waterloo-muscle/pipeline.yaml"
FRAME = 9

# The reconstruction grid matches the stored B-mode so the two line up. Kept here
# rather than derived per file so pipeline.yaml fully describes the reconstruction
# and zea process reproduces it.
PARAMETERS = {
    "xlims": [-0.019, 0.019],
    "zlims": [0.0, 0.080],
    "grid_size_x": 381,
    "grid_size_z": 801,
    "dynamic_range": [-60, 0],
}


def write_config(pipeline: Pipeline, path) -> None:
    """Serialize the pipeline and its acquisition parameters to pipeline.yaml."""
    config = pipeline.to_config()
    config["parameters"] = PARAMETERS
    config.to_yaml(str(path))


def build_pipeline() -> Pipeline:
    """Define the delay-and-sum B-mode pipeline in code."""
    return Pipeline(
        operations=[
            Cast(dtype="float32"),
            BandPassFilter(passband=(3e6, 7e6)),
            Demodulate(),
            Beamform(beamformer="delay_and_sum"),
            EnvelopeDetect(),
            Normalize(),
            LogCompress(),
        ],
    )


def main():
    zea.init_device()

    pipeline = build_pipeline()
    write_config(pipeline, CONFIG)

    with File(str(ZEA_FILE)) as f:
        frame = min(max(0, FRAME), f.data.image.values.shape[0] - 1)
        raw = f.data.raw_data[frame : frame + 1]  # (1, n_tx, n_ax, n_el, 1)
        parameters = f.load_parameters(**PARAMETERS)

    inputs = pipeline.prepare_parameters(parameters)
    recon = pipeline(data=raw, **inputs, return_numpy=True)["data"][0]
    extent = [v * 1e3 for v in parameters.extent_imshow]  # metres -> mm

    zea.visualize.set_mpl_style()
    # Size each panel to the image aspect ratio so the axes hug the B-mode.
    panel_h = 5.5
    img_aspect = (extent[1] - extent[0]) / (extent[2] - extent[3])
    fig, ax = plt.subplots(figsize=(panel_h * img_aspect, panel_h), constrained_layout=True)
    ax.imshow(
        recon,
        cmap="gray",
        vmin=parameters.dynamic_range[0],
        vmax=parameters.dynamic_range[1],
        extent=extent,
    )
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("z [mm]")
    ax.set_aspect("equal", adjustable="box")

    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
