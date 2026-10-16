# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the vanderbilt dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/vanderbilt

B-mode reconstruction of focused-transmit echocardiography channel data
(fundamental and harmonic) and the CIRS validation phantom.

All three reconstruct the same way. Each file holds 32 frames: set
``number_of_frames`` to 1 for just the first frame (the default) or to 32 for
the whole cineloop.

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
from zea import Config, File, Pipeline
from zea.ops import (
    Beamform,
    Cast,
    Demodulate,
    EnvelopeDetect,
    LogCompress,
    Normalize,
    ScanConvert,
)

HERE = Path(__file__).parent
CONFIG = HERE / "pipeline.yaml"  # written by write_config(); this is what the run loads
HF_CONFIG = "hf://nvidia/Open-H-RF/vanderbilt/pipeline.yaml"  # where CONFIG is published

# P4-2v is a phased array (sector scan), so beamform on a polar grid and
# scan convert to Cartesian for display, rather than beamforming directly
# on a Cartesian grid. polar_limits is pinned to the actual transmit angle
# range (+/-45 deg)
PARAMETERS = {
    "grid_type": "polar",
    "polar_limits": [-np.pi / 4, np.pi / 4],
    "grid_size_x": 1084,
    "grid_size_z": 636,
    "dynamic_range": [-60, 0],
    "zlims": [0, 0.18],
    "apply_lens_correction": False,
    "f_number": 0,
}

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/vanderbilt/data/Fundamental/118420_1_Focused_Uncoded_TX.hdf5"
N_FRAMES = 1
DEVICE = None  # CUDA device ID (e.g. 'cuda:0', 'auto:1', or 'cpu')


def build_pipeline() -> Pipeline:
    """Define the delay-and-sum beamforming pipeline in code."""
    return Pipeline(
        operations=[
            Cast(dtype="float32"),
            Demodulate(),
            Beamform(
                beamformer="delay_and_sum",
                enable_pfield=True,
            ),
            EnvelopeDetect(),
            Normalize(),
            LogCompress(),
            ScanConvert(),
        ],
    )


def write_config(pipeline: Pipeline, path: Path) -> None:
    """Serialize the pipeline and acquisition parameters to a YAML config file."""
    config = pipeline.to_config()
    config["parameters"] = PARAMETERS
    config.to_yaml(str(path))


def main():
    # The input may be an hf:// URI, so write the PNG beside this script.
    output_path = HERE / "assets" / f"{Path(ZEA_FILE).stem}.png"

    zea.init_device(device=DEVICE, verbose=False)

    # Define the beamforming pipeline in code, save it (with the acquisition
    # parameters) to pipeline.yaml, then load that YAML back in.
    write_config(build_pipeline(), CONFIG)
    config = Config.from_path(str(CONFIG))

    frames = list(range(N_FRAMES))
    # Load file: read acquisition parameters (with config overrides) and raw RF data
    with File(str(ZEA_FILE)) as f:
        parameters = f.load_parameters(**config.parameters)

        # Only grab and beamform the first frame
        raw = f.data.raw_data[frames, ...]  # (n_frames, n_tx, n_ax, n_el, 1) — RF

    # Build and run the beamforming pipeline loaded from pipeline.yaml
    pipeline = Pipeline.from_config(config)
    inputs = pipeline.prepare_parameters(parameters)

    outputs = pipeline(data=raw, **inputs, return_numpy=True)

    # Convert the output tensor to a NumPy array and save as PNG
    recon = outputs["data"]  # (n_frames, grid_z, grid_x)
    image = zea.display.to_8bit(recon[0], dynamic_range=parameters.dynamic_range)

    zea.visualize.set_mpl_style()
    plt.imshow(
        image,
        extent=parameters.extent_imshow,
        cmap="gray",
    )
    plt.xlabel("X (m)")
    plt.ylabel("Z (m)")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), bbox_inches="tight", dpi=100)

    print(f"Reconstructed  : {recon.shape}")
    print(f"Saved          : {output_path}")


if __name__ == "__main__":
    main()
