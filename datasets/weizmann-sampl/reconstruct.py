# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the weizmann-sampl dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/weizmann-sampl

B-mode reconstruction of focused ray-line thyroid channel data.

Three modes, selected by the constants below:

  1. Single-scan mode (``ZEA_FILE`` set): beamform frame ``FRAME`` of that one file
     and save it as a PNG. This is the default.
  2. Random grid mode (``ZEA_FILE = None``): pick ``N_SCANS`` random scans from
     ``DATA_DIR``, ``N_FRAMES`` random frames from each (never below
     ``MIN_FRAME``), and save a single PNG grid (rows = scans, columns = frames).
  3. Systematic grid mode (``ZEA_FILE = None`` and ``SYSTEMATIC = True``): fixed,
     evenly-spaced frame numbers (``FRAME_START``/``FRAME_STEP``/``FRAME_COUNT``,
     1-indexed to match the raw rawdata_{frame}of4 numbering) for the patients
     named in ``PATIENTS``. Rows = patients, columns = frame numbers.

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

import random
from pathlib import Path

import keras
import matplotlib.pyplot as plt
import zea
from zea import Config, File, Pipeline

HERE = Path(__file__).parent
CONFIG = HERE / "pipeline.yaml"

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/weizmann-sampl/data/30_1.hdf5"
DATA_DIR = HERE / "subjects"  # HDF5 files to sample from (grid modes, used when ZEA_FILE is None)
OUT = None
# Frame 0 is unsettled: a near-field transient saturates the log compression
# and blacks out everything below ~10 mm.
FRAME = 20  # Frame index (single-scan mode)
N_SCANS = 3  # Number of random scans (grid mode)
N_FRAMES = 4  # Random frames per scan (grid mode)
SEED = None  # Random seed (grid mode)
MIN_FRAME = 4  # Lowest frame index per scan (random grid mode); skips settling
SYSTEMATIC = False  # Systematic grid mode: fixed frame numbers per patient (see PATIENTS)
PATIENTS = None  # Comma-separated patient IDs, e.g. '1_1,10_1' (systematic mode)
FRAME_START = 1  # First frame number, 1-indexed (systematic mode)
FRAME_STEP = 5  # Step between frame numbers (systematic mode)
FRAME_COUNT = 15  # Number of frames to sample (systematic mode)


def reconstruct_single(config):
    output_path = OUT or HERE / "assets" / f"{Path(ZEA_FILE).stem}.png"

    with File(str(ZEA_FILE)) as f:
        n_frames_available = f.data.raw_data.shape[0]
        frame = FRAME if FRAME is not None else 0
        # apply_lens_correction (pipeline.yaml) + the probe's lens_thickness/
        # lens_sound_speed (set by convert.py) apply the lens correction
        # automatically -- no manual initial_times shift needed here.
        parameters = f.load_parameters(**config.parameters)
        raw = f.data.raw_data[frame : frame + 1]  # (1, n_tx, n_ax, n_el, 1) -- RF

    print(f"frame index      : {frame} / {n_frames_available - 1}")
    print(f"raw_data shape   : {raw.shape}")
    print(f"grid             : {parameters.grid.shape}  (z, x, 3)")
    if parameters.lens_thickness is not None:
        print(
            f"lens correction  : thickness={parameters.lens_thickness * 1e3:.3f}mm, "
            f"c_lens={parameters.lens_sound_speed:.0f}m/s"
        )

    pipeline = Pipeline.from_config(config)
    inputs = pipeline.prepare_parameters(parameters)
    outputs = pipeline(data=raw, **inputs)

    recon = keras.ops.convert_to_numpy(outputs["data"])  # (1, grid_z, grid_x)
    image = zea.display.to_8bit(recon[0], dynamic_range=parameters.dynamic_range)
    # NOTE: parameters.extent_imshow is in meters, not mm -- scale explicitly.
    extent_mm = [v * 1e3 for v in parameters.extent_imshow]

    zea.visualize.set_mpl_style()
    plt.imshow(image, extent=extent_mm, cmap="gray")
    plt.xlabel("X (mm)")
    plt.ylabel("Z (mm)")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), bbox_inches="tight", dpi=100)

    print(f"Reconstructed  : {recon.shape}")
    print(f"Saved          : {output_path}")


