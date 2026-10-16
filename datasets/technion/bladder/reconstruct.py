# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the technion/bladder dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/technion/bladder

B-mode reconstruction of in-vivo bladder channel data on a polar scanline grid.

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

HERE = Path(__file__).parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/technion/bladder/data/a1.hdf5"
CONFIG = "hf://nvidia/Open-H-RF/technion/bladder/pipeline.yaml"
FRAME = 10
OUT = HERE / "assets" / "bmode.png"


def main():
    zea.init_device()
    config = Config.from_path(str(CONFIG))

    with File(str(ZEA_FILE)) as f:
        parameters = f.load_parameters(**config.parameters)
        raw = f.data.raw_data[FRAME : FRAME + 1]  # (1, n_tx, n_ax, n_el, n_ch)

    pipeline = Pipeline.from_config(config)
    inputs = pipeline.prepare_parameters(parameters)
    outputs = pipeline(data=raw, **inputs, return_numpy=True)
    recon = np.asarray(outputs[pipeline.output_key])[0]  # (grid_z, grid_x)

    zea.visualize.set_mpl_style()
    fig, ax = plt.subplots(figsize=(5.5, 6))
    im = ax.imshow(
        zea.display.to_8bit(recon),
        cmap="gray",
        extent=np.asarray(parameters.extent_imshow) * 1e3,  # m -> mm
        aspect="equal",
    )
    ax.set_xlabel("lateral [mm]")
    ax.set_ylabel("depth [mm]")
    ax.set_title(f"{Path(ZEA_FILE).stem} — frame {FRAME}")
    cax = make_axes_locatable(ax).append_axes("right", size="5%", pad=0.05)
    fig.colorbar(im, cax=cax, label="a.u. (8-bit)")
    fig.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(OUT), dpi=130, bbox_inches="tight")
    print(f"raw {raw.shape} -> B-mode {recon.shape}; saved {OUT}")


if __name__ == "__main__":
    main()
