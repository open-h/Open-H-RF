# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the colorado-boulder dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/colorado-boulder

B-mode reconstruction of tracked swept synthetic aperture phantom channel data.

The probe is swept across the phantom while its pose is tracked, so each frame
is acquired from a different position. A custom ``ApplyProbePose`` operation,
defined in this module and placed before the beamformer, rotates and translates
the probe geometry and transmit origins by the tracked pose of the current
frame, bringing every frame into a common coordinate system before compounding.

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
from keras import ops
from mpl_toolkits.axes_grid1 import make_axes_locatable
from zea import Pipeline
from zea.internal.registry import ops_registry
from zea.ops import (
    Beamform,
    Cast,
    Demodulate,
    EnvelopeDetect,
    LogCompress,
    Map,
    Normalize,
    Operation,
)
from zea.ops.keras_ops import ExpandDims, Squeeze, Sum

HERE = Path(__file__).parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/colorado-boulder/Sub-dataset-1/sub-phantom2d_01_tracked-ssa.hdf5"
CONFIG = HERE / "pipeline.yaml"  # written by build_pipeline() below; this is what the run loads
OUT = HERE / "ssa_bmode.png"
HF_CONFIG = "hf://nvidia/Open-H-RF/colorado-boulder/pipeline.yaml"  # where CONFIG is published
FRAME_SPACING = 1e-3  # select tracked frames every 1 mm along the sweep


@ops_registry("apply_probe_pose")
class ApplyProbePose(Operation):
    """Apply the tracked probe pose of one frame before beamforming.

    Rotates and translates the probe geometry and transmit origins by the pose
    of the current frame, so that every frame shares one coordinate system. The
    per-frame pose is sliced off ``probe_translation`` / ``probe_rotation`` by
    the enclosing :class:`Map`.

    This operation lives here rather than in zea, so a ``pipeline.yaml`` naming
    ``apply_probe_pose`` only resolves once this module has been imported.
    """

    def __init__(self, **kwargs):
        super().__init__(additional_output_keys=["probe_geometry", "transmit_origins"], **kwargs)

    def call(self, probe_translation, probe_rotation, probe_geometry, transmit_origins, **kwargs):
        t = ops.reshape(ops.cast(probe_translation, "float32"), (3,))
        q = ops.reshape(ops.cast(probe_rotation, "float32"), (4,))
        q = q / (ops.sqrt(ops.sum(q * q)) + 1e-12)

        x, y, z, w = q[0], q[1], q[2], q[3]
        R = ops.stack(
            [
                ops.stack(
                    [
                        1.0 - 2.0 * (y * y + z * z),
                        2.0 * (x * y - z * w),
                        2.0 * (x * z + y * w),
                    ],
                    axis=0,
                ),
                ops.stack(
                    [
                        2.0 * (x * y + z * w),
                        1.0 - 2.0 * (x * x + z * z),
                        2.0 * (y * z - x * w),
                    ],
                    axis=0,
                ),
                ops.stack(
                    [
                        2.0 * (x * z - y * w),
                        2.0 * (y * z + x * w),
                        1.0 - 2.0 * (x * x + y * y),
                    ],
                    axis=0,
                ),
            ],
            axis=0,
        )

        probe_geometry = ops.matmul(ops.cast(probe_geometry, "float32"), ops.transpose(R)) + t
        transmit_origins = ops.matmul(ops.cast(transmit_origins, "float32"), ops.transpose(R)) + t

        return {
            self.output_key: kwargs[self.key],
            "probe_geometry": probe_geometry,
            "transmit_origins": transmit_origins,
        }


def build_pipeline() -> Pipeline:
    """Define the tracked swept synthetic aperture beamforming pipeline in code.

    ``Map`` beamforms one tracked frame at a time, each with its own pose. The
    stacked frames are coherently summed before envelope detection, which is
    what makes this a synthetic aperture rather than incoherent compounding.
    """
    return Pipeline(
        operations=[
            Map(
                operations=[
                    Squeeze(axis=0),
                    Cast(dtype="float32"),
                    Demodulate(),
                    ApplyProbePose(),
                    Beamform(beamformer="delay_and_sum", enable_pfield=False),
                    ExpandDims(axis=0),  # restore the frame axis so Map can stack
                ],
                argnames=["data", "probe_translation", "probe_rotation"],
                batch_size=1,
            ),
            Sum(axis=0),
            EnvelopeDetect(),
            Normalize(),
            LogCompress(),
        ],
        with_batch_dim=False,
    )


def select_sweep_frames(x_positions, spacing):
    """Indices of the frames closest to a uniform ``spacing`` along the sweep."""
    step = spacing * np.sign(x_positions[-1] - x_positions[0])
    targets = np.arange(x_positions[0], x_positions[-1] + 0.5 * step, step, dtype=np.float32)
    return np.array([np.argmin(np.abs(x_positions - target)) for target in targets])


def main():
    zea.init_device(verbose=False)

    # Define the pipeline in code, save it to pipeline.yaml, then load it back.
    build_pipeline().to_yaml(str(CONFIG))
    pipeline = Pipeline.from_path(str(CONFIG))

    # Load acquisition parameters, raw RF data and the tracked probe pose
    with zea.File(ZEA_FILE) as f:
        parameters = f.load_parameters(
            xlims=(-0.05, 0.05),
            zlims=(0.01, 0.13),
            ylims=(0.0, 0.0),
            f_number=0.75,
            dynamic_range=(-50, 0),
        )
        raw_data = f.data.raw_data[:]
        probe_translation = f.metadata.probe_pose.translation[:]
        probe_rotation = f.metadata.probe_pose.rotation[:]

    # Thin the sweep to a uniform spacing and centre it on the reconstruction grid
    frames = select_sweep_frames(probe_translation[:, 0], FRAME_SPACING)
    probe_translation = probe_translation - np.mean(probe_translation[frames], axis=0)

    bmode = pipeline(
        data=raw_data[frames],
        probe_translation=probe_translation[frames],
        probe_rotation=probe_rotation[frames],
        **pipeline.prepare_parameters(parameters),
    )["data"]

    # Save PNG
    zea.visualize.set_mpl_style()
    plt.figure(figsize=(6, 7))
    plt.imshow(
        np.squeeze(ops.convert_to_numpy(bmode)),
        cmap="gray",
        extent=parameters.extent_imshow * 1e3,
        aspect="auto",
    )
    plt.xlabel("x [mm]")
    plt.ylabel("z [mm]")
    plt.title("Tracked SSA B-mode")
    cax = make_axes_locatable(plt.gca()).append_axes("right", size="5%", pad=0.05)
    plt.gcf().colorbar(plt.gci(), cax=cax, label="dB")
    plt.tight_layout()
    plt.savefig(str(OUT), dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
