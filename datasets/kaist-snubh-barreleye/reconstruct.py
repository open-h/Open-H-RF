# SPDX-License-Identifier: Apache-2.0
"""Example reconstruction script for the kaist-snubh-barreleye dataset of Open-H-RF.

Dataset link: https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/kaist-snubh-barreleye

B-mode reconstruction of 9-angle plane-wave compounded in-vivo breast channel data.
The 1-12 MHz band-pass rejects a persistent sub-MHz band before coherent
beamforming, which allows the raw RF (n_ch=1) to demodulate and beamform
cleanly.

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
from zea import Config, File, Pipeline

HERE = Path(__file__).parent

# --- Inputs -----------------------------------------------------------------
# Defaults stream straight from the published corpus. Swap any of these for a
# local path to run against your own copy.
ZEA_FILE = "hf://nvidia/Open-H-RF/kaist-snubh-barreleye/data/S01_D1.hdf5"
CONFIG = "hf://nvidia/Open-H-RF/kaist-snubh-barreleye/pipeline.yaml"
OUT = HERE / "assets" / "reconstruction.png"


def main():
    zea.init_device()
    config = Config.from_path(CONFIG)

    with File(str(ZEA_FILE)) as f:
        parameters = f.load_parameters(**config.parameters)
        raw = f.data.raw_data[:]
        patient = f.metadata.subject.id
        label = f.metadata.annotations.label

    pipeline = Pipeline.from_config(config)
    inputs = pipeline.prepare_parameters(parameters)
    outputs = pipeline(data=raw, **inputs)
    recon = keras.ops.convert_to_numpy(outputs[pipeline.output_key])[0]

    zea.visualize.set_mpl_style()
    fig, ax = plt.subplots(figsize=(5.5, 6))
    ax.imshow(
        zea.display.to_8bit(recon, dynamic_range=parameters.dynamic_range),
        cmap="gray",
        extent=np.asarray(parameters.extent_imshow) * 1e3,
        aspect="equal",
    )
    ax.set_xlabel("lateral [mm]")
    ax.set_ylabel("depth [mm]")
    ax.set_title(f"{Path(ZEA_FILE).stem} — patient {patient} ({label})")
    fig.tight_layout()
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(OUT), dpi=130, bbox_inches="tight")
    print(f"raw {raw.shape} -> B-mode {recon.shape}; saved {OUT}")


if __name__ == "__main__":
    main()
