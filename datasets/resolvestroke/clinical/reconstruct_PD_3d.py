# SPDX-License-Identifier: Apache-2.0
"""Reconstruct power-Doppler 3D volumes for each clip and display as MIP montage.

Serves all 20 resolvestroke/clinical acquisitions (``SP01``-``SP10``, Left/Right),
which share probe, sequence and file layout: pick one with ``SUBJECT`` below.

For each of the 5 clips (4000 frames each), this script:
1. Beamforms all frames, in blocks, onto a real 3D POLAR (sector) volume -> LINEAR
   envelope. The hardware TGC stored in ``raw_data`` is kept.
2. Applies a 100 Hz slow-time high-pass (wall) filter to remove tissue clutter.
3. Integrates power Doppler (sum of squared envelope over slow time).
4. Displays a montage: rows = x-z MIP and y-z MIP, columns = clips, plus the
   reference ``mvi`` map of the file in the last column.

Grid: the acquisition is a matrix-probe DIVERGING wave, so a Cartesian box wastes
compute on the corners that fall outside the insonified cone. Instead we beamform
onto a 3D sector volume (radius x azimuth x elevation) whose apex is the virtual
source (|focus_distances|). Every voxel sits inside the cone, so the same coverage
needs far fewer voxels than a Cartesian box -> a faster beamform. It is still a
real 3D volume, so the MIPs project it (max over elevation for the x-z view, max
over azimuth for the y-z view). The volume's central planes match the two
perpendicular sectors produced by reconstruct.py.

Pipeline: a single pipeline in pipeline_PD_3d.yaml does everything end to end —
cast -> beamform -> envelope_detect -> tissue_highpass -> power_doppler. Steps 2-3
are CUSTOM zea ops (`tissue_highpass`, `power_doppler`) registered here with
`@ops_registry`; they act on the frame (slow-time) axis, so each block of frames
is beamformed in one pass (zea patches the grid to bound memory). Custom
ops need no merged zea PR — they only need to be defined (imported) before a config
referencing them is loaded, which is why the YAML can list them by name.

Runtime: about 14 min for a full acquisition on an RTX 4000 Ada with GPU JAX
(``uv sync --extra gpu`` in the Open-H-RF repo; the plain ``uv sync`` installs a CPU-only
JAX and this script then takes hours). Lower ``N_FRAMES`` for a quick look.

Usage:
    KERAS_BACKEND=jax uv run --project /path/to/Open-H-RF python reconstruct_PD_3d.py
"""

import os

os.environ.setdefault("KERAS_BACKEND", "jax")
os.environ.setdefault("MPLBACKEND", "Agg")

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import zea
from keras import ops as kops
from matplotlib.colors import PowerNorm
from zea import Config, File, Pipeline
from zea.internal.registry import ops_registry
from zea.ops import Operation

HERE = Path(__file__).parent
CONFIG = "hf://nvidia/Open-H-RF/resolvestroke/clinical/pipeline_PD_3d.yaml"

# Clip definitions (matching the combined file structure)
CLIPS = [
    "baseline_minus1s",
    "baseline_plus5s",
    "baseline_plus10s",
    "baseline_plus15s",
    "baseline_plus20s",
]
FRAMES_PER_CLIP = 4000
N_FRAMES_BF = 4000  # frames to beamform per clip (all of them)
BLOCK_FRAMES = 250  # frames per beamform + wall-filter pass (bounds GPU memory)
DISPLAY_DB = (-25.0, -5.0)  # dB range relative to the maximum over the five clips
DISPLAY_GAMMA = 1.25  # gamma on the normalised dB image (>1 darkens the mid-tones)
COLORMAP = "hot"

# --- Inputs -----------------------------------------------------------------
# One script serves all 20 clinical acquisitions; pick one with SUBJECT (the
# subdirectory / file stem on the Hub, e.g. "SP07-Right"). Defaults stream straight
# from the published corpus. Swap INPUT for a local path to run against your own copy.
SUBJECT = "SP02-Left-2"
INPUT = f"hf://nvidia/Open-H-RF/resolvestroke/clinical/{SUBJECT}/{SUBJECT}.hdf5"
N_FRAMES = N_FRAMES_BF
OUT = HERE / f"{SUBJECT}_PD_montage.png"

# The 3D sector-volume grid (limits, depth, resolution) and the high-pass params
# all live in pipeline_PD_3d.yaml (`grid:` block and tissue_highpass params).


