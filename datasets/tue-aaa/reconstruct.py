# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the tue-aaa dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/tue-aaa

B-mode reconstruction of in-vivo abdominal aortic aneurysm curved-array channel data.

The acquisition is a Verasonics C5-2v scan in steered diverging-wave mode (15
transmits, +/-12 deg). An ApplyWindow op tapers the axial axis so the far end of
the record, beyond the useful depth, does not leave a bright edge artifact at
the bottom of the sector.

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
import zea
from zea import Config, File, Pipeline
from zea.ops import (
    ApplyWindow,
    Beamform,
    Cast,
    Demodulate,
    EnvelopeDetect,
    LogCompress,
    Normalize,
)

HERE = Path(__file__).parent
CONFIG = HERE / "pipeline.yaml"

# Custom reconstruction parameters. These are passed to load_parameters and
# override (or fill in) values read from the HDF5 file.
PARAMETERS = {
    "grid_size_x": 580,
    "grid_size_z": 600,
    "xlims": [-0.1, 0.1],
    "zlims": [0.0065, 0.18],
    "f_number": 1.0,
    "dynamic_range": [-60, 0],
    "apply_lens_correction": True,
}

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/tue-aaa/data/AAA_subject11.hdf5"
OUT = HERE / "assets" / "AAApatient01_bmode.png"
HF_CONFIG = "hf://nvidia/Open-H-RF/tue-aaa/pipeline.yaml"
DEVICE = None  # CUDA device ID (e.g. 'cuda:0', 'auto:1', or 'cpu')


def build_pipeline() -> Pipeline:
    """Define the delay-and-sum beamforming pipeline in code."""
    return Pipeline(
        operations=[
            Cast(dtype="float32"),
            ApplyWindow(axis=-3, start=16, size=64, end=96, window_type="hanning"),
            Demodulate(),
            Beamform(beamformer="delay_and_sum"),
            EnvelopeDetect(),
            Normalize(),
            LogCompress(),
        ],
        validate=False,
    )


def write_config(pipeline: Pipeline, path: Path) -> None:
    """Serialize the pipeline and acquisition parameters to a YAML config file."""
    config = pipeline.to_config()
    config["parameters"] = PARAMETERS
    config.to_yaml(str(path))


def main():
    zea.init_device(device=DEVICE, verbose=False)

    # Define the beamforming pipeline in code, save it (with the acquisition
    # parameters) to pipeline.yaml, then load that YAML back in.
    write_config(build_pipeline(), CONFIG)
    config = Config.from_path(str(CONFIG))

    # Load file: read acquisition parameters (with config overrides) and raw RF data
    with File(str(ZEA_FILE)) as f:
        parameters = f.load_parameters(**config.parameters)
        raw = f.data.raw_data[0:1]  # (n_frames, n_tx, n_ax, n_el, 1) — RF

    # Build and run the beamforming pipeline loaded from pipeline.yaml
    pipeline = Pipeline.from_config(config)
    inputs = pipeline.prepare_parameters(parameters)
    outputs = pipeline(data=raw, **inputs)

    # Convert the output tensor to a NumPy array and save as PNG
    recon = keras.ops.convert_to_numpy(outputs["data"])  # (n_frames, grid_z, grid_x)
    image = zea.display.to_8bit(recon[0], dynamic_range=parameters.dynamic_range)

    zea.visualize.set_mpl_style()
    extent_mm = [v * 1e3 for v in parameters.extent_imshow]  # metres -> mm
    plt.imshow(
        image,
        extent=extent_mm,
        cmap="gray",
    )
    plt.xlabel("X (mm)")
    plt.ylabel("Z (mm)")
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(OUT), bbox_inches="tight", dpi=100)

    print(f"Reconstructed  : {recon.shape}")
    print(f"Saved          : {OUT}")


if __name__ == "__main__":
    main()
