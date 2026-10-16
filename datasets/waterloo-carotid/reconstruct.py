# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the waterloo-carotid dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/waterloo-carotid

B-mode reconstruction of steered plane-wave carotid channel data (UW-CarotidRF).

The display dynamic range lives in pipeline.yaml (``parameters.dynamic_range``);
tweak it there and it is picked up for display. Where the vector-flow fields are
present, a second panel overlays the vector velocity field using
``draw_velocity_field`` -- a self-contained (numpy + matplotlib) helper
reproduced below from the LITMUS core Python package
(``litmus.core_py.visualization``), so this script has no dependency on the full
LITMUS GPU stack.

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

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import zea
from zea import Config, File, Pipeline
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

DYNAMIC_RANGE = [-50, 0]  # dB; written to pipeline.yaml, tweak it there

# Reconstruction grid, matching the stored B-mode. Written into pipeline.yaml so
# zea process reproduces the same field of view.
PARAMETERS = {
    "xlims": [-0.019, 0.019],
    "zlims": [0.0, 0.030],
    "grid_size_x": 381,
    "grid_size_z": 301,
    "dynamic_range": DYNAMIC_RANGE,
}

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/waterloo-carotid/data/Acq1.hdf5"
CONFIG = HERE / "pipeline.yaml"
OUT = HERE / "assets" / "reconstruct_output.png"
HF_CONFIG = "hf://nvidia/Open-H-RF/waterloo-carotid/pipeline.yaml"
FRAME = 250
POWER_THRESHOLD = 55.0  # Power Doppler mask threshold (dB)


def draw_velocity_field(
    ax,
    vx,
    vz,
    power,
    threshold,
    extent,
    arrows_across=40,
    arrow_span=2.5,
    cmap="jet",
    vmax=None,
):
    """Overlay power-Doppler-masked velocity vectors on `ax` as a quiver plot.

    Reproduced from the LITMUS core Python package
    (`litmus.core_py.visualization.vector_field`), LITMUS Research Group,
    University of Waterloo, 2026. `extent` is [left, right, bottom, top] in mm.

    Arrows are sampled ``arrows_across`` to the image width and scaled so the
    fastest one spans ``arrow_span`` sample spacings, which keeps them legible
    whatever the field of view.
    """
    nz, nx = vx.shape
    step = max(1, int(round(nx / arrows_across)))
    x = np.linspace(extent[0], extent[1], nx)
    z = np.linspace(extent[3], extent[2], nz)
    X, Z = np.meshgrid(x, z)

    U = vx[::step, ::step]
    V = -vz[::step, ::step]  # negate so +axial velocity points up on screen
    mag = np.sqrt(U**2 + V**2)

    invalid = (power[::step, ::step] < threshold) | np.isnan(mag)
    U = np.where(invalid, np.nan, U)
    V = np.where(invalid, np.nan, V)
    mag = np.where(invalid, np.nan, mag)

    spacing = abs(extent[1] - extent[0]) / nx * step  # mm between arrows
    scale = (vmax or 1.0) / (arrow_span * spacing)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        q = ax.quiver(
            X[::step, ::step],
            Z[::step, ::step],
            U,
            V,
            mag,
            cmap=cmap,
            angles="xy",
            scale_units="xy",
            scale=scale,
            pivot="middle",
            width=0.006,
        )
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    return q


def build_config() -> Config:
    """Define the delay-and-sum B-mode pipeline in code, plus the display range."""
    config = Pipeline(
        operations=[
            Cast(dtype="float32"),
            BandPassFilter(passband=(3e6, 7e6)),
            Demodulate(),
            Beamform(beamformer="delay_and_sum"),
            EnvelopeDetect(),
            Normalize(),
            LogCompress(),
        ],
    ).to_config()
    config["parameters"] = PARAMETERS
    return config


def main():
    zea.init_device()

    config = build_config()
    config.to_yaml(str(CONFIG))
    pipeline = Pipeline.from_config(config)

    with File(str(ZEA_FILE)) as f:
        frame = min(max(0, FRAME), f.data.image.values.shape[0] - 1)

        raw = f.data.raw_data[frame : frame + 1]  # (1, n_tx, n_ax, n_el, 1)
        parameters = f.load_parameters(**config.get("parameters", {}))

        has_velocity = all(
            k in f.data for k in ("vector_velocity_x", "vector_velocity_z", "power_doppler")
        )
        if has_velocity:
            vx = f.data.vector_velocity_x.values[frame]
            vz = f.data.vector_velocity_z.values[frame]
            power = f.data.power_doppler.values[frame]

    inputs = pipeline.prepare_parameters(parameters)
    recon = pipeline(data=raw, **inputs, return_numpy=True)["data"][0]
    extent = [v * 1e3 for v in parameters.extent_imshow]  # metres -> mm
    vmin, vmax_db = parameters.dynamic_range

    zea.visualize.set_mpl_style()
    n_panels = 2 if has_velocity else 1
    # Size each panel to the image aspect ratio so the axes hug the B-mode.
    panel_h = 5.0
    img_aspect = (extent[1] - extent[0]) / (extent[2] - extent[3])
    fig, axes = plt.subplots(
        1,
        n_panels,
        figsize=(panel_h * img_aspect * n_panels, panel_h),
        constrained_layout=True,
    )
    imshow_kw = dict(cmap="gray", vmin=vmin, vmax=vmax_db, extent=extent)

    axes[0].imshow(recon, **imshow_kw)

    if has_velocity:
        mag = np.sqrt(vx**2 + vz**2)
        valid = (power >= POWER_THRESHOLD) & ~np.isnan(mag)
        v_scale = float(np.percentile(mag[valid], 95)) if np.any(valid) else 1.0
        axes[1].imshow(recon, **imshow_kw)
        q = draw_velocity_field(axes[1], vx, vz, power, POWER_THRESHOLD, extent, vmax=v_scale)
        q.set_clim(0, v_scale)

    for ax in axes:
        ax.set_xlabel("x [mm]")
        ax.set_ylabel("z [mm]")
        ax.set_aspect("equal", adjustable="box")

    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(OUT), dpi=150, bbox_inches="tight")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
