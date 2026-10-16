# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the oslo dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/oslo

B-mode reconstruction for every acquisition in the USTB channel-capture collection.

A single, geometry-agnostic script covers every acquisition in every
sub-dataset folder. How each one is reconstructed lives entirely in
``parameters.yaml``: the ``pipeline`` field picks the ``zea.Pipeline`` YAML and
the rest gives the display window and dynamic range, with no per-file logic
here. ``pipeline`` values:

  * ``scanline`` -- focused linear (FI) scans (line-by-line beamforming).
  * ``sector``   -- phased-array / steered focused sector scans (polar + scan convert).
  * ``iq``       -- baseband IQ data (no demodulation).
  * ``compound`` -- non-focused linear scans (plane-wave / diverging / STA).

Acquisitions with enough transmit events (>= 8) may additionally set
``refocus: true`` in ``parameters.yaml``. For those, a second REFoCUS
reconstruction (transmit-encoding recovery, Bottenus 2018) is written next to
the standard one as ``<name>_zea_refocus_bmode.png``. REFoCUS is not enabled for
single/few-transmit or synthetic transmit aperture acquisitions, where the
encoding inversion is ill-posed or undefined. The secondary pass is opt-in via
REFOCUS; by default only the standard reconstruction is produced.

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

HERE = Path(__file__).parent
PARAMETERS = zea.Config.from_path(str(HERE / "parameters.yaml"))
PIPELINE_YAML = {
    "scanline": "pipeline_scanline.yaml",
    "sector": "pipeline_sector.yaml",
    "iq": "pipeline_iq.yaml",
    "compound": "pipeline.yaml",
    "refocus": "pipeline_refocus.yaml",
    "refocus_sector": "pipeline_refocus_sector.yaml",
}

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
PATHS = "hf://nvidia/Open-H-RF/oslo/A_cardiac/Verasonics_P2-4_apical_four_chamber_subject_1.hdf5"
REFOCUS = False  # Also emit the secondary REFoCUS reconstruction where flagged for it


def reconstruct(
    path: str | Path, pipeline_key: str | None = None, suffix: str = "_zea_bmode.png"
) -> Path:
    """Reconstruct the first frame of a zea file and save a B-mode PNG.

    ``pipeline_key`` overrides the pipeline chosen in ``parameters.yaml`` (used to
    also render the REFoCUS variant); ``suffix`` names the output PNG.
    """
    cfg = PARAMETERS[Path(path).stem]
    config = zea.Config.from_path(str(HERE / PIPELINE_YAML[pipeline_key or cfg["pipeline"]]))
    is_scanline = bool(config.parameters.get("enable_scanline"))
    overrides = dict(config.parameters)
    if "dynamic_range" in cfg:
        overrides["dynamic_range"] = cfg["dynamic_range"]
    if "zlims" in cfg:
        overrides["zlims"] = tuple(v * 1e-3 for v in cfg["zlims"])
    if "xlims" in cfg:
        overrides["xlims"] = tuple(v * 1e-3 for v in cfg["xlims"])

    # Load everything we need from the file, then close it before processing.
    with zea.File(str(path)) as f:
        # polar_limits frames the shared (non-scanline) polar grid; scanline
        # imaging builds its own per-transmit rays and ignores it.
        if config.parameters.get("grid_type") == "polar" and not is_scanline:
            angles = np.asarray(f.scan.polar_angles, dtype=float)
            overrides["polar_limits"] = (float(angles.min()), float(angles.max()))
        parameters = f.load_parameters(**overrides)
        data = f.data.raw_data[:1]  # first frame

    pipeline = zea.Pipeline.from_config(config)
    outputs = pipeline(data=data, **pipeline.prepare_parameters(parameters))
    image = np.array(
        zea.display.to_8bit(
            np.squeeze(keras.ops.convert_to_numpy(outputs["data"])),
            dynamic_range=parameters.dynamic_range,
        )
    )

    zea.visualize.set_mpl_style()
    fig, ax = plt.subplots(figsize=(5, 6))
    if is_scanline:
        # Scanline geometry is defined by the beamforming grid.
        gx = np.asarray(parameters.grid[..., 0]) * 1e3
        gz = np.asarray(parameters.grid[..., 2]) * 1e3
        ax.pcolormesh(gx, gz, image, cmap="gray", shading="gouraud", vmin=0, vmax=255)
        ax.invert_yaxis()
    else:  # pixel-grid pipelines: regular imshow with the grid extent
        extent = np.array(parameters.extent_imshow) * 1e3
        ax.imshow(image, extent=extent, cmap="gray", aspect="equal")

    if "xlims" in cfg:
        ax.set_xlim(cfg["xlims"])
    if "zlims" in cfg:
        ax.set_ylim(cfg["zlims"][1], cfg["zlims"][0])
    ax.set_aspect("equal")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("z [mm]")
    ax.set_title(Path(path).stem, fontsize=8)

    out_path = HERE / "assets" / (Path(path).stem + suffix)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), bbox_inches="tight", dpi=110)
    plt.close(fig)
    print(f"{Path(path).parent.name}/{Path(path).name} -> {out_path.name}")
    return out_path


def main():
    zea.init_device()
    paths = [str(PATHS)] if PATHS else [str(p) for p in sorted(HERE.glob("*/*.hdf5"))]
    for path in paths:
        reconstruct(path)
        # Optional second reconstruction with REFoCUS transmit-encoding recovery
        # (opt-in via REFOCUS). Sector (phased-array) acquisitions need the polar
        # refocus pipeline so the sector geometry is preserved; every other geometry
        # uses the linear one.
        if not REFOCUS:
            continue
        cfg = PARAMETERS[Path(path).stem]
        if cfg.get("refocus"):
            refocus_key = "refocus_sector" if cfg["pipeline"] == "sector" else "refocus"
            reconstruct(path, pipeline_key=refocus_key, suffix="_zea_refocus_bmode.png")


if __name__ == "__main__":
    main()
