# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the tel-aviv dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/tel-aviv

B-mode reconstruction of multi-angle plane-wave acquisitions of mouse tumors and
water-bead phantoms.

Each acquisition samples a volume across a 180 deg rotation of the motorized
array, with five steered plane waves per angular frame. The tumor segmentation
stored alongside the channel data is outlined on the reconstruction.

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

HERE = Path(__file__).parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy. The phantom acquisitions live under
# tel-aviv/phantom and carry no segmentation.
ZEA_FILE = "hf://nvidia/Open-H-RF/tel-aviv/mouse_tumor/seg/01-scan-3.hdf5"
CONFIG = HERE / "mouse_tumor" / "pipeline.yaml"  # this is what the run loads
HF_CONFIG = "hf://nvidia/Open-H-RF/tel-aviv/mouse_tumor/pipeline.yaml"  # where CONFIG is published
FRAME = 46
OUT = HERE / "assets" / "01-scan-3_frame046.png"


def main():
    zea.init_device()
    config = zea.Config.from_path(str(CONFIG))

    with zea.File(ZEA_FILE) as f:
        parameters = f.load_parameters(**config.parameters)
        raw_data = f.data.raw_data[FRAME, parameters.selected_transmits]
        mask = np.argmax(f.data.segmentation.values[FRAME], axis=-1)
        coords = f.data.segmentation.coordinates[:]

    # The segmentation carries the grid it was drawn on, and its depth range
    # varies per mouse. Reconstruct onto that grid so the outline lands on the
    # pixels it was traced over.
    xlims = (float(coords[..., 0].min()), float(coords[..., 0].max()))
    zlims = (float(coords[..., 2].min()), float(coords[..., 2].max()))
    parameters.update(xlims=xlims, zlims=zlims)
    extent = [xlims[0] * 1e3, xlims[1] * 1e3, zlims[1] * 1e3, zlims[0] * 1e3]

    pipeline = zea.Pipeline.from_config(config, with_batch_dim=False)
    inputs = pipeline.prepare_parameters(parameters)
    bmode = pipeline(data=raw_data, **inputs, return_numpy=True)["data"]

    zea.visualize.set_mpl_style()
    fig, ax = plt.subplots(figsize=(6, 7))
    ax.imshow(bmode, cmap="gray", extent=extent, aspect="equal")
    zea.visualize.plot_shape_from_mask(
        ax, mask, extent=extent, edgecolor="red", facecolor="none", linewidth=1.5
    )
    ax.set_title(f"{Path(ZEA_FILE).stem} — B-mode + segmentation, frame {FRAME}")
    ax.set_xlabel("Lateral [mm]")
    ax.set_ylabel("Axial depth [mm]")
    fig.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches="tight")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
