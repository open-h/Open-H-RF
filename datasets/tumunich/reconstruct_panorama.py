# SPDX-License-Identifier: Apache-2.0
"""Extended-field-of-view reconstruction for the tumunich dataset of Open-H-RF.

The robot translates the probe 70 mm along its own lateral axis during the
acquisition, so frames taken at different points in the sweep see overlapping
but offset slices of the phantom. This script beamforms ``N_FRAMES`` of them
and compounds them onto one canvas, giving a panorama about 108 mm wide: the
38.4 mm aperture plus the 70 mm of travel.

It uses the operations of that reference pipeline but stops at the envelope, and
normalises once over the finished panorama instead of once per frame. The
pipeline is written out beside this script under its own name, so the reference
config is left alone.

Frames are placed from ``metadata/probe_pose``, which records the robot
trajectory as an absolute measurement. The pose is a pure translation
here: the quaternions are constant, and all the motion is on one axis.

Usage:
    uv run python reconstruct_panorama.py
"""

import os

os.environ.setdefault("KERAS_BACKEND", "jax")
os.environ.setdefault("MPLBACKEND", "Agg")

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import zea
from reconstruct import (
    DYNAMIC_RANGE,
    FEEDTHROUGH_SAMPLES,
    PARAMETERS,
    build_pipeline,
)

HERE = Path(__file__).parent
CONFIG = HERE / "pipeline_panorama.yaml"

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
INPUT = "hf://nvidia/Open-H-RF/tumunich/data/cirs_phantom/synth_apert_sweep_1.hdf5"
OUTPUT = None  # PNG to write (default: <input>_panorama.png next to the sample)
N_FRAMES = 20  # Frames to compound, spread evenly over the travel
BLEND_TAPER = 0.25  # Fraction of each frame's width ramped down at either edge
DISPLAY_PERCENTILE = 99.95  # Panorama percentile mapped to 0 dB (see blend_panorama)


def frame_times(f):
    """Acquisition time of each frame in seconds, measured from the first transmit."""
    intervals = np.asarray(f.scan.time_to_next_transmit, dtype=np.float64).sum(axis=1)
    return np.concatenate([[0.0], np.cumsum(intervals)[:-1]])


def displacement_by_pose(f):
    """Per-frame lateral probe displacement in metres, relative to the first frame.

    ``start_time_offset`` is defined by the zea spec as the time between the
    first transmit event and sample 0 of the pose signal, so it belongs on the
    pose clock and not on the frame clock: pose sample ``t`` was taken at
    acquisition time ``t + start_time_offset``.
    """
    pose = f.metadata.probe_pose
    translation = np.asarray(pose.translation, dtype=np.float64)
    timestamps = np.asarray(pose.timestamps, dtype=np.float64)
    start_time_offset = float(np.asarray(pose.start_time_offset))

    # The sweep is a pure translation, so the axis that moves is the sweep axis.
    sweep_axis = int(np.argmax(translation.max(axis=0) - translation.min(axis=0)))
    position = np.interp(frame_times(f), timestamps + start_time_offset, translation[:, sweep_axis])
    return position - position[0]


def select_frames(displacement, n_frames):
    """Frame indices whose positions are spread as evenly as possible over the travel.

    Evenly in space, not in frame number: the robot is stationary for the first
    ~30 and last ~45 frames, so an even split by index would stack several
    frames on top of each other at both ends and leave gaps in the middle.
    """
    targets = np.linspace(displacement.min(), displacement.max(), n_frames)
    indices = {int(np.argmin(np.abs(displacement - target))) for target in targets}
    return sorted(indices)


def beamform_frame(f, frame):
    """Beamform one frame onto the axial extent of the stored B-mode."""
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

    # The reference pipeline without its last two stages, the per-frame Normalize
    # and LogCompress: this script normalises once over the finished panorama.
    operations = list(build_pipeline(passband).operations)[:-2]
    config = zea.Pipeline(operations=operations).to_config()
    config["parameters"] = parameters
    config.to_yaml(str(CONFIG))

    config = zea.Config.from_path(str(CONFIG))
    pipeline = zea.Pipeline.from_config(config)
    params = f.load_parameters(**config.parameters)
    inputs = pipeline.prepare_parameters(params)
    generated = pipeline(data=raw, **inputs, return_numpy=True)["data"][0]

    # The grid starts at the imaging start depth, so pad the near field back on
    # to line the result up with the stored Verasonics B-mode. These are linear
    # envelope values, so the fill is plain silence.
    axial_spacing = (end_depth - start_depth) / (generated.shape[0] - 1)
    generated = np.pad(generated, ((round(start_depth / axial_spacing), 0), (0, 0)))
    return generated


