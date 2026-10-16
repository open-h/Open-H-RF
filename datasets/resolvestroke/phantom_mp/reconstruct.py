# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the resolvestroke/phantom_mp dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/resolvestroke/phantom_mp

B-mode reconstruction of a matrix-probe diverging-wave phantom acquisition.

Because the probe is a 2D array and the transmit is a single diverging wave, one
frame insonifies a 3D volume, while zea's polar grid is 2D (an x-z fan at y=0).
The script therefore beamforms two perpendicular sector fans, x-z (y = 0) and
y-z (x = 0), and shows them side by side. Hardware TGC is divided out of the
channel data first.

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
CONFIG = "hf://nvidia/Open-H-RF/resolvestroke/phantom_mp/pipeline.yaml"

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/resolvestroke/phantom_mp/phantom_mp.hdf5"
FRAME = 0
OUT = HERE / "assets" / f"{Path(ZEA_FILE).stem}_bmode.png"


def sector_grids(p, apex):
    """Two perpendicular diverging-wave sector fans, each (n_radial, n_angular, 3)
    in Cartesian metres. The y-z fan is the x-z fan rotated 90 deg about z (swap
    x and y). polar_pixel_grid takes zlims as on-axis depth and adds the apex to the
    radii itself, so the configured zlims go in unchanged."""
    lims = tuple(float(v) for v in p["polar_limits"])
    z0, z1 = (float(v) for v in p["zlims"])
    xz = polar_pixel_grid(lims, (z0, z1), int(p["grid_size_z"]), int(p["grid_size_x"]), apex)
    yz = xz.copy()
    yz[..., 0], yz[..., 1] = 0.0, xz[..., 0]
    return np.stack([xz, yz])  # (2, n_r, n_theta, 3)


def main():

    zea.init_device()
    config = Config.from_path(str(CONFIG))
    with File(str(ZEA_FILE)) as f:
        parameters = f.load_parameters(**config.parameters)
        raw = f.data.raw_data[FRAME : FRAME + 1]  # (1, n_tx, n_ax, n_el, n_ch)

    # Undo the hardware TGC baked into raw_data (divide by scan/tgc_gain_curve).
    tgc = np.asarray(parameters.tgc_gain_curve, np.float32)
    raw = np.asarray(raw, np.float32) / tgc.reshape(1, 1, -1, 1, 1)

    apex = float(config.parameters.distance_to_apex)  # virtual source behind the array
    grid = sector_grids(config.parameters, apex)  # (2, n_r, n_theta, 3): [x-z, y-z]

    # Beamform both fans in one pass; reshape_grid restores the (2, n_r, n_theta) shape.
    pipeline = Pipeline.from_config(config)
    inputs = pipeline.prepare_parameters(parameters, grid=grid, flatgrid=grid.reshape(-1, 3))
    sectors = np.asarray(
        pipeline(**{pipeline.key: raw}, **inputs, return_numpy=True)[pipeline.output_key]
    )[0]
    print(f"raw {raw.shape}  sectors {sectors.shape}  (polar, apex={apex * 1e3:.1f} mm)")

    dr = config.parameters.get("dynamic_range", [-40, 0])
    vmin, vmax = float(dr[0]), float(dr[1])
    zea.visualize.set_mpl_style()
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    for ax, g, img, lat, plane in [
        (axes[0], grid[0], sectors[0], 0, "x-z (y=0)"),
        (axes[1], grid[1], sectors[1], 1, "y-z (x=0)"),
    ]:
        pm = ax.pcolormesh(
            g[..., lat] * 1e3,
            g[..., 2] * 1e3,
            img,
            cmap="gray",
            vmin=vmin,
            vmax=vmax,
            shading="auto",
        )
        ax.set_aspect("equal")
        ax.invert_yaxis()
        ax.set_title(f"{plane} sector, frame {FRAME}")
        ax.set_xlabel("xy"[lat] + " [mm]")
        ax.set_ylabel("z [mm]")
        cax = make_axes_locatable(ax).append_axes("right", size="5%", pad=0.05)
        fig.colorbar(pm, cax=cax, label="dB")

    fig.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(OUT), dpi=150, bbox_inches="tight")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
