#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the ubc/module_C dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/ubc/module_C

B-mode reconstruction and scan conversion of one frame of synthetic channel data.

zea builds the one-line-per-transmit grid and the one-hot aligned transmit
mask, then runs RF demodulation, delay-and-sum, envelope detection,
normalization and log compression. A BK-like virtual-apex display
approximation is applied afterwards with zea's scan conversion; its parameters
are inferred from the available BK viewport rather than recovered from
manufacturer calibration. The stored source IQ, BK video and camera streams are
never loaded by this script.

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

import hdf5plugin  # noqa: F401 - registers compressed HDF5 filters
import keras
import matplotlib.pyplot as plt
import numpy as np
import zea
from mpl_toolkits.axes_grid1 import make_axes_locatable
from zea.ops import Beamform, Cast, Demodulate, EnvelopeDetect, LogCompress, Normalize

HERE = Path(__file__).resolve().parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/ubc/module_C/acquisitions/session_01/session_01_f1306.hdf5"
OUT = HERE / "assets" / "reconstruct_f1306_bk_scanconverted.png"
FRAME = 0

NORMALIZATION_PERCENTILE = 99.5
DISPLAY_FLOOR_DB = -50.0
DISPLAY_PADDING_FRACTION = 0.04
LINE_DEPTH_MIN_M = 0.1e-3
GRID_SIZE_Z = 704
# These are display-model parameters inferred from the available BK viewport,
# not recovered BK manufacturer calibration or the synthetic receive aperture.
DISPLAY_SOURCE_APERTURE_M = 31.1e-3
DISPLAY_MAX_STEERING_RAD = 0.26111900806427


def build_pipeline() -> zea.Pipeline:
    """Return the zea pipeline used for this reference reconstruction.

    Cast -> Demodulate -> Beamform(...) -> EnvelopeDetect -> Normalize
    -> LogCompress
    """
    return zea.Pipeline(
        operations=[
            # The cast is explicit because the stored channel data is int16.
            Cast(dtype="float32"),
            # Demodulate real RF to complex baseband IQ.
            Demodulate(),
            # Receive DAS with zea's built-in one-transmit-per-scanline mask.
            Beamform(beamformer="delay_and_sum", enable_aligned_apodization=True),
            EnvelopeDetect(),
            Normalize(output_range=[0.0, 1.0], percentile=NORMALIZATION_PERCENTILE),
            LogCompress(),
        ]
    )


def reconstruct_scanlines(zea_path, frame: int = 0, pipeline=None):
    """Run scanline DAS on one frame, using only the stored ``raw_data``."""
    zea.init_device()

    with zea.File(str(zea_path)) as f:
        # Reconstruction depth travels with the acquisition, as a custom element.
        depth_m = float(f.custom.source_provenance.imaging_depth_m.data)
        parameters = f.load_parameters(
            enable_scanline=True,
            grid_type="cartesian",
            zlims=[LINE_DEPTH_MIN_M, depth_m],
            grid_size_z=GRID_SIZE_Z,
            dynamic_range=[DISPLAY_FLOOR_DB, 0.0],
            f_number=0.0,
            apply_lens_correction=False,
        )
        raw_data = f.data.raw_data[frame : frame + 1]

    pipeline = pipeline or build_pipeline()
    inputs = pipeline.prepare_parameters(parameters)
    # return_numpy=True uses keras.ops.convert_to_numpy for multi-backend support.
    outputs = pipeline(**{pipeline.key: raw_data}, **inputs, return_numpy=True)
    scanlines = np.squeeze(outputs[pipeline.output_key][0])
    return scanlines, depth_m


def scan_convert_bk_style(scanlines, depth_m: float):
    """Apply the documented BK-like zea virtual-apex display approximation.

    Returns the scan-converted sector and its (x, z) display limits in metres.
    """
    virtual_apex_m = DISPLAY_SOURCE_APERTURE_M / (2.0 * np.tan(DISPLAY_MAX_STEERING_RAD))
    radial_step_m = (depth_m - LINE_DEPTH_MIN_M) / (scanlines.shape[0] - 1)
    sector, display_parameters = zea.display.scan_convert_2d(
        scanlines,
        rho_range=(virtual_apex_m + LINE_DEPTH_MIN_M, virtual_apex_m + depth_m),
        # The stored scanline order is laterally opposite to the BK viewport.
        theta_range=(DISPLAY_MAX_STEERING_RAD, -DISPLAY_MAX_STEERING_RAD),
        resolution=radial_step_m,
        fill_value=DISPLAY_FLOOR_DB,
        order=1,
        distance_to_apex=virtual_apex_m,
    )
    # scan_convert_2d returns backend tensors; pull them off the device here.
    sector = keras.ops.convert_to_numpy(sector)
    x_lim = keras.ops.convert_to_numpy(display_parameters["x_lim"])
    z_lim = keras.ops.convert_to_numpy(display_parameters["z_lim"])
    resolution = float(keras.ops.convert_to_numpy(display_parameters["resolution"]))

    # zea returns a tight Cartesian box. Add a border so the complete fan stays
    # visible without cropping or resampling any reconstructed sample.
    pad_z = max(1, int(np.ceil(sector.shape[0] * DISPLAY_PADDING_FRACTION)))
    pad_x = max(1, int(np.ceil(sector.shape[1] * DISPLAY_PADDING_FRACTION)))
    sector = np.pad(
        sector,
        ((pad_z, pad_z), (pad_x, pad_x)),
        mode="constant",
        constant_values=DISPLAY_FLOOR_DB,
    )
    x_lim = [x_lim[0] - pad_x * resolution, x_lim[1] + pad_x * resolution]
    z_lim = [z_lim[0] - pad_z * resolution, z_lim[1] + pad_z * resolution]
    return sector, x_lim, z_lim


def save_bmode(sector, x_lim, z_lim, output_path: Path) -> None:
    """Save the full scan-converted sector with truthful physical axes."""
    x_limits_mm = np.asarray(x_lim, dtype=float) * 1e3
    z_limits_mm = np.asarray(z_lim, dtype=float) * 1e3

    output_path.parent.mkdir(parents=True, exist_ok=True)
    zea.visualize.set_mpl_style()
    fig, axis = plt.subplots(figsize=(7.2, 8.0))
    image = axis.imshow(
        sector,
        cmap="gray",
        vmin=DISPLAY_FLOOR_DB,
        vmax=0.0,
        aspect="equal",
        extent=[x_limits_mm[0], x_limits_mm[1], z_limits_mm[1], z_limits_mm[0]],
    )
    axis.set_ylim(z_limits_mm[1], z_limits_mm[0])
    axis.set_title("UBC Module C session 01: zea DAS + BK-like scan conversion")
    axis.set_xlabel("Lateral position x (mm)")
    axis.set_ylabel("Depth z (mm)")
    cax = make_axes_locatable(axis).append_axes("right", size="5%", pad=0.05)
    fig.colorbar(image, cax=cax, label="Normalized log envelope (dB)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    scanlines, depth_m = reconstruct_scanlines(ZEA_FILE, FRAME)
    sector, x_lim, z_lim = scan_convert_bk_style(scanlines, depth_m)
    save_bmode(sector, x_lim, z_lim, OUT)
    print(f"Scanline B-mode: {scanlines.shape}; {scanlines.min():.3f}..{scanlines.max():.3f} dB")
    print(f"Scan converted : {sector.shape}; depth={depth_m * 1e3:.1f} mm")
    print(f"Saved          : {OUT}")


if __name__ == "__main__":
    main()
