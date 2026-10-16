# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the strasbourg-basel dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/strasbourg-basel

B-mode reconstruction of focused, walking-aperture bone channel data (BoneSRF).

All nine scans reconstruct the same way; only the input file and the frame
chosen as that scan's reference differ.

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
from zea import Config, File, Pipeline

HERE = Path(__file__).parent
CONFIG = HERE / "pipeline.yaml"
OUTPUT_DIR = HERE / "assets"
ASSETS = HERE / "assets"

# The frame each scan's committed reference_bmodes/<scan>.png was rendered from.
REFERENCE_FRAME = {
    "phantom1_distal": 130,
    "phantom1_proximal": 100,
    "phantom1_wholebone": 150,
    "phantom2_distal": 40,
    "phantom2_proximal": 40,
    "phantom2_wholebone": 45,
    "phantom3_distal": 100,
    "phantom3_proximal": 0,
    "phantom3_wholebone": 100,
}

# The CT segment outlining the phantom, per sweep (see the README's segment table).
CT_SEGMENT = {"distal": "Distal", "proximal": "Proximal", "wholebone": "Complete"}

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
SCAN = "hf://nvidia/Open-H-RF/strasbourg-basel/BoneSRF/data/phantom2_proximal.hdf5"
FRAME = None  # frame to beamform (default: that scan's reference frame)
DEVICE = None  # CUDA device ID (e.g. 'cuda:0', 'auto:1', or 'cpu')
CT = True  # also write assets/ct_<scan>.png from the CT embedded in the file


def reconstruct(source: str, scan: str, frame: int, config: Config) -> None:
    """Beamform one frame of one scan and write reference_bmodes/<scan>.png.

    ``source`` is a local path or an ``hf://`` URI and stays a string throughout
    -- pathlib collapses the ``//`` in a URI.
    """
    # Each file is a full multi-frame sweep (~20-24 GB); only this frame is read.
    with File(str(source)) as f:
        parameters = f.load_parameters(**config.parameters)  # dynamic_range etc.
        raw = f.data.raw_data[frame : frame + 1]  # (1, n_tx, n_ax, n_el, n_ch)

    print(f"{scan}: frame {frame}, raw_data {raw.shape}, grid {parameters.grid.shape}")

    pipeline = Pipeline.from_config(config)
    outputs = pipeline(data=raw, **pipeline.prepare_parameters(parameters))

    recon = keras.ops.convert_to_numpy(outputs["data"])  # (n_frames, grid_z, grid_x, n_ch)
    # No envelope_detect in pipeline.yaml (see its comments), so the trailing
    # n_ch=1 axis survives to the output; squeeze it for a 2D image.
    image = zea.display.to_8bit(np.squeeze(recon[0]), dynamic_range=parameters.dynamic_range)

    zea.visualize.set_mpl_style()
    plt.figure()
    # extent_imshow is in meters; convert to mm to match the axis labels below.
    plt.imshow(image, extent=np.array(parameters.extent_imshow) * 1e3, cmap="gray")
    plt.xlabel("X (mm)")
    plt.ylabel("Z (mm)")
    out = OUTPUT_DIR / f"{scan}.png"
    plt.savefig(str(out), bbox_inches="tight", dpi=100)
    plt.close()
    print(f"  saved {out.relative_to(HERE)}")


def plot_ct(source: str, scan: str) -> None:
    """Plot three slices of the file's CT and write assets/ct_<scan>.png.

    The segment outlined is the one covering this scan's sweep of the phantom.
    """
    phantom, sweep = scan.split("_")
    segment = f"BoneSRF-{phantom[-1]}_{CT_SEGMENT[sweep]}"

    ct, seg = "custom/ct", "custom/ct_segmentation"
    with File(str(source)) as f:
        volume = f.dataset(f"{ct}/volume")[:]  # (k, j, i), a few hundred MB
        names = list(f.dataset(f"{seg}/segment_names")[:])
        s = names.index(segment)
        layer = int(f.dataset(f"{seg}/segment_layers")[s])
        label = int(f.dataset(f"{seg}/segment_label_values")[s])
        mask = f.dataset(f"{seg}/labelmap")[..., layer] == label
        # spacing is index-ordered (i, j, k) in meters; the arrays are stored (k, j, i).
        si, sj, sk = f.dataset(f"{ct}/spacing")[:] * 1e3

    # Slice through the middle of the bone, trimming the air around the phantom.
    kc, jc, ic = (int(np.median(axis)) for axis in np.nonzero(mask))
    solid = volume > -500  # the phantom and its container, i.e. everything but air
    (k0, k1), (j0, j1), (i0, i1) = (
        (int(used[0]), int(used[-1]) + 1)
        for used in (np.nonzero(solid.any(axis=tuple({0, 1, 2} - {axis})))[0] for axis in range(3))
    )
    kk, jj, ii = slice(k0, k1), slice(j0, j1), slice(i0, i1)
    panels = [  # view, what to slice out, then the (offset, spacing, name) of each axis
        ("Coronal", (kk, jc, ii), (i0, si, "i"), (k0, sk, "k")),
        ("Sagittal", (kk, jj, ic), (j0, sj, "j"), (k0, sk, "k")),
        ("Axial", (kc, jj, ii), (i0, si, "i"), (j0, sj, "j")),
    ]

    zea.visualize.set_mpl_style()
    fig, axes = plt.subplots(1, 3, figsize=(12, 5), constrained_layout=True)
    for ax, (view, index, (x0, sx, x), (y0, sy, y)) in zip(axes, panels):
        image, outline = volume[index], mask[index]
        xs = (x0 + np.arange(image.shape[1])) * sx
        ys = (y0 + np.arange(image.shape[0])) * sy
        # The print is hollow, so the bone reads dark against the bright coupling gel.
        ax.imshow(
            image,
            cmap="gray",
            vmin=-1024,
            vmax=250,
            aspect="equal",
            extent=(xs[0], xs[-1], ys[-1], ys[0]),
        )
        ax.contour(xs, ys, outline, levels=[0.5], colors="red", linewidths=0.9)
        ax.set_title(view)
        ax.set_xlabel(f"{x} (mm)")
        ax.set_ylabel(f"{y} (mm)")
    fig.suptitle(f"{scan}: CT with {segment} outlined")

    out = ASSETS / f"ct_{scan}.png"
    fig.savefig(str(out), bbox_inches="tight", dpi=140)
    plt.close(fig)
    print(f"  saved {out.relative_to(HERE)}")


def main():
    scan = Path(SCAN).stem
    frame = FRAME if FRAME is not None else REFERENCE_FRAME[scan]

    zea.init_device(device=DEVICE, verbose=False)
    OUTPUT_DIR.mkdir(exist_ok=True)
    ASSETS.mkdir(exist_ok=True)
    config = Config.from_path(str(CONFIG))

    reconstruct(SCAN, scan, frame, config)
    if CT:
        plot_ct(SCAN, scan)


if __name__ == "__main__":
    main()
