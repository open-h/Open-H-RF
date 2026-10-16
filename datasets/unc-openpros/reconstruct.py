# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the unc-openpros dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/unc-openpros

Speed-of-sound reconstruction of limited-view prostate waveform data with a
pretrained InversionNet.

The waveform data are converted back to the tensor layout used by the OpenPros
models and given the same signed-log and min-max preprocessing as the official
OpenPros implementation, as defined in ``pipeline.yaml`` (loaded straight from
the Hub). The network's normalized prediction is mapped back to the physical
speed-of-sound range (1300--3600 m/s), then saved two ways: a side-by-side
comparison against the ground truth (``pred_sos.png``) and a clean, unlabeled
hero image of just the prediction (``assets/main.png``).

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

import custom_ops  # noqa: F401 - registers MyRearrange/LogTransform with zea's ops_registry
import keras
import matplotlib.pyplot as plt
import network_ops  # noqa: F401 - registers InversionNetInference with zea's ops_registry
import zea
from mpl_toolkits.axes_grid1 import make_axes_locatable
from zea import Config, File, Pipeline

HERE = Path(__file__).parent
OUT = HERE / "assets" / "comparison.png"
MAIN_OUTPUT = HERE / "assets" / "main.png"

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/unc-openpros/data/3_01_P_prostate_00.hdf5"
CONFIG = "hf://nvidia/Open-H-RF/unc-openpros/pipeline.yaml"
# The file holds 1140 acquisitions; the figure shows the first.
SAMPLES = 1  # acquisitions to run through the network

SOS_CMAP = "turbo"  # high-contrast, multi-hue colormap for the SOS maps
SOS_RANGE = (1300, 1700)  # physical speed-of-sound range, m/s


def plot_comparison(sos, pred, path: Path) -> None:
    """Side-by-side ground-truth vs. predicted SOS maps, for validation."""
    zea.visualize.set_mpl_style()
    pred = keras.ops.convert_to_numpy(pred)
    fig, ax = plt.subplots(1, 2, figsize=(7, 6))
    ax[0].imshow(sos[0, :, :, 0], cmap=SOS_CMAP, vmin=SOS_RANGE[0], vmax=SOS_RANGE[1])
    ax[0].set_title("Ground Truth SOS Map")
    im = ax[1].imshow(pred[0, :, :, 0], cmap=SOS_CMAP, vmin=SOS_RANGE[0], vmax=SOS_RANGE[1])
    ax[1].set_title("Predicted SOS Map")
    for axis in ax:
        axis.set_xlabel("X (mm)")
        axis.set_xticks(range(0, 161, 40), labels=range(0, 61, 15))
    ax[0].set_ylabel("Z (mm)")
    ax[0].set_yticks(range(0, 401, 80), labels=range(0, 151, 30))
    ax[1].set_yticks(range(0, 401, 80), [])
    cax = make_axes_locatable(ax[1]).append_axes("right", size="5%", pad=0.05)
    fig.colorbar(im, cax=cax, orientation="vertical", label="SOS (m/s)")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_main(pred, path: Path) -> None:
    """Clean hero image: just the predicted SOS map, no axes/title/colorbar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = keras.ops.convert_to_numpy(pred)[0, :, :, 0]
    height, width = image.shape
    fig = plt.figure(figsize=(width / 100, height / 100), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(image, cmap=SOS_CMAP, vmin=SOS_RANGE[0], vmax=SOS_RANGE[1])
    ax.axis("off")
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    zea.init_device(verbose=False)

    config = Config.from_path(str(CONFIG))
    pipeline = Pipeline.from_config(config)

    with File(ZEA_FILE) as f:
        raw = f.data.raw_data[:SAMPLES]
        sos = f.data.sos_map.values[:SAMPLES]  # gt

    print(f"raw_data shape: {raw.shape}")
    print(f"ground truth shape: {sos.shape}")
    outputs = pipeline(data=raw)["data"]
    print(f"reconstructed shape: {outputs.shape}")

    plot_comparison(sos, outputs, OUT)
    print(f"Saved comparison plot: {OUT}")

    plot_main(outputs, MAIN_OUTPUT)
    print(f"Saved hero image: {MAIN_OUTPUT}")


if __name__ == "__main__":
    main()
