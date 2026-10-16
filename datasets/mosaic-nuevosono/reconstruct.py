# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the mosaic-nuevosono dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/mosaic-nuevosono

B-mode reconstruction of rotational in-vivo IVUS channel data.

Frames can be chosen two ways:

  * ``NUM_FRAMES = N``     : N frames spaced evenly across the whole pullback.
  * ``FRAMES = [a, b, c]`` : explicit frame indices (takes precedence over NUM_FRAMES).

The transducer rotates the opposite way in some acquisitions, mirroring the
image across the y axis. This is read from the file's ``metadata/rotation``
section (+1 clockwise, -1 counterclockwise) and the flip is applied
automatically.

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
from matplotlib.colors import to_rgba
from zea.ops import Downsample

HERE = Path(__file__).resolve().parent

OUTPUT_PX = None  # reconstruction side length; None -> derive from segmentation mask dims

MASK_COLORS = ["tab:red", "tab:green", "tab:cyan", "tab:orange", "tab:purple"]

LABEL_COLORS = {
    "lumen": "tab:red",
    "intima_media": "tab:green",
    "guidewire": "tab:cyan",
}

FRAME_COLORS = plt.get_cmap("tab10").colors

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/mosaic-nuevosono/data/22_12_10_52.hdf5"
CONFIG = "hf://nvidia/Open-H-RF/mosaic-nuevosono/pipeline.yaml"
NUM_FRAMES = 5  # Number of frames to overlay, spaced evenly across the pullback
FRAMES = None  # Explicit frame indices to overlay (overrides NUM_FRAMES)
OUT = None
BANDWIDTH = 30e6
DYNAMIC_RANGE = (-43.0, -0.0)
SIZE = OUTPUT_PX  # Square canvas side length (px) for the reconstruction
ALPHA = 0.45  # Opacity of the segmentation overlays in [0, 1]


def color_for(label, channel):
    """Color for a segmentation class: by name, falling back to channel index."""
    return LABEL_COLORS.get(label, MASK_COLORS[(channel - 1) % len(MASK_COLORS)])


def select_frames(n_frames, explicit, num_frames):
    if explicit:
        frames = sorted({int(i) for i in explicit})
        for i in frames:
            if not 0 <= i < n_frames:
                raise ValueError(f"Frame {i} out of range [0, {n_frames - 1}].")
        return frames
    num = max(1, min(num_frames, n_frames))
    return sorted(set(np.linspace(0, n_frames - 1, num).astype(int).tolist()))


def reconstruct_frame(
    pipeline, parameters, raw_frame, coordinates, mirror, bandwidth, dynamic_range
):
    """Run the pipeline (RF -> Cartesian B-mode) on one frame and return the 8-bit image.

    ``scan_convert`` in the pipeline produces the Cartesian image with the catheter centred;
    the depth (``+depth`` up) and lateral-mirror flips are display orientation applied here.
    """
    inputs = pipeline.prepare_parameters(parameters)
    inputs["bandwidth"] = bandwidth
    inputs["coordinates"] = coordinates

    outputs = pipeline(**{pipeline.key: raw_frame}, **inputs)
    cartesian = keras.ops.convert_to_numpy(outputs[pipeline.output_key])[0]

    cartesian = cartesian[::-1]  # +depth up
    if mirror:
        cartesian = cartesian[:, ::-1]  # reversed transducer rotation -> mirror across y
    return np.asarray(zea.display.to_8bit(cartesian, dynamic_range=dynamic_range))


def draw_overlay(ax, recon_gray, segmentation, labels, alpha):
    ax.imshow(recon_gray, cmap="gray")
    present = []
    for channel, label in enumerate(labels):
        if label == "background":
            continue
        mask = segmentation[..., channel]
        area = int(mask.sum())
        if area == 0:
            continue
        present.append((area, channel, label, mask))

    colors = {}
    for _, channel, label, mask in sorted(present, key=lambda t: t[0], reverse=True):
        color = color_for(label, channel)
        colors[label] = color
        overlay = np.zeros((*mask.shape, 4), dtype=float)
        overlay[mask] = to_rgba(color, alpha=alpha)
        ax.imshow(overlay)
    return colors


