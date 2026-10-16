# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the unc-liver dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/unc-liver

B-mode reconstruction of simulated full synthetic aperture abdominal-wall channel data.

The transmit sequence runs on a curvilinear array, so beamforming happens on a
polar grid and scan conversion to a physical sector is part of the
reconstruction itself.

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

import matplotlib
import matplotlib.pyplot as plt
import zea
from mpl_toolkits.axes_grid1 import make_axes_locatable
from zea import Config, File, Pipeline
from zea.ops import (
    Beamform,
    Cast,
    Demodulate,
    EnvelopeDetect,
    LogCompress,
    Normalize,
    ScanConvert,
)

HERE = Path(__file__).parent
CONFIG = HERE / "pipeline.yaml"

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/unc-liver/data/fullwave_abdominal_wall_1283_reg.hdf5"
FRAME = 0
OUT = HERE / "assets" / "bmode.png"
SOS_MAP = False  # Also plot the ground-truth sos_map next to the B-mode (2 subplots)


def build_pipeline() -> Pipeline:
    """RF channel data -> log-compressed, scan-converted B-mode sector."""
    return Pipeline(
        [
            Cast(dtype="float32"),
            Demodulate(),
            Beamform(beamformer="delay_and_sum"),
            EnvelopeDetect(),
            Normalize(),
            LogCompress(),
            ScanConvert(),
        ],
    )


def build_parameters(
    r_min: float = 0.005, n_r: int = 640, dr: float = 1.0405405405405406e-04
) -> dict:
    """Beamforming + scan-conversion parameters for the polar grid the dataset's
    reference beamformed_data was formed on (640 radial x 128 lateral). ``zlims`` are
    depths below the array surface; ``distance_to_apex`` is left unset, so zea fits it
    from the probe's curvature.
    """
    return {
        "grid_type": "polar",
        "polar_limits": (-0.3, 0.3),
        "grid_size_z": 640,
        "grid_size_x": 128,
        "f_number": 2.0,
        "dynamic_range": (-60, 0),
        "fill_value": -60.0,
        "zlims": (r_min, r_min + n_r * dr),
    }


def write_config(pipeline: Pipeline, parameters: dict, path: Path) -> None:
    """Serialize the pipeline and acquisition parameters to a YAML config file."""
    config = pipeline.to_config()
    config["parameters"] = parameters
    config.to_yaml(str(path))


def scan_convert_map(
    data, params: zea.Parameters, frame: int = 0, fill_value: float = float("nan")
):
    """Scan-convert a single-channel map (e.g. a ground-truth material map) onto the
    same sector as the B-mode, using the same ``params``."""
    pipeline = Pipeline([ScanConvert()])
    inputs = pipeline.prepare_parameters(params)
    outputs = pipeline(
        data=data.astype("float32"),
        **{**inputs, "fill_value": fill_value},
        return_numpy=True,
    )
    return outputs["data"][frame]


def main() -> None:
    zea.visualize.set_mpl_style()
    zea.init_device()

    # Define the pipeline + parameters in code, save them (together) to pipeline.yaml,
    # then load that YAML back in -- pipeline.yaml is the single source of truth from
    # here on.
    write_config(build_pipeline(), build_parameters(), CONFIG)
    config = Config.from_path(str(CONFIG))
    pipeline = Pipeline.from_config(config)

    with File(str(ZEA_FILE)) as f:
        params = f.load_parameters(**config.parameters)
        raw = f.data.raw_data[:]

    inputs = pipeline.prepare_parameters(params)
    outputs = pipeline(**{pipeline.key: raw}, **inputs, return_numpy=True)
    bmode = outputs[pipeline.output_key][FRAME]
    extent = params.extent_imshow * 1e3

    if SOS_MAP:
        with File(str(ZEA_FILE)) as f:
            sos = f.data.sos_map.values[:]
        sos_sector = scan_convert_map(sos, params, frame=FRAME)
        sos_cmap = matplotlib.colormaps["viridis"].copy()
        sos_cmap.set_bad("black")

        fig, (ax_bmode, ax_sos) = plt.subplots(1, 2, figsize=(12, 7))

        im_bmode = ax_bmode.imshow(
            bmode,
            cmap="gray",
            vmin=params.dynamic_range[0],
            vmax=params.dynamic_range[1],
            extent=extent,
        )
        ax_bmode.set_aspect("equal")
        ax_bmode.set_title(f"B-mode (DAS), frame {FRAME}")
        ax_bmode.set_xlabel("Lateral position [mm]")
        ax_bmode.set_ylabel("Depth [mm]")
        cax_bmode = make_axes_locatable(ax_bmode).append_axes("right", size="5%", pad=0.08)
        fig.colorbar(im_bmode, cax=cax_bmode, label="dB")

        im_sos = ax_sos.imshow(sos_sector, cmap=sos_cmap, extent=extent)
        ax_sos.set_aspect("equal")
        ax_sos.set_title("Ground-truth speed of sound")
        ax_sos.set_xlabel("Lateral position [mm]")
        ax_sos.set_ylabel("Depth [mm]")
        cax_sos = make_axes_locatable(ax_sos).append_axes("right", size="5%", pad=0.08)
        fig.colorbar(im_sos, cax=cax_sos, label="m/s")
    else:
        fig, ax = plt.subplots(figsize=(6.5, 7))
        im = ax.imshow(
            bmode,
            cmap="gray",
            vmin=params.dynamic_range[0],
            vmax=params.dynamic_range[1],
            extent=extent,
        )
        ax.set_aspect("equal")
        ax.set_title(f"Fullwave abdominal wall B-mode (DAS), frame {FRAME}")
        ax.set_xlabel("Lateral position [mm]")
        ax.set_ylabel("Depth [mm]")
        cax = make_axes_locatable(ax).append_axes("right", size="5%", pad=0.08)
        fig.colorbar(im, cax=cax, label="dB")

    fig.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"Saved reconstruction to {OUT}")


if __name__ == "__main__":
    main()
