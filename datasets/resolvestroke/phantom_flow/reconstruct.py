# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the resolvestroke/phantom_flow dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/resolvestroke/phantom_flow

B-mode reconstruction of a matrix-probe diverging-wave pipe phantom flow acquisition.

Because the probe is a 2D array (32x32), a single diverging transmit insonifies
a 3D volume, while zea's polar grid is 2D (a single x-z fan at y=0). The script
therefore builds two perpendicular sector grids and beamforms each: the standard
x-z fan (y = 0) and the same fan rotated 90 deg about z (x = 0). Both are
(n_radial, n_angular, 3) Cartesian point clouds fed to the beamformer via the
``grid``/``flatgrid`` overrides, so the pipeline runs once per plane. Each sector
is scan-converted and the two are displayed side by side.

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
from zea.beamform.pixelgrid import polar_pixel_grid

HERE = Path(__file__).parent
CONFIG = "hf://nvidia/Open-H-RF/resolvestroke/phantom_flow/pipeline.yaml"

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/resolvestroke/phantom_flow/phantom_flow.hdf5"
FRAME = 0
OUT = HERE / "assets" / f"{Path(ZEA_FILE).stem}_bmode.png"


def reverse_tgc(raw, parameters):
    """Undo the hardware time-gain compensation baked into ``raw_data``.

    The hardware applies a (non-linear) depth-dependent gain before the ADC, so
    ``raw_data`` carries it. zea stores that gain as ``scan/tgc_gain_curve`` (n_ax,)
    — "the TGC applied to every sample; divide by this curve to undo it". Doing it
    here (a plain per-axial-sample divide) keeps the zea pipeline fully standard.
    """
    tgc = np.asarray(parameters.tgc_gain_curve, dtype=np.float32)  # (n_ax,)
    return np.asarray(raw, dtype=np.float32) / tgc.reshape(1, 1, -1, 1, 1)


def build_sector_grids(config):
    """Build two perpendicular 2D sector grids (x-z and y-z) for a diverging wave.

    zea's polar grid only supports the x-z plane (y = 0), so the y-z sector is
    the same fan with its x and y coordinates swapped (a 90 deg rotation about z).

    Returns:
        (grid_xz, grid_yz, apex): each grid has shape (n_radial, n_angular, 3)
        in Cartesian (x, y, z) metres; apex is the virtual-source depth in metres.
    """
    p = config.parameters
    apex = float(p.distance_to_apex)  # virtual source behind the array

    polar_limits = tuple(float(v) for v in p["polar_limits"])
    z0, z1 = (float(v) for v in p["zlims"])
    # polar_pixel_grid takes zlims as on-axis depth from the transducer face and adds
    # distance_to_apex to the radii itself, so the configured zlims go in unchanged.
    grid_xz = polar_pixel_grid(
        polar_limits,
        (z0, z1),
        num_radial_pixels=int(p["grid_size_z"]),
        num_polar_pixels=int(p["grid_size_x"]),
        distance_to_apex=apex,
    )

    # y-z sector: rotate the fan 90 deg about z (swap x <-> y).
    grid_yz = grid_xz.copy()
    grid_yz[..., 0] = 0.0
    grid_yz[..., 1] = grid_xz[..., 0]
    return grid_xz, grid_yz, apex


def beamform_sector(pipeline, parameters, raw, grid):
    """Beamform `raw` onto an arbitrary Cartesian `grid` (n_r, n_theta, 3)."""
    flatgrid = grid.reshape(-1, 3)
    inputs = pipeline.prepare_parameters(parameters, grid=grid, flatgrid=flatgrid)
    outputs = pipeline(**{pipeline.key: raw}, **inputs, return_numpy=True)
    return np.asarray(outputs[pipeline.output_key])[0]  # (n_r, n_theta)


def main():

    zea.init_device()
    config = Config.from_path(str(CONFIG))

    with File(str(ZEA_FILE)) as f:
        parameters = f.load_parameters(**config.parameters)
        raw = f.data.raw_data[FRAME : FRAME + 1]  # (1, n_tx, n_ax, n_el, n_ch)

    raw = reverse_tgc(raw, parameters)  # undo hardware TGC before beamforming
    grid_xz, grid_yz, apex = build_sector_grids(config)
    print(f"raw_data shape : {raw.shape}")
    print(f"sector grid    : {grid_xz.shape}  (polar, apex={apex * 1e3:.1f} mm)")

    pipeline = Pipeline.from_config(config)
    xz_slice = beamform_sector(pipeline, parameters, raw, grid_xz)  # (n_r, n_theta)
    yz_slice = beamform_sector(pipeline, parameters, raw, grid_yz)

    dr = config.parameters.get("dynamic_range", [-40, 0])
    vmin, vmax = float(dr[0]), float(dr[1])

    zea.visualize.set_mpl_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))

    # x-z sector: scan-convert with the fan's Cartesian (x, z).
    x_mm, z_mm = grid_xz[..., 0] * 1e3, grid_xz[..., 2] * 1e3
    pm1 = ax1.pcolormesh(x_mm, z_mm, xz_slice, cmap="gray", vmin=vmin, vmax=vmax, shading="auto")
    ax1.set_aspect("equal")
    ax1.invert_yaxis()
    ax1.set_title(f"x-z sector (y=0) — frame {FRAME}")
    ax1.set_xlabel("x [mm]")
    ax1.set_ylabel("z [mm]")
    cax1 = make_axes_locatable(ax1).append_axes("right", size="5%", pad=0.05)
    fig.colorbar(pm1, cax=cax1, label="dB")

    # y-z sector: the fan lives in y-z, so plot y vs z.
    y_mm, z2_mm = grid_yz[..., 1] * 1e3, grid_yz[..., 2] * 1e3
    pm2 = ax2.pcolormesh(y_mm, z2_mm, yz_slice, cmap="gray", vmin=vmin, vmax=vmax, shading="auto")
    ax2.set_aspect("equal")
    ax2.invert_yaxis()
    ax2.set_title(f"y-z sector (x=0) — frame {FRAME}")
    ax2.set_xlabel("y [mm]")
    ax2.set_ylabel("z [mm]")
    cax2 = make_axes_locatable(ax2).append_axes("right", size="5%", pad=0.05)
    fig.colorbar(pm2, cax=cax2, label="dB")

    print(f"x-z sector     : {xz_slice.shape}")
    print(f"y-z sector     : {yz_slice.shape}")

    fig.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(OUT), dpi=150, bbox_inches="tight")
    print(f"Saved          : {OUT}")


if __name__ == "__main__":
    main()