def render_overview(panels, frames, labels, position_mm, frame_rate_hz, alpha, output):
    n_panels = len(panels)
    has_tracking = position_mm is not None
    frame_color = {fr: FRAME_COLORS[i % len(FRAME_COLORS)] for i, fr in enumerate(frames)}

    zea.visualize.set_mpl_style()
    fig = plt.figure(
        figsize=(max(12, 4 * n_panels), 9 if has_tracking else 5),
        constrained_layout=True,
    )
    n_rows = 2 if has_tracking else 1
    gs = fig.add_gridspec(n_rows, n_panels)
    panel_row = 1 if has_tracking else 0

    if has_tracking:
        frame_axis = np.arange(len(position_mm))
        ax_track = fig.add_subplot(gs[0, :])
        ax_track.plot(frame_axis, position_mm, linewidth=1.5, color="0.4", zorder=1)
        for fr in frames:
            if 0 <= fr < len(position_mm):
                ax_track.scatter(
                    fr,
                    position_mm[fr],
                    color=frame_color[fr],
                    s=70,
                    zorder=3,
                    edgecolor="black",
                    linewidth=0.6,
                    label=f"frame {fr}",
                )
        ax_track.set_title("Sequential IVUS Acquisition")
        ax_track.set_xlabel("Frame")
        ax_track.set_ylabel("Pullback position (mm)")
        ax_track.grid(True, alpha=0.3)
        ax_track.legend(loc="best", ncol=min(n_panels, 6), framealpha=0.8)
        if frame_rate_hz > 0:
            time_ax = ax_track.secondary_xaxis(
                "top",
                functions=(lambda fr: fr / frame_rate_hz, lambda s: s * frame_rate_hz),
            )
            time_ax.set_xlabel("Elapsed time (s)")

    present_colors = {}
    for col, (frame, recon_gray, segmentation) in enumerate(panels):
        ax = fig.add_subplot(gs[panel_row, col])
        present_colors.update(draw_overlay(ax, recon_gray, segmentation, labels, alpha))
        ax.set_title(f"frame {frame}", color=frame_color[frame], fontweight="bold")
        ax.set_xticks([])
        ax.set_yticks([])

        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(frame_color[frame])
            spine.set_linewidth(2.5)

    legend_handles = [
        plt.Line2D([0], [0], marker="s", linestyle="", color=present_colors[label], label=label)
        for label in labels
        if label in present_colors
    ]
    if legend_handles:
        fig.legend(
            handles=legend_handles,
            loc="lower center",
            ncol=len(legend_handles),
            framealpha=0.8,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    print(f"Saved {output}")


def main():
    zea.init_device()

    pipeline = zea.Pipeline.from_path(str(CONFIG))
    print(f"Pipeline: {pipeline}")

    with zea.File(str(ZEA_FILE)) as f:
        parameters = f.load_parameters()
        n_frames = int(f.data.raw_data.shape[0])
        frames = select_frames(n_frames, FRAMES, NUM_FRAMES)

        raw_frames = [np.asarray(f.data.raw_data[fr : fr + 1]) for fr in frames]
        masks = [np.asarray(f.data.segmentation.values[fr]).astype(bool) for fr in frames]
        labels = list(f.data.segmentation.labels.asstr()[:])
        mask_h, mask_w = (
            int(f.data.segmentation.values.shape[1]),
            int(f.data.segmentation.values.shape[2]),
        )

        # Pullback trajectory, recorded only for the tracked acquisitions.
        position_mm, frame_rate_hz = None, 0.0
        if "pullback_position" in f["metadata"]:
            pullback = f.metadata.pullback_position
            position_mm = np.squeeze(np.asarray(pullback.samples) * 1e3)
            if position_mm.ndim > 1:
                position_mm = position_mm[:, int(np.argmax(np.ptp(position_mm, axis=0)))]
            frame_rate_hz = float(pullback.sampling_frequency)
        else:
            print("No pullback_position metadata found; skipping trajectory panel.")

        # Rotation sense: +1 clockwise, -1 counterclockwise (mirror across y).
        rotation_sign = float(np.squeeze(np.asarray(f.metadata.rotation.samples)))
        mirror = rotation_sign < 0

    print(f"Mirror (from rotation metadata): {mirror}")
    print(f"n_frames        : {n_frames}, selected frames: {frames}")

    # Reconstruct onto the exact grid the stored image/segmentation use, so the overlay lines
    # up pixel-for-pixel. SIZE overrides to a square canvas (e.g. for quick previews).
    if SIZE is not None:
        out_h = out_w = SIZE
    else:
        out_h, out_w = mask_h, mask_w

    # Polar grid: one A-line per transmit (theta), n_ax // downsample factor (rho).
    n_theta = int(raw_frames[0].shape[1])
    n_ax = int(raw_frames[0].shape[2])
    factor = next((op.factor for op in pipeline.operations if isinstance(op, Downsample)), 1)
    n_rho = n_ax // factor
    print(f"reconstruction: {out_h}x{out_w} px (mask {mask_h}x{mask_w}), polar {n_rho}x{n_theta}")

    # Full-circle cross-section centred on the catheter, inscribed in the shorter axis.
    coordinates = zea.display.polar_to_cartesian_coordinates(
        (out_h, out_w),
        n_rho,
        n_theta,
        tip=(out_w / 2, out_h / 2),
        r_max=min(out_h, out_w) / 2,
        theta_range=(-np.pi, np.pi),
    )

    # Reconstruct each frame one at a time: Normalize infers its range per frame.
    panels = []
    for frame, raw_frame, mask in zip(frames, raw_frames, masks):
        recon_gray = reconstruct_frame(
            pipeline,
            parameters,
            raw_frame,
            coordinates,
            mirror,
            bandwidth=BANDWIDTH,
            dynamic_range=tuple(DYNAMIC_RANGE),
        )
        if mask.shape[:2] != recon_gray.shape[:2]:
            raise ValueError(
                f"segmentation mask {mask.shape[:2]} and reconstruction "
                f"{recon_gray.shape[:2]} disagree; they must share one grid for the overlay."
            )
        panels.append((frame, recon_gray, mask))

    output = OUT or (HERE / "assets" / Path(ZEA_FILE).stem / f"overview_{len(frames)}_frames.png")
    render_overview(panels, frames, labels, position_mm, frame_rate_hz, ALPHA, output)


if __name__ == "__main__":
    main()
