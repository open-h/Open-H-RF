# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the dartmouth-uct dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/dartmouth-uct

Delay-and-sum reflectivity reconstruction of ring-array USCT channel data.

The transmits are individual point sources firing in turn rather than a
wavefront steered from the receive aperture, so the standard
``zea.ops.Beamform`` delay model does not apply; ``zea.ops.USCTReflectivityDAS``
is the dedicated operation for this geometry.

Both sub-datasets reconstruct with the same pipeline -- the 2D full-ring (256
transmits) and the 3D ring (64 transmits) -- and only the compounding differs
(see COMPOUNDING). The imaging grid defaults to the footprint and resolution of
the ground-truth sound-speed map stored in the file, so the reconstruction is
directly comparable with the ground truth pixel for pixel. Set SOS_MAP to feed
that map to the same operation, replacing the constant-c delays with a
straight-ray integral of the local slowness.

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
from zea.ops import (
    Cast,
    LogCompress,
    Normalize,
    PatchedGrid,
    ReshapeGrid,
    USCTReflectivityDAS,
)

HERE = Path(__file__).parent
CONFIG = HERE / "pipeline.yaml"

# The ring lies in the XZ imaging plane, so the reconstruction grid is Cartesian
# and centred on the ring. `ylims` is pinned to zero: the ring images a single
# plane, so the grid must stay 2D (left unset, zea would infer an elevation
# extent from the probe and build a volume).
PARAMETERS = {
    "grid_type": "cartesian",
    "ylims": [0.0, 0.0],
    "dynamic_range": [-40, 0],
}

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/dartmouth-uct/data/2d/phantom_179604449_z200.hdf5"
FOV = None  # square field of view [m] (default: the ground-truth map footprint)
NUM_PIXELS = None  # output image is num_pixels x num_pixels (default: ground-truth resolution)
SOS_MAP = False  # use the ground-truth sound-speed map for straight-ray corrected delays
COMPOUNDING = None  # transmit compounding (default: coherent for 2D, incoherent for 3D)
DEVICE = None  # CUDA device ID (e.g. 'cuda:0', 'auto:1', or 'cpu')


def build_pipeline(compounding: str = "coherent") -> Pipeline:
    """Define the USCT delay-and-sum reflectivity pipeline in code."""
    return Pipeline(
        operations=[
            Cast(dtype="float32"),
            # Every pixel is independent, so reconstruct the grid in patches to
            # bound peak memory, then reshape the flat result to an image. The
            # 5-cycle 1.5 MHz toneburst is ~3.3 us long; a 2.5 us guard (~0.75 of
            # a pulse) past the direct arrival rejects through-transmission while
            # keeping backscatter from near the ring.
            PatchedGrid(
                operations=[
                    USCTReflectivityDAS(
                        tx_chunk=4, transmission_guard_s=2.5e-6, compounding=compounding
                    ),
                ]
            ),
            ReshapeGrid(),
            Normalize(),
            LogCompress(),
        ],
        # Python-level loops over transmit chunks: not jittable.
        jit_options="pipeline",
        # One acquisition at a time: `data` is (n_tx, ...) with no leading frame
        # axis. The pipeline propagates this to every operation it contains.
        with_batch_dim=False,
    )


def write_config(pipeline: Pipeline, path: Path) -> None:
    """Serialize the pipeline and reconstruction parameters to a YAML config file."""
    config = pipeline.to_config()
    config["parameters"] = PARAMETERS
    config.to_yaml(str(path))


def check_ring_in_imaging_plane(file: File):
    """The ring must lie in the XZ imaging plane (y = elevation), as zea expects.

    A ring stored in the XY plane still reconstructs — every element projects onto
    a line — but yields a meaningless image, and lets zea infer an elevation extent
    from the ring, turning the grid into a volume that exhausts GPU memory. Both
    are far easier to understand as an error here.
    """
    probe_geometry = file.probe.probe_geometry[:]
    elevation = np.abs(probe_geometry[:, 1]).max()
    in_plane = np.abs(probe_geometry[:, [0, 2]]).max()
    if elevation > 0.01 * in_plane:
        raise ValueError(
            f"{file.path}: probe_geometry spans {2 * elevation * 1e3:.1f} mm in y "
            f"(elevation) against {2 * in_plane * 1e3:.1f} mm in-plane, so the ring is "
            "not in the XZ imaging plane. Run fix_uploaded_files.py (see FEEDBACK.md)."
        )


def ground_truth(file: File):
    """Ground-truth maps and their in-plane (x, z) axes, read from the zea file."""
    coords = file.data.sos_map.coordinates[:]  # (n_z, n_x, 3)
    return {
        "sos": file.data.sos_map.values[0],
        "attenuation": file.data.attenuation_map.values[0],
        "x": coords[0, :, 0],
        "z": coords[:, 0, 2],
    }


def ring_radius(file: File):
    """Radius of the transducer ring [m], from the in-plane element positions."""
    probe_geometry = file.probe.probe_geometry[:]
    return float(np.linalg.norm(probe_geometry[:, [0, 2]], axis=-1).mean())