# --------------------------------------------------------------------------- #
# Custom pipeline operations (registered locally — no zea PR required).
# --------------------------------------------------------------------------- #
# These ops are defined here, not in zea: a pipeline.yaml naming them resolves
# only once this module is imported. See https://github.com/open-h/Open-H-RF
@ops_registry("tissue_highpass")
class TissueHighpass(Operation):
    """Slow-time high-pass (wall) filter to suppress stationary tissue clutter.

    Operates along the frame (slow-time) axis with a frequency-domain filter and a
    raised-cosine taper around the cutoff. Implemented with Keras ops (``rfft`` /
    ``irfft``), so it runs on the same device as the beamformer (the GPU when one is
    available) and stays jittable: the filter mask only depends on the static frame
    count, so the whole pipeline compiles as one program.
    """

    def __init__(
        self,
        cutoff_hz: float = 50.0,
        frame_rate_hz: float = 4000.0,
        transition_hz: float = 10.0,
        time_axis: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.cutoff_hz = cutoff_hz
        self.frame_rate_hz = frame_rate_hz
        self.transition_hz = transition_hz
        self.time_axis = time_axis

    def frequency_mask(self, n_frames):
        """Real mask over the ``n_frames // 2 + 1`` non-negative rfft bins.

        1 above the cutoff, 0 below, with a raised-cosine taper across
        [cutoff - transition, cutoff) to reduce ringing. Built with NumPy at trace
        time (it is a constant for a given frame count).
        """
        freqs = np.fft.rfftfreq(n_frames, d=1.0 / self.frame_rate_hz)
        mask = (freqs >= self.cutoff_hz).astype(np.float32)
        taper = (freqs >= self.cutoff_hz - self.transition_hz) & (freqs < self.cutoff_hz)
        mask[taper] = 0.5 * (
            1.0 + np.cos(np.pi * (self.cutoff_hz - freqs[taper]) / self.transition_hz)
        )
        return mask

    def call(self, **kwargs):
        # Keras FFTs work along the last axis: move slow time there and back.
        data = kops.moveaxis(kwargs[self.key], self.time_axis, -1)
        n = int(data.shape[-1])
        mask = kops.convert_to_tensor(self.frequency_mask(n), dtype=data.dtype)
        real, imag = kops.rfft(data)
        filtered = kops.irfft((real * mask, imag * mask), fft_length=n)
        return {self.output_key: kops.moveaxis(filtered, -1, self.time_axis)}


@ops_registry("power_doppler")
class PowerDoppler(Operation):
    """Power-Doppler integration: sum of squared magnitude over the slow-time axis."""

    def __init__(self, time_axis: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.time_axis = time_axis

    def call(self, **kwargs):
        data = kwargs[self.key]
        return {self.output_key: kops.sum(kops.square(data), axis=self.time_axis)}


# --------------------------------------------------------------------------- #
# Sector-volume grid.
# --------------------------------------------------------------------------- #
def build_sector_volume_grid(azimuth_limits, elevation_limits, zlims, apex, n_r, n_az, n_el):
    """Build a real 3D sector-volume grid for a diverging wave.

    Bi-angular ("pyramidal") parametrization: a ray is steered by an azimuth
    angle alpha (x-z) and an elevation angle beta (y-z), and sampled at radius r
    from the apex at (0, 0, -apex). On the central planes this reduces to zea's
    2D polar fan (beta=0 -> x=r*sin(alpha), z=r*cos(alpha)-apex), so the volume's
    centre slices match reconstruct.py's perpendicular sectors.

    Returns:
        (grid, coords): grid has shape (n_r, n_az, n_el, 3) in Cartesian (x, y, z)
        metres; coords is (r, alpha, beta) 1D arrays for scan-conversion.
    """
    z0, z1 = float(zlims[0]), float(zlims[1])
    # Radius measured from the apex, so offset by apex -> on-axis depth is z0..z1.
    r = np.linspace(z0 + apex, z1 + apex, n_r)
    alpha = np.linspace(azimuth_limits[0], azimuth_limits[1], n_az)
    beta = np.linspace(elevation_limits[0], elevation_limits[1], n_el)

    R, A, B = np.meshgrid(r, alpha, beta, indexing="ij")  # (n_r, n_az, n_el)
    ta, tb = np.tan(A), np.tan(B)
    norm = np.sqrt(ta**2 + tb**2 + 1.0)
    x = R * ta / norm
    y = R * tb / norm
    z = R / norm - apex
    grid = np.stack((x, y, z), axis=-1).astype(np.float32)
    return grid, (r, alpha, beta)


def sector_plane_coords(r, angle, apex):
    """Cartesian (lat, z) mesh for a 2D sector (central-plane MIP), in mm."""
    R, T = np.meshgrid(r, angle, indexing="ij")
    lat = R * np.sin(T) * 1e3
    z = (R * np.cos(T) - apex) * 1e3
    return lat, z


def load_reference_mips(f):
    """x-z and y-z MIPs of the reference ``mvi`` map with their Cartesian extents (mm)."""
    ref = "custom/computed_references"
    coords = np.asarray(f.dataset(f"{ref}/coordinates")[...])  # (nz, ny, nx, 3) m
    mvi = np.asarray(f.dataset(f"{ref}/mvi")[...], dtype=np.float32)
    x_mm, y_mm, z_mm = coords[0, 0, :, 0] * 1e3, coords[0, :, 0, 1] * 1e3, coords[:, 0, 0, 2] * 1e3
    with np.errstate(all="ignore"):
        xz, yz = np.nanmax(mvi, axis=1), np.nanmax(mvi, axis=2)
    ext_xz = [x_mm.min(), x_mm.max(), z_mm.max(), z_mm.min()]
    ext_yz = [y_mm.min(), y_mm.max(), z_mm.max(), z_mm.min()]
    return xz, yz, ext_xz, ext_yz


def main():

    n_bf = N_FRAMES
    zea.init_device()
    config = Config.from_path(str(CONFIG))

    # One pipeline, end to end: cast -> beamform -> envelope -> tissue_highpass ->
    # power_doppler. The custom slow-time ops resolve by name because they are
    # registered above at import time.
    pipeline = Pipeline.from_config(config)
    hp_cutoff = pipeline["tissue_highpass"].cutoff_hz

    pd_volumes, (r, alpha, beta, apex), ref = beamform_clips(config, pipeline, hp_cutoff, n_bf)

    render(pd_volumes, r, alpha, beta, apex, ref, n_bf, hp_cutoff)


def beamform_clips(config, pipeline, hp_cutoff, n_bf):
    """Beamform every clip of INPUT to a power-Doppler volume; also read the reference maps."""
    g = config["grid"]  # 3D sector-volume spec
    azimuth_limits = tuple(float(v) for v in g["azimuth_limits"])
    elevation_limits = tuple(float(v) for v in g["elevation_limits"])
    zlims = tuple(float(v) for v in g["zlims"])

    with File(str(INPUT)) as f:
        parameters = f.load_parameters(**config.parameters)
        total_frames = f.data.raw_data.shape[0]

        apex = float(g["distance_to_apex"])  # virtual source behind the array

        grid, (r, alpha, beta) = build_sector_volume_grid(
            azimuth_limits,
            elevation_limits,
            zlims,
            apex,
            int(g["n_radial"]),
            int(g["n_azimuth"]),
            int(g["n_elevation"]),
        )
        flatgrid = grid.reshape(-1, 3)
        n_vox = flatgrid.shape[0]
        print(
            f"Total frames: {total_frames}, beamforming {n_bf} per clip, blocks of {BLOCK_FRAMES}"
        )
        print(
            f"Sector volume: {grid.shape[:-1]} = {n_vox} voxels (polar, apex={apex * 1e3:.1f} mm)"
        )

        inputs = pipeline.prepare_parameters(parameters, grid=grid, flatgrid=flatgrid)

        # Process each clip block by block: every block goes through the pipeline in
        # one pass (the slow-time ops see BLOCK_FRAMES frames) and the power-Doppler
        # volumes of the blocks are summed.
        pd_volumes = []  # list of (n_r, n_az, n_el) power-Doppler volumes
        for clip_idx, clip_name in enumerate(CLIPS):
            clip_start = clip_idx * FRAMES_PER_CLIP
            # Take n_bf frames from the middle of each clip
            frame_offset = (FRAMES_PER_CLIP - n_bf) // 2
            start = clip_start + frame_offset
            end = start + n_bf

            print(f"\n  Clip '{clip_name}': frames {start}-{end}  (HP cutoff={hp_cutoff} Hz)")

            pd = np.zeros(grid.shape[:-1], dtype=np.float64)
            for block_start in range(start, end, BLOCK_FRAMES):
                raw = f.data.raw_data[block_start : block_start + BLOCK_FRAMES]
                outputs = pipeline(**{pipeline.key: raw}, **inputs, return_numpy=True)
                pd += np.asarray(outputs[pipeline.output_key], dtype=np.float64)
            pd_volumes.append(pd)
            print(f"    PD volume: {pd.shape}, linear max={pd.max():.4g}")

        ref = load_reference_mips(f)
    return pd_volumes, (r, alpha, beta, apex), ref


def render(pd_volumes, r, alpha, beta, apex, ref, n_bf, hp_cutoff):
    """Montage of all clips (x-z / y-z MIPs) plus the reference mvi column."""
    ref_xz, ref_yz, ext_xz, ext_yz = ref

    # Normalize all PD volumes to the same global max (common dB scale). Voxels the
    # beamformer leaves at exactly zero (outside its receive aperture) become NaN.
    global_max = max(pv.max() for pv in pd_volumes)
    with np.errstate(all="ignore"):
        pd_db_volumes = [
            10.0 * np.log10(np.where(pd > 0, pd / global_max, np.nan)) for pd in pd_volumes
        ]

    vmin, vmax = DISPLAY_DB
    norm = PowerNorm(DISPLAY_GAMMA, vmin=vmin, vmax=vmax)
    cmap = plt.get_cmap(COLORMAP).copy()
    cmap.set_bad("#101010")

    # Scan-conversion coordinates for the two MIP planes (central plane of the fan)
    xz_lat, xz_z = sector_plane_coords(r, alpha, apex)  # (n_r, n_az)
    yz_lat, yz_z = sector_plane_coords(r, beta, apex)  # (n_r, n_el)

    zea.visualize.set_mpl_style()
    fig, axes = plt.subplots(2, len(CLIPS) + 1, figsize=(4.4 * (len(CLIPS) + 1), 9.5))

    with np.errstate(all="ignore"):
        for col, (clip_name, pd_vol) in enumerate(zip(CLIPS, pd_db_volumes)):
            # x-z MIP: project out elevation (max over the y-fan)
            xz_mip = np.nanmax(pd_vol, axis=2)  # (n_r, n_az)
            ax = axes[0, col]
            ax.pcolormesh(xz_lat, xz_z, xz_mip, cmap=cmap, norm=norm, shading="auto")
            ax.set_aspect("equal")
            ax.invert_yaxis()
            ax.set_title(f"{clip_name}\nx-z MIP", fontsize=9)
            ax.set_xlabel("x [mm]")
            if col == 0:
                ax.set_ylabel("z [mm]")

            # y-z MIP: project out azimuth (max over the x-fan)
            yz_mip = np.nanmax(pd_vol, axis=1)  # (n_r, n_el)
            ax = axes[1, col]
            ax.pcolormesh(yz_lat, yz_z, yz_mip, cmap=cmap, norm=norm, shading="auto")
            ax.set_aspect("equal")
            ax.invert_yaxis()
            ax.set_title(f"{clip_name}\ny-z MIP", fontsize=9)
            ax.set_xlabel("y [mm]")
            if col == 0:
                ax.set_ylabel("z [mm]")

    # Reference mvi map of the same file, for comparison (its own linear scale).
    vmax_ref = float(np.nanpercentile(ref_xz, 99.9))
    for row, (img, ext, lab) in enumerate([(ref_xz, ext_xz, "x"), (ref_yz, ext_yz, "y")]):
        ax = axes[row, -1]
        ax.imshow(img, extent=ext, cmap=cmap, vmin=0, vmax=vmax_ref, aspect="equal")
        ax.set_title(f"reference mvi\n{lab}-z MIP", fontsize=9)
        ax.set_xlabel(f"{lab} [mm]")
        ax.set_xlim(axes[row, 0].get_xlim())
        ax.set_ylim(axes[row, 0].get_ylim())

    fig.suptitle(
        f"Power Doppler 3D polar MIPs — {n_bf} frames/clip, HP cutoff {hp_cutoff} Hz, "
        f"{vmin:.0f}..{vmax:.0f} dB, gamma {DISPLAY_GAMMA}",
        fontsize=14,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(str(OUT), dpi=150, bbox_inches="tight")
    print(f"\nSaved montage: {OUT}")


if __name__ == "__main__":
    main()
