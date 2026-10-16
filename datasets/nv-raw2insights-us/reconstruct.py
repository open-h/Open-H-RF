# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the nv-raw2insights-us dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/nv-raw2insights-us

B-mode reconstruction of simulated full synthetic aperture (FSA) channel data.

The simulation ships its own ground truth, so the reconstruction can be checked
against it directly. The figure puts seven panels side by side: IQ energy, the
stored DAS B-mode, the focused-transmit B-mode, the zea reconstruction, a
sound-speed-corrected zea reconstruction, the ground-truth speed-of-sound map
and the segmentation. The DAS -> envelope -> normalize -> log-compress pipeline
is defined in code and saved to pipeline.yaml as a shareable recipe; it is the
plain, non-SoS-corrected reconstruction. The SoS-corrected panel reruns the
same pipeline with sos_map/sos_grid_x/sos_grid_z supplied at call time.

Requires zea>=0.1.6 (https://github.com/tue-bmd/zea), the library that does the
ultrasound processing here, together with one of its Keras backends (JAX,
PyTorch or TensorFlow). Installation instructions are at
https://zea.readthedocs.io/en/latest/installation.html.

Usage:
    python reconstruct.py
"""

from pathlib import Path

import keras
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import zea
from zea.ops import Beamform, EnvelopeDetect, LogCompress, Normalize

HERE = Path(__file__).resolve().parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/nv-raw2insights-us/data/nv_r2i_us_validation_0084.hdf5"
OUT = HERE / "assets" / "nv_raw2insights_us_reconstructed.png"
CONFIG = HERE / "pipeline.yaml"


def coords_to_imshow_mm(coords):
    """open-h-rf per-pixel coordinates (z, x, 3), last axis [x, y, z] in metres
    -> mpl imshow extent [left, right, bottom, top] in mm."""
    c = np.asarray(coords)
    x, z = c[..., 0] * 1e3, c[..., 2] * 1e3
    return [x.min(), x.max(), z.max(), z.min()]


def build_pipeline() -> "zea.Pipeline":
    """Define the DAS beamforming pipeline in code (no SoS correction)."""
    return zea.Pipeline(
        operations=[
            Beamform(beamformer="delay_and_sum"),
            EnvelopeDetect(),
            Normalize(),
            LogCompress(),
        ]
    )


def main():
    zea.init_device()

    with zea.File(str(ZEA_FILE)) as f:
        parameters = f.load_parameters()
        raw = f.data.raw_data[:]
        img = f.data.image.values[:]
        img_coords = f.data.image.coordinates[:]
        focused = f.data.bmode_focused.values[:]
        focused_coords = f.data.bmode_focused.coordinates[:]
        sos = f.data.sos_map.values[:]
        sos_coords = f.data.sos_map.coordinates[:]
        seg = f.data.segmentation.values[:]
        seg_coords = f.data.segmentation.coordinates[:]
        labels = f.data.segmentation.labels.asstr()[:]
        phase_err = f.metrics.common_midpoint_phase_error

    print(f"raw_data: {raw.shape}")

    build_pipeline().to_yaml(str(CONFIG))
    config = zea.Config.from_path(str(CONFIG))
    pipeline = zea.Pipeline.from_config(config)

    params = pipeline.prepare_parameters(parameters)
    outputs = pipeline(**{pipeline.key: raw}, **params)
    recon = keras.ops.convert_to_numpy(outputs[pipeline.output_key])[0]
    grid = keras.ops.convert_to_numpy(params["grid"])  # (nz, nx, 3)
    recon_ext = [
        grid[0, 0, 0] * 1e3,
        grid[0, -1, 0] * 1e3,
        grid[-1, 0, 2] * 1e3,
        grid[0, 0, 2] * 1e3,
    ]
    print(f"Reconstructed: {recon.shape}")

    # Reconstruct with SoS correction
    print(f"sos shape: {sos.shape}")
    # Handle different possible sos shapes: (frames, nz, nx) or (frames, nz, nx, 1)
    sos_frame = sos[0] if sos.ndim == 3 else sos[0, :, :, 0]
    nz_sos, nx_sos = sos_frame.shape[0], sos_frame.shape[1]
    sos_x, sos_z = sos_coords[..., 0], sos_coords[..., 2]
    sos_grid_x = np.linspace(sos_x.min(), sos_x.max(), nx_sos, dtype=np.float32)
    sos_grid_z = np.linspace(sos_z.min(), sos_z.max(), nz_sos, dtype=np.float32)

    params_sos = params.copy()
    params_sos["sos_map"] = sos_frame
    params_sos["sos_grid_x"] = sos_grid_x
    params_sos["sos_grid_z"] = sos_grid_z
    outputs_sos = pipeline(**{pipeline.key: raw}, **params_sos)

    recon_sos = keras.ops.convert_to_numpy(outputs_sos[pipeline.output_key])[0]
    print(f"Reconstructed with SoS correction: {recon_sos.shape}")

    zea.visualize.set_mpl_style()
    fig, axes = plt.subplots(1, 7, figsize=(30, 5))

    # 1: IQ magnitude for one transmit event, in dB
    tx_idx = raw.shape[1] // 2
    iq = raw[0, tx_idx, :, :, 0] + 1j * raw[0, tx_idx, :, :, 1]
    iq_db = 20 * np.log10(np.abs(iq) / np.abs(iq).max() + 1e-10)
    axes[0].imshow(iq_db, aspect="auto", cmap="gray", vmin=-80, vmax=0)
    axes[0].set_title(f"IQ magnitude (tx {tx_idx}) [dB]\nraw_data: {raw.shape}")
    axes[0].set_xlabel("Element")
    axes[0].set_ylabel("Axial sample")

    # 2: Stored B-mode (DAS)
    axes[1].imshow(img[0], aspect="auto", cmap="gray", extent=coords_to_imshow_mm(img_coords))
    axes[1].set_title(f"B-mode (DAS, stored)\nimage: {img.shape}")
    axes[1].set_xlabel("Lateral [mm]")
    axes[1].set_ylabel("Depth [mm]")

    # 3: Stored DBUA
    axes[2].imshow(
        focused[0], aspect="auto", cmap="gray", extent=coords_to_imshow_mm(focused_coords)
    )
    axes[2].set_title(f"B-mode (DBUA, stored)\nbmode_focused: {focused.shape}")
    axes[2].set_xlabel("Lateral [mm]")
    axes[2].set_ylabel("Depth [mm]")

    # 4: zea-reconstructed B-mode (DAS pipeline on raw_data)
    stored_ext = coords_to_imshow_mm(img_coords)
    axes[3].imshow(recon, aspect="auto", cmap="gray", vmin=-60, vmax=0, extent=recon_ext)
    axes[3].set_xlim(stored_ext[0], stored_ext[1])
    axes[3].set_ylim(stored_ext[2], stored_ext[3])
    axes[3].set_title(f"B-mode (DAS, zea)\nreconstructed: {recon.shape}")
    axes[3].set_xlabel("Lateral [mm]")
    axes[3].set_ylabel("Depth [mm]")

    # 5: SOS map
    im = axes[4].imshow(sos[0], aspect="auto", cmap="hot", extent=coords_to_imshow_mm(sos_coords))
    plt.colorbar(im, ax=axes[4], label="m/s")
    axes[4].set_title(f"Speed of sound\nsos_map: {sos.shape}")
    axes[4].set_xlabel("Lateral [mm]")
    axes[4].set_ylabel("Depth [mm]")

    # 6: zea-reconstructed B-mode with SoS correction
    axes[5].imshow(recon_sos, aspect="auto", cmap="gray", vmin=-60, vmax=0, extent=recon_ext)
    axes[5].set_xlim(stored_ext[0], stored_ext[1])
    axes[5].set_ylim(stored_ext[2], stored_ext[3])
    axes[5].set_title(f"B-mode (DAS + SoS, zea)\nreconstructed: {recon_sos.shape}")
    axes[5].set_xlabel("Lateral [mm]")
    axes[5].set_ylabel("Depth [mm]")

    # 7: Segmentation overlaid on focused (DBUA) B-mode
    axes[6].imshow(
        focused[0], aspect="auto", cmap="gray", extent=coords_to_imshow_mm(focused_coords)
    )
    axes[6].imshow(
        seg[0, :, :, 1],
        aspect="auto",
        cmap="Reds",
        alpha=0.4,
        extent=coords_to_imshow_mm(seg_coords),
    )
    axes[6].set_title(f"Segmentation on DBUA\nlabels: {list(labels)}")
    axes[6].set_xlabel("Lateral [mm]")
    axes[6].set_ylabel("Depth [mm]")

    fig.suptitle(f"open-h-rf sample (phase error: {phase_err[0]:.2f} rad)", fontsize=14, y=1.02)
    plt.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