def grid_limits(gt, radius, fov=None, num_pixels=None):
    """Imaging grid: the ground-truth footprint, clipped to the ring interior.

    The 3D ground-truth maps are wider than the ring (232 mm across a 222 mm ring),
    so imaging their full footprint would put the transducer ring itself inside the
    grid, where it reconstructs as a bright ring that dominates the normalization
    and buries the phantom. A square of half-width `h` has corners at `h*sqrt(2)`,
    so keeping `h <= 0.9 * radius / sqrt(2)` leaves a 10% margin to the elements.
    The 2D maps are already well inside their ring, so this leaves them untouched.
    """
    half = min(np.abs(gt["x"]).max(), np.abs(gt["z"]).max(), 0.636 * radius)
    if fov is not None:
        half = fov / 2
    if num_pixels is None:
        # Keep the ground-truth pixel pitch, so the panels stay comparable.
        num_pixels = round(2 * half / (gt["x"][1] - gt["x"][0])) + 1
    return {
        "xlims": [-half, half],
        "zlims": [-half, half],
        "grid_size_x": num_pixels,
        "grid_size_z": num_pixels,
    }


def crop_to_grid(gt, grid):
    """Crop the ground-truth maps to the imaging grid, for a like-for-like figure."""
    keep_x = (gt["x"] >= grid["xlims"][0]) & (gt["x"] <= grid["xlims"][1])
    keep_z = (gt["z"] >= grid["zlims"][0]) & (gt["z"] <= grid["zlims"][1])
    return {
        "sos": gt["sos"][np.ix_(keep_z, keep_x)],
        "attenuation": gt["attenuation"][np.ix_(keep_z, keep_x)],
        "x": gt["x"][keep_x],
        "z": gt["z"][keep_z],
    }


def main():
    suffix = "_sos.png" if SOS_MAP else ".png"
    output_path = HERE / "assets" / (Path(ZEA_FILE).stem + suffix)

    zea.init_device(device=DEVICE, verbose=True)

    # Load file: acquisition parameters (with config overrides) and raw RF data.
    with File(str(ZEA_FILE)) as f:
        check_ring_in_imaging_plane(f)
        gt_full = ground_truth(f)
        grid = grid_limits(gt_full, ring_radius(f), FOV, NUM_PIXELS)
        gt = crop_to_grid(gt_full, grid)
        compounding = COMPOUNDING
        if compounding is None:
            compounding = "incoherent" if "3D" in f.probe.name else "coherent"

        # Define the pipeline in code, save it (with the reconstruction
        # parameters) to pipeline.yaml, then load that YAML back in.
        write_config(build_pipeline(compounding), CONFIG)
        config = Config.from_path(str(CONFIG))

        parameters = f.load_parameters(**config.parameters, **grid)
        raw = f.data.raw_data[0]  # (n_tx, n_ax, n_el, 1) — RF, one frame

    # SoS-corrected delays: pass the ground-truth map (uncropped, so rays that
    # leave the imaging grid still see the phantom) as call-time data. This is
    # a runtime input, not a pipeline parameter, so pipeline.yaml is unchanged.
    sos_inputs = {}
    if SOS_MAP:
        sos_inputs = {
            "sos_map": gt_full["sos"].astype(np.float32),
            "sos_grid_x": gt_full["x"].astype(np.float32),
            "sos_grid_z": gt_full["z"].astype(np.float32),
        }

    # Build and run the pipeline loaded from pipeline.yaml.
    pipeline = Pipeline.from_config(config)
    inputs = pipeline.prepare_parameters(parameters, **sos_inputs)

    zea.log.info("Running pipeline on RF data...")
    outputs = pipeline(data=raw, **inputs, return_numpy=True)

    recon = outputs["data"]  # (grid_z, grid_x) — log-compressed reflectivity

    # The ground-truth maps share the reconstruction's frame, so the reflective
    # skin boundary should trace the ground-truth contour panel for panel.
    gt_extent = [gt["x"].min(), gt["x"].max(), gt["z"].max(), gt["z"].min()]

    zea.visualize.set_mpl_style()
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    recon_title = "DAS reflectivity [dB]" + (" (SoS-corrected)" if SOS_MAP else "")
    panels = [
        (recon, recon_title, "gray", parameters.extent_imshow),
        (gt["sos"], "Ground-truth sound speed [m/s]", "viridis", gt_extent),
        (gt["attenuation"], "Ground-truth attenuation [dB/m/Hz]", "magma", gt_extent),
    ]
    for ax, (image, title, cmap, extent) in zip(axes, panels):
        handle = ax.imshow(image, cmap=cmap, extent=extent)
        ax.set_title(title)
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Z (m)")
        # Tie the colorbar axes to the image axes so it matches the panel height.
        cax = make_axes_locatable(ax).append_axes("right", size="5%", pad=0.05)
        fig.colorbar(handle, cax=cax)
    fig.suptitle(Path(ZEA_FILE).name)
    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), bbox_inches="tight", dpi=100)

    print(f"Reconstructed  : {recon.shape}")
    print(f"Saved          : {output_path}")


if __name__ == "__main__":
    main()
