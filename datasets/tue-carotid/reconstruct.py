# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the tue-carotid dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/tue-carotid

B-mode reconstruction of in-vivo carotid channel data.

The acquisition interleaves 128 focused scan lines with 21 plane-wave
transmits; ``parameters.selected_transmits`` decides which of them go into the
reconstruction.

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
import zea

HERE = Path(__file__).parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/tue-carotid/data/5_long_bifur_R_0000.hdf5"
CONFIG = "hf://nvidia/Open-H-RF/tue-carotid/pipeline.yaml"
FRAME = 0
OUT = HERE / "assets" / "zea_carotid_2023_sample.png"


def main():
    zea.init_device()
    config = zea.Config.from_path(CONFIG)

    # Load data and parameters
    with zea.File(ZEA_FILE) as f:
        parameters = f.load_parameters(**config.parameters)
        raw_data = f.data.raw_data[FRAME, parameters.selected_transmits]

    # Process data through the pipeline
    pipeline = zea.Pipeline.from_path(CONFIG, with_batch_dim=False)
    bmode = pipeline(data=raw_data, **pipeline.prepare_parameters(parameters))["data"]

    # Save PNG
    zea.visualize.set_mpl_style()
    plt.figure()
    plt.imshow(
        bmode,
        cmap="gray",
        vmin=config.parameters.dynamic_range[0],
        vmax=config.parameters.dynamic_range[1],
        extent=parameters.extent_imshow * 1e3,
    )
    plt.xlabel("x [mm]")
    plt.ylabel("z [mm]")
    plt.title("TU/e carotid 2023 sample")
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(OUT), dpi=300, bbox_inches="tight")
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