def reconstruct_grid(config):
    hdf5_files = sorted(DATA_DIR.glob("*.hdf5"))
    if not hdf5_files:
        raise FileNotFoundError(f"No .hdf5 files found in {DATA_DIR}. Run convert.py first.")

    rng = random.Random(SEED)
    n_scans = min(N_SCANS, len(hdf5_files))
    chosen_files = rng.sample(hdf5_files, n_scans)

    pipeline = Pipeline.from_config(config)
    rows = []  # (scan_name, [(frame_idx, image, extent_mm), ...]) per scan

    for path in chosen_files:
        with File(str(path)) as f:
            parameters = f.load_parameters(**config.parameters)
            n_frames_available = f.data.raw_data.shape[0]
            if MIN_FRAME < n_frames_available:
                candidate_indices = range(MIN_FRAME, n_frames_available)
            else:
                candidate_indices = range(n_frames_available)
            n_frames = min(N_FRAMES, len(candidate_indices))
            frame_indices = sorted(rng.sample(candidate_indices, n_frames))
            raw = f.data.raw_data[frame_indices]

        inputs = pipeline.prepare_parameters(parameters)
        outputs = pipeline(data=raw, **inputs)
        recon = keras.ops.convert_to_numpy(outputs["data"])  # (n_frames, grid_z, grid_x)
        extent_mm = [v * 1e3 for v in parameters.extent_imshow]
        images = [zea.display.to_8bit(r, dynamic_range=parameters.dynamic_range) for r in recon]
        rows.append((path.stem, list(zip(frame_indices, images, [extent_mm] * len(images)))))
        print(f"raw_data shape   : {raw.shape}  ({path.stem})")

    _save_grid(rows, OUT or HERE / "assets" / "random_grid.png", frame_label_offset=0)


def reconstruct_systematic_grid(config):
    """Fixed, evenly-spaced 1-indexed frame numbers per patient, one row per
    patient. Frame *numbers* here match the raw rawdata_{frame}of4 numbering
    (1-indexed); array index = frame_number - 1."""
    patients = [p.strip() for p in PATIENTS.split(",") if p.strip()]
    if not patients:
        raise ValueError("SYSTEMATIC requires PATIENTS (comma-separated patient IDs).")

    frame_numbers = list(range(FRAME_START, FRAME_START + FRAME_STEP * FRAME_COUNT, FRAME_STEP))

    pipeline = Pipeline.from_config(config)
    rows = []

    for patient in patients:
        path = DATA_DIR / f"{patient}.hdf5"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Run convert.py for patient {patient!r} first."
            )

        with File(str(path)) as f:
            parameters = f.load_parameters(**config.parameters)
            n_frames_available = f.data.raw_data.shape[0]
            valid = [n for n in frame_numbers if 1 <= n <= n_frames_available]
            if len(valid) < len(frame_numbers):
                print(
                    f"{patient}: only {n_frames_available} frames available, "
                    f"dropping frame numbers > {n_frames_available}"
                )
            array_indices = [n - 1 for n in valid]
            raw = f.data.raw_data[array_indices]

        inputs = pipeline.prepare_parameters(parameters)
        outputs = pipeline(data=raw, **inputs)
        recon = keras.ops.convert_to_numpy(outputs["data"])
        extent_mm = [v * 1e3 for v in parameters.extent_imshow]
        images = [zea.display.to_8bit(r, dynamic_range=parameters.dynamic_range) for r in recon]
        rows.append((patient, list(zip(valid, images, [extent_mm] * len(images)))))
        print(f"raw_data shape   : {raw.shape}  ({patient}, frame numbers {valid})")

    _save_grid(rows, OUT or HERE / "assets" / "search_grid.png", frame_label_offset=0)


def _save_grid(rows, output_path, frame_label_offset):
    zea.visualize.set_mpl_style()

    n_scans = len(rows)
    n_cols = max(len(row_cells) for _, row_cells in rows)
    fig, axes = plt.subplots(n_scans, n_cols, figsize=(3 * n_cols, 3.4 * n_scans), squeeze=False)
    for row, (scan_name, row_cells) in enumerate(rows):
        for col in range(n_cols):
            ax = axes[row][col]
            if col >= len(row_cells):
                ax.axis("off")
                continue
            frame_idx, image, extent_mm = row_cells[col]
            ax.imshow(image, extent=extent_mm, cmap="gray")
            ax.set_title(f"{scan_name}\nframe {frame_idx + frame_label_offset}", fontsize=9)
            ax.set_xlabel("X (mm)")
            ax.set_ylabel("Z (mm)")

    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), bbox_inches="tight", dpi=100)
    print(f"Saved          : {output_path}")


def main():
    config = Config.from_path(str(CONFIG))

    if ZEA_FILE is not None:
        reconstruct_single(config)
    elif SYSTEMATIC:
        reconstruct_systematic_grid(config)
    else:
        reconstruct_grid(config)


if __name__ == "__main__":
    main()
