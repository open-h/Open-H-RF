# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the wpi dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/wpi

B-mode reconstruction of one rotation frame of eSAF rotational 3D channel data.

The linear array rotates 180 degrees about its axial axis, one degree per
frame, with a single normal plane-wave transmit per rotation frame. The
per-frame rotation angle is plotted next to the B-mode so the frame axis can be
interpreted.

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

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy. The default below is one of the 5
# measured-phantom scans, which show real reflector/reverberation texture --
# a more representative first look than the mostly-empty simulated point
# targets (see the probe x target grid in this dataset's README for those).
ZEA_FILE = "hf://nvidia/Open-H-RF/wpi/data/experiment__acq_exp_30mm.hdf5"
OUT = HERE / "assets" / "bmode.png"
HF_CONFIG = "hf://nvidia/Open-H-RF/wpi/pipeline.yaml"
FRAME = None  # rotation frame to beamform (default: closest to +-90 deg rotation)


def main():
    zea.init_device()

    # Load the whole processing chain + parameters from pipeline.yaml
    config = Config.from_path(str(CONFIG))

    # Load file: acquisition parameters (with config overrides), one raw RF frame,
    # and this dataset's special data — the probe rotation angle per frame.
    # Files are single-track (channel RF + scan); the paired eSAF label volume
    # lives in the custom group (custom/saf_bmode/{values,coordinates}, via f.custom).
    with File(str(ZEA_FILE)) as f:
        parameters = f.load_parameters(**config.parameters)
        # Rotation angle per frame lives in metadata/probe_pose (euler_xyz [rad],
        # nominal 1 Hz sampling — one pose per rotation frame): the array rotates
        # about its axial (z) axis, so the angle is the z Euler component.
        rotation_angles_deg = np.degrees(np.asarray(f.metadata.probe_pose.rotation)[:, 2]).ravel()
        n_frames = f.data.raw_data.shape[0]
        frame = FRAME
        if frame is None:  # default: frame where the probe has rotated ~90 deg
            # Select on rotation *magnitude* so signed encoder angles work too
            # (measured scans run 0 -> ~-180 deg; a plain |angle - 90| would pick
            # frame 0 for those). |abs(angle) - 90| picks the ~90 deg frame either way.
            frame = int(np.argmin(np.abs(np.abs(rotation_angles_deg) - 90.0)))
        raw = f.data.raw_data[frame : frame + 1]  # (1, n_tx, n_ax, n_el, 1) — RF

    print(f"raw_data frame : {raw.shape} ({n_frames} frames in file)")
    print(
        f"selected frame : {frame} @ {rotation_angles_deg[frame]:.1f} deg "
        f"(|rotation| {abs(rotation_angles_deg[frame]):.1f} deg)"
    )

    # Build and run the beamforming pipeline defined in pipeline.yaml
    pipeline = Pipeline.from_config(config)
    inputs = pipeline.prepare_parameters(parameters)
    outputs = pipeline(data=raw, **inputs)

    recon = keras.ops.convert_to_numpy(outputs["data"])  # (1, grid_z, grid_x), log-compressed dB
    image = zea.display.to_8bit(recon[0], dynamic_range=parameters.dynamic_range, pillow=False)

    # B-mode + rotation-angle plot (how to interpret the frame axis)
    zea.visualize.set_mpl_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), gridspec_kw={"width_ratios": [1, 1.3]})

    mm = plt.FuncFormatter(lambda v, _: f"{v * 1e3:.0f}")
    axes[0].imshow(image, extent=parameters.extent_imshow, cmap="gray", aspect="equal")
    axes[0].xaxis.set_major_formatter(mm)
    axes[0].yaxis.set_major_formatter(mm)
    axes[0].set(
        title=f"B-mode frame {frame} @ {rotation_angles_deg[frame]:.0f} deg",
        xlabel="Lateral [mm]",
        ylabel="Depth [mm]",
    )

    axes[1].plot(np.arange(n_frames), rotation_angles_deg, color="tab:blue")
    axes[1].axvline(frame, color="tab:red", linewidth=1.2, label="beamformed frame")
    axes[1].set(
        title="Probe rotation angle per frame\n(array rotates about its axial axis)",
        xlabel="Frame index",
        ylabel="Rotation angle [deg]",
    )
    axes[1].grid(True, color="0.85", linewidth=0.8)
    axes[1].legend(loc="upper left", fontsize=8, frameon=False)

    fig.suptitle(f"Open-H-RF eSAF rotational 3D US — {Path(ZEA_FILE).name}", y=0.98)
    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(OUT), bbox_inches="tight", dpi=150)

    print(f"Reconstructed  : {recon.shape}")
    print(f"Saved          : {OUT}")


if __name__ == "__main__":
    main()