def blend_panorama(frames, offsets, taper=BLEND_TAPER, percentile=DISPLAY_PERCENTILE):
    """Compound linear-envelope frames onto one canvas at the given column offsets.

    The panorama is normalised once here, against a high percentile rather than
    the maximum: the point targets are specular and sit ~95x above the speckle,
    so normalising by the peak would drop the tissue to -40 dB and render the
    result nearly black. The default percentile sits on the knee between speckle
    and specular, putting the tissue median near the -24.7 dB of the single-frame
    reference and letting the point targets saturate, which is what a scanner
    does anyway.

    Each frame is tapered at its lateral edges so the ends of the panorama,
    where only one frame contributes, fade out instead of ending on a hard seam.
    """
    n_depth, n_columns = frames[0].shape
    offsets = np.asarray(offsets, dtype=np.float64)
    offsets = offsets - offsets.min()
    width = int(np.ceil(offsets.max())) + n_columns

    weight_profile = np.ones(n_columns)
    n_ramp = max(1, int(taper * n_columns))
    ramp = np.hanning(2 * n_ramp)[:n_ramp]
    weight_profile[:n_ramp] = ramp
    weight_profile[-n_ramp:] = ramp[::-1]

    total = np.zeros((n_depth, width))
    weight = np.zeros((n_depth, width))
    for frame, offset in zip(frames, offsets):
        column = int(round(offset))
        total[:, column : column + n_columns] += frame * weight_profile[None, :]
        weight[:, column : column + n_columns] += weight_profile[None, :]

    covered = weight > 0
    compounded = np.divide(total, weight, out=np.zeros_like(total), where=covered)

    reference = np.percentile(compounded[covered], percentile)
    panorama = 20.0 * np.log10(np.maximum(compounded / reference, 1e-12))
    panorama[~covered] = DYNAMIC_RANGE[0]
    return np.clip(panorama, DYNAMIC_RANGE[0], DYNAMIC_RANGE[1])


def main():
    global OUTPUT
    if OUTPUT is None:
        OUTPUT = Path(f"{Path(INPUT).stem}_panorama.png")

    zea.init_device()

    with zea.File(str(INPUT)) as f:
        displacement = displacement_by_pose(f)
        selected = select_frames(displacement, N_FRAMES)
        travel = displacement.max() - displacement.min()
        print(f"Sweep travel {travel * 1e3:.1f} mm; compounding {len(selected)} frames: {selected}")

        coordinates = f.data.image.coordinates[:]
        frames = [beamform_frame(f, frame) for frame in selected]

    lateral_extent = float(coordinates[..., 0].max() - coordinates[..., 0].min())
    column_spacing = lateral_extent / (frames[0].shape[1] - 1)
    offsets = displacement[selected] / column_spacing

    panorama = blend_panorama(frames, offsets)
    print(f"Panorama: {panorama.shape} ({panorama.shape[1] * column_spacing * 1e3:.1f} mm wide)")

    # Lateral axis is the probe's own, extended by the sweep: canvas column 0 is
    # the left edge of the frame taken furthest along the travel.
    lateral_start = (float(coordinates[..., 0].min()) + float(displacement[selected].min())) * 1e3
    extent = [
        lateral_start,
        lateral_start + panorama.shape[1] * column_spacing * 1e3,
        float(coordinates[..., 2].max()) * 1e3,
        0.0,
    ]

    zea.visualize.set_mpl_style()
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.imshow(
        panorama,
        aspect="equal",
        cmap="gray",
        extent=extent,
        vmin=DYNAMIC_RANGE[0],
        vmax=DYNAMIC_RANGE[1],
    )
    ax.set_xlabel("Lateral [mm]")
    ax.set_ylabel("Depth [mm]")
    plt.tight_layout()
    plt.savefig(OUTPUT, dpi=150, bbox_inches="tight")
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
