# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the tumunich dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/tumunich

B-mode reconstruction of walking-aperture robotic ultrasound sweep channel data.

Each steering angle is acquired three times with the aperture walked across the
array, so a reconstruction has to compound all 21 acquisitions to cover the full
probe. Transmit uses a 64-element aperture; receive is multiplexed into three
42/44-element blocks that tile the 128 elements. The grey levels reproduce the
Verasonics display mapping, making them directly comparable to the VSX B-mode
stored in the file as ``data/image``.

Requires zea>=0.1.7 (https://github.com/tue-bmd/zea), the library that does the
ultrasound processing here, together with one of its Keras backends (JAX,
PyTorch or TensorFlow). Installation instructions are at
https://zea.readthedocs.io/en/latest/installation.html.

Usage:
    uv run python reconstruct.py
"""

import os

os.environ.setdefault("KERAS_BACKEND", "jax")
os.environ.setdefault("MPLBACKEND", "Agg")

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import zea
from keras import ops
from zea.internal.core import DataTypes
from zea.internal.registry import ops_registry
from zea.ops import (
    BandPassFilter,
    Cast,
    DelayAndSum,
    Demodulate,
    EnvelopeDetect,
    LogCompress,
    Normalize,
    PatchedGrid,
    ReshapeGrid,
    TOFCorrection,
)
from zea.ops.base import Operation

HERE = Path(__file__).parent
CONFIG = HERE / "pipeline.yaml"  # written by build_pipeline(); this is what the run loads
HF_CONFIG = "hf://nvidia/Open-H-RF/tumunich/pipeline.yaml"  # where CONFIG is published


PARAMETERS = {
    "f_number": 1.155,
    "apply_lens_correction": True,
}

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/tumunich/data/cirs_phantom/synth_apert_sweep_1.hdf5"
OUT = HERE / "assets" / f"{Path(ZEA_FILE).stem}_reconstructed.png"
FRAME = 0  # Zero-based frame index to reconstruct
DYNAMIC_RANGE = [-40, 0]  # dB range shown

# Leading fast-time samples to blank before beamforming. Samples 0-1 are transmit
# pulse feedthrough clipped at the ADC rail: the same value on every driven element
# (~32000 against a typical echo of ~284), on exactly the elements that transmit.
FEEDTHROUGH_SAMPLES = 2


def coords_to_imshow_mm(coords):
    """open-h-rf per-pixel coordinates (z, x, 3), last axis [x, y, z] in metres
    -> mpl imshow extent [left, right, bottom, top] in mm."""
    x = coords[..., 0]
    z = coords[..., 2]
    return [x.min() * 1e3, x.max() * 1e3, z.max() * 1e3, z.min() * 1e3]


# These ops are defined here, not in zea: a pipeline.yaml naming them resolves
# only once this module is imported. See https://github.com/open-h/Open-H-RF
@ops_registry("power_compress")
class PowerCompress(Operation):
    """Power (gamma) compression: raises the normalised envelope to ``exponent``."""

    def __init__(self, exponent=0.5, **kwargs):
        super().__init__(
            input_data_type=DataTypes.ENVELOPE_DATA,
            output_data_type=DataTypes.IMAGE,
            **kwargs,
        )
        self.exponent = exponent

    def call(self, **kwargs):
        data = kwargs[self.key]
        return {self.output_key: ops.power(data, self.exponent)}


def build_pipeline(passband):
    return zea.Pipeline(
        operations=[
            Cast(dtype="float32"),
            BandPassFilter(passband=passband),
            Demodulate(),
            zea.Pipeline(
                operations=[
                    PatchedGrid(operations=[TOFCorrection(), DelayAndSum()]),
                    ReshapeGrid(),
                ],
                validate=True,
            ),
            EnvelopeDetect(),
            Normalize(),
            LogCompress(),
        ],
    )


def reconstruct_frame(f, frame):
    """Beamform one frame onto the axial extent of the stored B-mode.

    Compounds all transmits: each steering angle is acquired three times with
    the aperture walked across the array, so every acquisition is needed to
    cover the full probe.
    """
    n_tx = f.scan.polar_angles.shape[0]
    selected = list(range(n_tx))
    raw = np.asarray(f.data.raw_data[frame : frame + 1, selected]).copy()
    raw[:, :, :FEEDTHROUGH_SAMPLES] = 0

    sound_speed = float(np.asarray(f.scan.sound_speed))
    initial_times = np.asarray(f.scan.initial_times, dtype=np.float64)
    start_depth = float(initial_times[0]) * sound_speed / 2

    display_coords = f.data.image.coordinates[:]
    end_depth = float(display_coords[..., 2].max())
    display_axial_spacing = display_coords[1, 0, 2] - display_coords[0, 0, 2]
    img_coords = display_coords[round(start_depth / display_axial_spacing) :].copy()
    img_coords[..., 2] = np.linspace(start_depth, end_depth, img_coords.shape[0])[:, None]

    parameters = {
        **PARAMETERS,
        "xlims": [float(img_coords[..., 0].min()), float(img_coords[..., 0].max())],
        "zlims": [float(img_coords[..., 2].min()), float(img_coords[..., 2].max())],
        "selected_transmits": selected,
    }

    center_frequency = float(np.asarray(f.scan.center_frequency).reshape(-1)[0])
    bandwidth_fraction = float(np.asarray(f.probe.probe_bandwidth_percent).reshape(-1)[0]) / 100.0
    passband = (
        center_frequency * (1 - bandwidth_fraction / 2),
        center_frequency * (1 + bandwidth_fraction / 2),
    )

    config = build_pipeline(passband).to_config()
    config["parameters"] = parameters
    config.to_yaml(str(CONFIG))

    config = zea.Config.from_path(str(CONFIG))
    pipeline = zea.Pipeline.from_config(config)
    params = f.load_parameters(**config.parameters)
    inputs = pipeline.prepare_parameters(params)
    generated = pipeline(
        data=raw,
        **inputs,
        return_numpy=True,
    )["data"][0]

    # The grid starts at the imaging start depth, so pad the near field back on
    # to line the result up with the stored Verasonics B-mode.
    axial_spacing = (end_depth - start_depth) / (generated.shape[0] - 1)
    generated = np.pad(
        generated,
        ((round(start_depth / axial_spacing), 0), (0, 0)),
        constant_values=DYNAMIC_RANGE[0],
    )
    return generated


def main():

    zea.init_device()

    with zea.File(str(ZEA_FILE)) as f:
        display_coords = f.data.image.coordinates[:]
        generated = reconstruct_frame(f, FRAME)
        print(f"Reconstructed: {generated.shape}")

    extent = coords_to_imshow_mm(display_coords)
    zea.visualize.set_mpl_style()
    fig, ax = plt.subplots(figsize=(6, 8))

    ax.imshow(
        generated,
        aspect="equal",
        cmap="gray",
        extent=extent,
        vmin=DYNAMIC_RANGE[0],
        vmax=DYNAMIC_RANGE[1],
    )
    ax.set_xlabel("Lateral [mm]")
    ax.set_ylabel("Depth [mm]")
    plt.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
