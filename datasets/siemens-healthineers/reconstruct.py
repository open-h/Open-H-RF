# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the siemens-healthineers dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/siemens-healthineers

B-mode reconstruction of in-vivo IQ channel data from a clinical scanner.

``data/image`` was produced by this same processing at conversion time, so the
reconstruction reproduces it exactly -- a round-trip check on the converted
data. The grid and display range live in ``pipeline.yaml``.

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
import zea
from zea import Config, File, Pipeline

HERE = Path(__file__).parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/siemens-healthineers/data/Subject_01_acq_006.hdf5"
CONFIG = HERE / "pipeline.yaml"
OUT = None  # PNG path (default: <input>_recon.png)
FRAME = 0
HF_CONFIG = "hf://nvidia/Open-H-RF/siemens-healthineers/pipeline.yaml"  # where CONFIG is published


def main():
    output = OUT or HERE / "assets" / f"{Path(ZEA_FILE).stem}_recon.png"

    zea.init_device()
    config = Config.from_path(str(CONFIG))

    with File(str(ZEA_FILE)) as f:
        params = f.load_parameters(**config.parameters)
        raw = f.data.raw_data[FRAME : FRAME + 1]

    print(f"raw_data: {raw.shape}")

    pipeline = Pipeline.from_config(config)

    inputs = pipeline.prepare_parameters(params)
    recon = keras.ops.convert_to_numpy(pipeline(data=raw, **inputs)["data"])[0]
    recon_ext = [v * 1e3 for v in params.extent_imshow]
    print(f"Reconstructed: {recon.shape}")

    zea.visualize.set_mpl_style()
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(
        recon,
        aspect="equal",
        cmap="gray",
        vmin=params.dynamic_range[0],
        vmax=params.dynamic_range[1],
        extent=recon_ext,
    )
    ax.set_xlabel("Lateral [mm]")
    ax.set_ylabel("Depth [mm]")
    plt.tight_layout()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output, dpi=150, bbox_inches="tight")
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
