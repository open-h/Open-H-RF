# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the twente-vortexflow dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/twente-vortexflow

B-mode reconstruction of single plane-wave flow-phantom channel data.

Each track has its own pipeline (``pipeline_<track>.yaml``). Both tracks use
the same delay-and-sum chain, defined in ``build_pipeline()`` and written to
both YAMLs together with ``PARAMETERS``; the script runs them on the chosen
file and saves the results side by side in one PNG. A second PNG pairs the
short-imaging-pulse B-mode with the synchronized camera image stored in the
same file.

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
from zea.ops import Beamform, Cast, Demodulate, EnvelopeDetect, LogCompress, Normalize

HERE = Path(__file__).parent

# 160 x 50 mm field of view on a 0.104 mm isotropic grid.
PARAMETERS = {
    "xlims": [-0.08, 0.08],
    "zlims": [0.05, 0.10],
    "grid_size_x": 1536,
    "grid_size_z": 480,
    "dynamic_range": [-50, 0],
}

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/twente-vortexflow/data/AcqData_PVoltage80_TVoltage3.4.hdf5"
CONFIGS = {  # track label -> pipeline YAML, written by write_config()
    "short imaging pulse": HERE / "pipeline_short_imaging_pulse.yaml",
    "chirp": HERE / "pipeline_chirp.yaml",
}
FRAME = 10
OUT = HERE / "assets" / "reference_bmode.png"
OUT_MAPPING = HERE / "assets" / "reference_mapping.png"  # B-mode + camera image
HF_CONFIGS = "hf://nvidia/Open-H-RF/twente-vortexflow/"  # where CONFIGS are published


def build_pipeline() -> Pipeline:
    """Define the delay-and-sum B-mode pipeline in code."""
    return Pipeline(
        operations=[
            Cast(dtype="float32"),
            Demodulate(),  # RF (n_ch=1) -> IQ before beamforming
            Beamform(),
            EnvelopeDetect(),
            Normalize(output_range=(0.0, 1.0)),
            LogCompress(),
        ],
    )


def write_config(pipeline: Pipeline, path: Path) -> None:
    """Serialize the pipeline and acquisition parameters to a YAML config file."""
    config = pipeline.to_config()
    config["parameters"] = PARAMETERS
    config.to_yaml(str(path))


def main():
    zea.init_device()

    # Define the pipeline in code, save it (with PARAMETERS) to each track's
    # YAML, then load those YAMLs back in so the shipped files are what runs.
    for path in CONFIGS.values():
        write_config(build_pipeline(), path)

    configs, parameters, raw = {}, {}, {}
    with File(ZEA_FILE) as f:
        for track in f.tracks:
            label = track.label
            configs[label] = Config.from_path(str(CONFIGS[label]))
            parameters[label] = track.load_parameters(**configs[label].parameters)
            raw[label] = track.data.raw_data[FRAME : FRAME + 1]
            if label == "short imaging pulse":
                camera = np.flipud(np.rot90(track.data.image.values[FRAME], 3))

    bmodes = {}
    for label, config in configs.items():
        pipeline = Pipeline.from_config(config)
        inputs = pipeline.prepare_parameters(parameters[label])
        outputs = pipeline(data=raw[label], **inputs)
        bmodes[label] = keras.ops.convert_to_numpy(outputs["data"])[0]

    def show_bmode(ax, label):
        p = parameters[label]
        vmin, vmax = p.dynamic_range
        extent = p.extent_imshow * 1e3
        ax.imshow(bmodes[label], cmap="gray", vmin=vmin, vmax=vmax, extent=extent, aspect="equal")
        ax.set_xlabel("Lateral [mm]")
        ax.set_ylabel("Depth [mm]")

    zea.visualize.set_mpl_style()
    fig, axes = plt.subplots(len(bmodes), 1, figsize=(6 * len(bmodes), 6))
    for ax, label in zip(axes, bmodes):
        show_bmode(ax, label)
        ax.set_title(f"Track: {label}\nFile: {Path(ZEA_FILE).name}, Frame {FRAME}")
    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"Saved {OUT}")

    fig, (ax_us, ax_cam) = plt.subplots(2, 1, figsize=(7, 10))
    show_bmode(ax_us, "short imaging pulse")
    ax_us.set_title(f"Ultrasound (short imaging pulse) - frame {FRAME}")
    ax_cam.imshow(camera, cmap="gray", aspect="equal")
    ax_cam.set_title(f"Camera image - frame {FRAME}")
    ax_cam.set_xlabel("X [px]")
    ax_cam.set_ylabel("Y [px]")
    fig.tight_layout()
    fig.savefig(OUT_MAPPING, dpi=150)
    plt.close(fig)
    print(f"Saved {OUT_MAPPING}")


if __name__ == "__main__":
    main()
