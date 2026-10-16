# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the us4us dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/us4us

Transmission-mode attenuation reconstruction (filtered backprojection) of
ring-array USCT data.

This is a full ring of point-source transmit elements with a receive
sub-aperture on the far side of the ring rather than surrounding the
transmitter, so it is a transmission (amplitude-attenuation) acquisition, not
reflection B-mode. Neither ``zea.ops.Beamform`` nor ``zea.ops.USCTReflectivityDAS``
applies, so the script defines its own operations
(https://zea.readthedocs.io/en/latest/pipeline.html#custom-operations).

``LinearizeDetectors`` resamples each projection from the ring's arc-spaced
detectors onto the uniform chord axis that parallel-beam FBP assumes; without it
the reconstruction is radially distorted. ``ApertureRearrange``'s
``aperture_offset`` (receive channel ``k`` of transmit ``t`` is ring element
``(t + offset + k) mod 1024``, centered on the antipode) is not documented
anywhere in the file; it is confirmed by ``validate_geometry`` below, which
predicts the direct-arrival sample from real element positions and compares it
to the measured envelope peak.

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

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import zea
from keras import ops
from mpl_toolkits.axes_grid1 import make_axes_locatable
from zea import Config, File, Pipeline
from zea.internal.registry import ops_registry
from zea.ops import Cast, GaussianBlur, Operation

HERE = Path(__file__).parent
CONFIG = HERE / "pipeline.yaml"

N_EL = 1024  # ring elements
N_RX = 512  # receive sub-aperture width
APERTURE_OFFSET = (N_EL - N_RX) // 2  # 256
PROBE_RADIUS = 13e-2  # m; matches us4us's reconstruction_example.py and the measured geometry

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/us4us/data/s1_l.hdf5"
FRAME = 8  # slice index within the acquisition (10 slices, 9 mm apart)
APERTURE_OFFSET_2 = APERTURE_OFFSET
PROBE_RADIUS_2 = PROBE_RADIUS  # ring radius in metres
SMOOTH_SIGMA = 1.0  # post-FBP Gaussian smoothing


# These ops are defined here, not in zea: a pipeline.yaml naming them resolves
# only once this module is imported. See https://github.com/open-h/Open-H-RF
@ops_registry("transmission_attenuation")
class TransmissionAttenuation(Operation):
    """Windowed peak RF amplitude per (tx, rx) pair, converted to attenuation via
    ``-20 * log10(amp / reference)``. ``reference=1.0`` is arbitrary units (no
    water-reference calibration)."""

    # Default is None (resolved below) rather than 1.0 so that an explicitly
    # passed value always differs from the signature default and is therefore
    # written into pipeline.yaml - zea omits params left at their default.
    def __init__(self, reference: float | None = None, **kwargs):
        super().__init__(**kwargs)
        self.reference = 1.0 if reference is None else reference

    def call(self, **kwargs):
        raw = kwargs[self.key]  # (n_tx, n_ax, n_rx, n_ch)
        raw = ops.squeeze(raw, axis=-1)  # (n_tx, n_ax, n_rx)
        n_ax = raw.shape[1]
        # `keras.ops.bartlett` requires its length argument to be a concrete
        # (non-traced) Python int even under jit, which a shape-derived value
        # here isn't - so the triangular window is built directly instead.
        i = ops.arange(n_ax, dtype="float32")
        half = (n_ax - 1) / 2.0
        window = (1.0 - ops.abs((i - half) / half))[None, :, None]
        amp = ops.max(ops.abs(raw * window), axis=1)  # (n_tx, n_rx)
        att = -20 * ops.log10(amp / self.reference)
        return {self.output_key: att}


@ops_registry("aperture_rearrange")
class ApertureRearrange(Operation):
    """Cyclically re-indexes each transmit's receive columns to a consistent
    relative frame, so `ResortSinogram` can treat rows as consecutive projection
    angles. `aperture_offset` is not documented in the file — see module
    docstring."""

    def __init__(self, aperture_offset: int | None = None, **kwargs):
        super().__init__(**kwargs)
        self.aperture_offset = APERTURE_OFFSET if aperture_offset is None else aperture_offset

    def call(self, **kwargs):
        att = kwargs[self.key]  # (n_tx, n_rx)
        n_tx, n_rx = att.shape
        rel_start = n_tx // 2 - self.aperture_offset
        rel_end = n_tx // 2 + self.aperture_offset
        tx = ops.arange(n_tx)
        rx_end = ops.mod(tx + rel_end, n_tx)
        rx_start = ops.mod(tx + rel_start, n_tx)
        shift = ops.where(rx_end < rx_start, rx_end + 1, 0)  # (n_tx,)
        col = ops.mod(ops.arange(n_rx)[None, :] + shift[:, None], n_rx)
        rearranged = ops.take_along_axis(att, col, axis=1)
        return {self.output_key: rearranged}


@ops_registry("resort_sinogram")
class ResortSinogram(Operation):
    """Doubles angular sampling (n_tx -> 2*n_tx) and halves detector count
    (n_rx -> n_rx // 2) by interleaving receive channels across transmits, into a
    proper parallel-projection sinogram."""

    def call(self, **kwargs):
        att = kwargs[self.key]  # (n_tx, n_rx)
        n_tx, n_rx = att.shape
        rx = ops.arange(n_rx // 2)
        tx = ops.arange(n_tx)
        RX, TX = ops.meshgrid(rx, tx, indexing="xy")
        src_tx = ops.mod(TX + n_rx // 4 - RX, n_tx)  # (n_tx, n_rx // 2)

        # output[2t, r] = att[src_tx[t, r], 2r]; output[2t+1, r] = att[src_tx[t, r], 2r+1].
        # Gathering the even/odd columns separately along axis 0 with the same
        # src_tx index, then interleaving via stack+reshape, is equivalent to that
        # scatter but keras.ops.take_along_axis-only (no fancy 2D indexing needed).
        even = ops.take_along_axis(att[:, 0::2], src_tx, axis=0)
        odd = ops.take_along_axis(att[:, 1::2], src_tx, axis=0)
        sinogram = ops.reshape(ops.stack([even, odd], axis=1), (n_tx * 2, n_rx // 2))
        return {self.output_key: sinogram}


@ops_registry("linearize_detectors")
class LinearizeDetectors(Operation):
    """Resample each projection from the ring's arc positions onto a uniform
    linear (chord) axis, which is what parallel-beam FBP assumes.

    Detector `i` sits at angle `alpha_i` on the ring, so its perpendicular offset
    from the ring centre is `R * sin(alpha_i)` — compressed towards the edges of
    the aperture, not uniformly spaced. Backprojecting without correcting this
    distorts the image radially. Matches `linearize_detectors()` in us4us's
    `reconstruction_example.py` (added in their 2026-09-07 revision).

    `keras.ops` has no `interp`, but both the source (`xp`) and target (`x`) axes
    depend only on `n_detectors` and the radius, so the gather indices and
    interpolation weights are constant and precomputed here in numpy. Endpoint
    handling matches `np.interp` (clamp, no extrapolation).
    """

    # See the note on TransmissionAttenuation.__init__ for why this defaults to None.
    def __init__(self, probe_radius: float | None = None, **kwargs):
        super().__init__(**kwargs)
        self.probe_radius = PROBE_RADIUS if probe_radius is None else probe_radius

    def call(self, **kwargs):
        sinogram = kwargs[self.key]  # (n_angles, n_detectors)
        n_col = sinogram.shape[1]

        i = np.arange(-(n_col // 2), n_col // 2)
        xp = self.probe_radius * np.sin(i * np.pi / 2 / n_col)  # arc -> chord, non-uniform
        x = i * np.sqrt(2) * self.probe_radius / n_col  # uniform target axis

        lo = np.clip(np.searchsorted(xp, x) - 1, 0, n_col - 2)
        w = np.clip((x - xp[lo]) / (xp[lo + 1] - xp[lo]), 0.0, 1.0).astype("float32")

        left = ops.take(sinogram, ops.convert_to_tensor(lo), axis=1)
        right = ops.take(sinogram, ops.convert_to_tensor(lo + 1), axis=1)
        return {self.output_key: left * (1.0 - w) + right * w}


@ops_registry("filtered_backprojection")
class FilteredBackprojection(Operation):
    """Ram-Lak (ramp) filter + backprojection onto a square grid sized to the
    detector count, vectorized over all angles in one gather-and-sum."""

    @staticmethod
    def _ramp_filter_half(n_detectors: int):
        """Ram-Lak filter, rfft-domain half. `sinogram` is real, so `rfft`/`irfft`
        (real in, real out) are used below instead of a full complex `fft`/`ifft`
        - there's no plain complex `ifft` in keras.ops anyway."""
        half = n_detectors // 2
        n = ops.concatenate([ops.arange(1.0, half + 1, 2.0), ops.arange(half - 1.0, 0.0, -2.0)])
        odd = -1.0 / (np.pi * n) ** 2
        even = ops.concatenate([ops.convert_to_tensor([0.25]), ops.zeros((half - 1,))])
        f = ops.reshape(ops.stack([even, odd], axis=1), (n_detectors,))
        real, _ = ops.rfft(f)
        return 2 * real

    def call(self, **kwargs):
        sinogram = kwargs[self.key]  # (n_angles, n_detectors)
        n_angles, n_detectors = sinogram.shape

        ramp_half = self._ramp_filter_half(n_detectors)
        real, imag = ops.rfft(sinogram)
        filtered = ops.irfft((real * ramp_half, imag * ramp_half), fft_length=n_detectors)

        # Backprojection geometry (which detector index each pixel/angle maps to)
        # depends only on (n_angles, n_detectors).
        half = n_detectors // 2
        angles = ops.arange(n_angles, dtype="float32") * (2 * np.pi / n_angles)
        x = ops.arange(n_detectors) - half
        X, Y = ops.meshgrid(x, x)  # (n_detectors, n_detectors)
        t = X[None] * ops.cos(angles)[:, None, None] + Y[None] * ops.sin(angles)[:, None, None]
        idx_raw = ops.cast(ops.round(t + half), "int32")  # (n_angles, D, D)
        # Skip out-of-range detector indices per angle rather than clamping them
        # to the edge, which would smear a repeated edge value into the image.
        valid = ops.logical_and(idx_raw >= 0, idx_raw < n_detectors)
        idx_safe = ops.clip(idx_raw, 0, n_detectors - 1)

        gathered = ops.take_along_axis(
            ops.repeat(filtered[:, None, :], n_detectors, axis=1), idx_safe, axis=2
        )  # (n_angles, D, D)
        image = ops.sum(ops.where(valid, gathered, 0.0), axis=0)
        return {self.output_key: image}


def build_pipeline(
    reference: float = 1.0,
    aperture_offset: int = APERTURE_OFFSET,
    probe_radius: float = PROBE_RADIUS,
    smooth_sigma: float = 1.0,
) -> Pipeline:
    """Every acquisition-specific constant is passed explicitly, so it round-trips
    into `pipeline.yaml` and the reconstruction is fully described by that file
    rather than by constants in this script."""
    return Pipeline(
        operations=[
            Cast(dtype="float32"),
            TransmissionAttenuation(reference=reference),
            ApertureRearrange(aperture_offset=aperture_offset),
            ResortSinogram(),
            LinearizeDetectors(probe_radius=probe_radius),
            FilteredBackprojection(),
            GaussianBlur(sigma=smooth_sigma, axes=(-2, -1)),
        ],
        with_batch_dim=False,
    )


def write_config(pipeline: Pipeline, path: Path) -> None:
    config = pipeline.to_config()
    config.to_yaml(str(path))


def parse_dead_channels(description: str) -> np.ndarray:
    """Dead-element indices, parsed from the file's root `description` text."""
    match = re.search(r"turned off[^:]*:\s*([\d,\s]+?)\s*\(numbering", description)
    if not match:
        return np.array([], dtype=np.int64)
    return np.array([int(x) for x in match.group(1).split(",") if x.strip()], dtype=np.int64)


def ring_center_and_radius(probe_geometry: np.ndarray) -> tuple[np.ndarray, float]:
    """Ring center [x, z] and radius [m], measured (this ring is centered at
    z ~ 0.13 m, not the origin)."""
    xz = probe_geometry[:, [0, 2]]
    center = xz.mean(axis=0)
    radius = float(np.linalg.norm(xz - center, axis=-1).mean())
    return center, radius


def rx_element_indices(aperture_offset: int, n_tx: int, n_rx: int) -> np.ndarray:
    """Physical ring-element index for every (transmit, raw receive channel)
    pair: `(n_tx, n_rx)`. Sizes come from the file, not from constants."""
    k = np.arange(n_rx)
    return (np.arange(n_tx)[:, None] + aperture_offset + k[None, :]) % n_tx


def validate_geometry(rf, tx_position, rx_positions, sound_speed, initial_time, fs):
    """Predicted vs. measured direct-arrival sample, per receive channel, for one
    transmit. Agreement confirms the ring geometry, `initial_times`, and the
    aperture offset at once. `rf` is `(n_ax, n_rx)` real RF for one transmit."""
    distance = np.linalg.norm(rx_positions - tx_position, axis=-1)
    predicted = (distance / sound_speed - initial_time) * fs
    envelope = np.abs(rf)
    measured = envelope.argmax(axis=0)
    strong = envelope.max(axis=0) > 0.2 * envelope.max()
    residual = float(np.median(np.abs(measured[strong] - predicted[strong])))
    return predicted, measured, residual


def main():
    input_path = str(ZEA_FILE)
    if "://" not in input_path:
        candidate = Path(input_path)
        if not candidate.is_absolute():
            candidate = HERE / candidate
        if not candidate.exists():
            raise FileNotFoundError(f"{ZEA_FILE} not found (looked in cwd and {HERE}).")
        input_path = str(candidate)
    output_path = HERE / "assets" / f"{Path(input_path).stem}_reconstruct.png"

    # Build with every parameter explicit, save to pipeline.yaml, then reload and
    # run from that file - so the YAML alone fully describes the reconstruction.
    pipeline = build_pipeline(
        aperture_offset=APERTURE_OFFSET_2,
        probe_radius=PROBE_RADIUS_2,
        smooth_sigma=SMOOTH_SIGMA,
    )
    write_config(pipeline, CONFIG)
    config = Config.from_path(str(CONFIG))
    pipeline = Pipeline.from_config(config)

    with File(str(input_path)) as f:
        probe_geometry = f.probe.probe_geometry[:]
        center, radius = ring_center_and_radius(probe_geometry)
        sound_speed = float(f.scan.sound_speed)
        fs = float(f.scan.sampling_frequency)
        initial_times = f.scan.initial_times[:]
        dead_elements = parse_dead_channels(str(f.attrs.get("description", "")))
        zea.log.info(f"Dead elements parsed from description: {dead_elements.tolist()}")
        # Cross-check the PROBE_RADIUS used by LinearizeDetectors against the
        # radius actually implied by probe_geometry.
        if abs(radius - PROBE_RADIUS_2) > 1e-3:
            zea.log.warning(
                f"probe_radius={PROBE_RADIUS_2:.4f} m differs from the measured ring "
                f"radius {radius:.4f} m (centre {center[0]:.4f}, {center[1]:.4f} m)"
            )
        else:
            zea.log.info(f"Ring radius: {radius:.4f} m (matches PROBE_RADIUS)")

        raw = np.asarray(f.data.raw_data[FRAME])  # (n_tx, n_ax, n_rx, n_ch)

        # As of the Sep-2026 resubmission these live in `data` as spatial maps
        # (with coordinates); older files put them in the free-form `custom`
        # group. Read `data` first, fall back to `custom` for the old layout.
        # us4us ship their own FBP output and sinogram alongside the raw data, as
        # spatial maps under `data` with `coordinates`.
        stored_image = np.asarray(f.data.image.values[FRAME])
        image_coords = np.asarray(f.data.image.coordinates)
        stored_sinogram = np.asarray(f.data.sinogram.values[FRAME])
        sinogram_coords = np.asarray(f.data.sinogram.coordinates)

    rx_idx = rx_element_indices(
        APERTURE_OFFSET_2, n_tx=probe_geometry.shape[0], n_rx=raw.shape[2]
    )  # (n_tx, n_rx)
    ring_xz = probe_geometry[:, [0, 2]].astype(np.float32)

    predicted, measured, residual = validate_geometry(
        raw[0, :, :, 0].astype(np.float32),
        ring_xz[0],
        ring_xz[rx_idx[0]],
        sound_speed,
        float(initial_times[0]),
        fs,
    )
    zea.log.info(f"Direct-arrival check: median |measured - predicted| = {residual:.2f} samples")

    outputs = pipeline(data=raw, return_numpy=True)
    recon = outputs["data"]  # (n_detectors, n_detectors)

    zea.visualize.set_mpl_style()
    fig, axes = plt.subplots(1, 4, figsize=(24, 5.5))

    n_rx = raw.shape[2]
    rf_db = 20 * np.log10(np.abs(raw[0, :, :, 0]) / (np.abs(raw[0, :, :, 0]).max() + 1e-12) + 1e-10)
    axes[0].imshow(rf_db, aspect="auto", cmap="gray", vmin=-60, vmax=0)
    axes[0].plot(np.arange(n_rx), predicted, "r--", lw=1.0, label="predicted direct arrival")
    axes[0].plot(np.arange(n_rx), measured, "c:", lw=0.7, alpha=0.6, label="measured (argmax)")
    axes[0].set_ylim(raw.shape[1], 0)
    axes[0].legend(loc="lower left", fontsize=7)
    axes[0].set_title(f"RF, transmit 0 [dB]\ngeometry check: residual {residual:.2f} samples")
    axes[0].set_xlabel("Receive channel")
    axes[0].set_ylabel("Axial sample")

    # After LinearizeDetectors the backprojection grid spans the uniform chord
    # axis, i.e. +-R*sqrt(2)/2 (~92 mm) about the ring centre - not +-R. Plotted
    # in mm relative to the ring centre, matching the frame of the stored maps'
    # own `coordinates` so the panels line up.
    half_width = PROBE_RADIUS_2 * np.sqrt(2) / 2 * 1e3
    extent = [-half_width, half_width, half_width, -half_width]
    vmin, vmax = np.percentile(recon, [1, 99])
    handle = axes[1].imshow(recon, cmap="magma", extent=extent, vmin=vmin, vmax=vmax)
    axes[1].set_title(f"Attenuation FBP (zea.Pipeline)\n({Path(input_path).name}, frame {FRAME})")
    axes[1].set_xlabel("X (mm)")
    axes[1].set_ylabel("Z (mm)")
    cax = make_axes_locatable(axes[1]).append_axes("right", size="5%", pad=0.05)
    fig.colorbar(handle, cax=cax)

    # Stored sinogram: x is detector position in metres; the "z" slot carries the
    # projection angle in radians (0..2*pi) rather than a Cartesian coordinate.
    sino_extent = [
        sinogram_coords[..., 0].min() * 1e3,
        sinogram_coords[..., 0].max() * 1e3,
        sinogram_coords[..., 2].max(),
        sinogram_coords[..., 2].min(),
    ]
    axes[2].imshow(stored_sinogram, cmap="viridis", aspect="auto", extent=sino_extent)
    axes[2].set_title("Stored sinogram (us4us)")
    axes[2].set_xlabel("Detector position (mm)")
    axes[2].set_ylabel("Projection angle (rad)")

    img_extent = [
        image_coords[..., 0].min() * 1e3,
        image_coords[..., 0].max() * 1e3,
        image_coords[..., 2].max() * 1e3,
        image_coords[..., 2].min() * 1e3,
    ]
    svmin, svmax = np.percentile(stored_image, [1, 99])
    h = axes[3].imshow(stored_image, cmap="magma", extent=img_extent, vmin=svmin, vmax=svmax)
    axes[3].set_title("Stored FBP (us4us)")
    axes[3].set_xlabel("X (mm)")
    axes[3].set_ylabel("Z (mm)")
    cax = make_axes_locatable(axes[3]).append_axes("right", size="5%", pad=0.05)
    fig.colorbar(h, cax=cax)

    fig.suptitle(f"{Path(input_path).name} — frame {FRAME}")
    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), bbox_inches="tight", dpi=100)

    print(f"Reconstructed  : {recon.shape}")
    print(f"Saved          : {output_path}")


if __name__ == "__main__":
    main()
