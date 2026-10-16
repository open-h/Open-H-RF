---
name: resolvestroke-phantom-mp
pretty_name: "Resolve Stroke Multi-tissue Phantom (CIRS 040GSE)"
license: cc-by-4.0
task_categories:
  - other
tags:
  - ultrasound
  - iq
  - open-h-rf
  - 3d
  - matrix-probe
  - phantom
language:
  - en
size_categories:
  - 1K<n<10K
---

# Resolve Stroke Multi-tissue Phantom (CIRS 040GSE)

![Reference B-mode (two perpendicular sectors)](../assets/phantom_mp_bmode.png)

*B-mode of one frame, x-z and y-z sectors, reconstructed from [`phantom_mp.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/resolvestroke/phantom_mp/phantom_mp.hdf5).*

## Dataset Description

Pre-beamformed channel-data acquisition of a multi-purpose, multi-tissue imaging phantom (CIRS 040GSE). Acquired with SYLVER, Resolve Stroke's ultrasound device, using a 32×32 matrix probe with diverging-wave transmits at 4 kHz frame rate. A single transmit insonifies a 3D volume, so each frame is a full volumetric capture of the static phantom (wire targets, cysts, and tissue-mimicking background). The file holds 1000 consecutive frames of the same scene.

## Dataset Contributor(s)

- Aitana Waelbroeck
- Carl Ferlay
- Arthur Chavignon
- Maxence Reberol <maxence.reberol@resolvestroke.com> (contact)
- Vincent Hingot
- Resolve Stroke, 29 Rue du Faubourg Saint-Jacques, 75014 Paris

## Dataset Creation Date

01/23/2026

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

Beamforming and reconstruction research (RFP task group 6.1, Generalized Reconstruction): resolution and contrast assessment, compressed sensing, super-resolution, and matrix-probe diverging-wave 3D beamforming on a phantom with known target structures.

## Dataset Characterization

- Data collection method: Phantom (CIRS 040GSE multi-purpose, multi-tissue imaging phantom)
- Labeling method: None (single static acquisition; no per-frame labels)
- Acquisition system: SYLVER (Resolve Stroke's ultrasound device). 32×32 matrix probe, 0.50 mm pitch, 0.30 mm kerf; transmit center frequency ≈ 2.031 MHz, sound speed 1540 m/s. Diverging-wave transmits; receive sub-apertures flattened into 256 virtual elements. Channel data is DDC (baseband) IQ, so `sampling_frequency` (≈ 2.031 MHz) is the post-decimation IQ rate and equals `demodulation_frequency`.

## Processing the Dataset

The acquisitions can be processed with the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/resolvestroke/phantom_mp/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF), together with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea). The script streams the data from the Hugging Face Hub.

```bash
uv run --project /path/to/Open-H-RF python reconstruct.py
```

The Python scripts carry their own `SPDX-License-Identifier: Apache-2.0` header; the dataset itself is CC BY 4.0.

## Dataset Format

[zea v0.1.6](https://github.com/tue-bmd/zea)

Single zea HDF5 file (`phantom_mp.hdf5`), one track holding the raw channel data and scan parameters, in the zea HDF5 format, root `zea_version` 0.1.6, validated `compliant: true` against `validate_zea_spec.py`. `data/raw_data` is DDC IQ (last axis [I, Q]). The hardware time-gain compensation is baked into `raw_data`; `scan/tgc_gain_curve` is the applied (non-linear) gain per axial sample; divide by it to recover true channel amplitudes. `reconstruct.py` divides `raw_data` by this curve before beamforming (the `zea.Pipeline` itself stays standard; the reversal is a plain array step).

## Dataset Quantification

**Current Open-H-RF release:** 1 HDF5 file; 33.75 MB (33,751,040 bytes) stored; root `zea_version` **0.1.6**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- Frames: 1000 (single acquisition)
- Train / val / test split: N/A
- **Stored HDF5 size:** 33.75 MB (33,751,040 bytes).

| Field | Shape | dtype | Units | Description |
|---|---|---|---|---|
| `data/raw_data` | `(1000, 1, 320, 256, 2)` | int16 | n/a | IQ channel data: frames × tx × axial × elements × {I, Q} |
| `probe/probe_geometry` | `(256, 3)` | float32 | m | Virtual element positions |
| `scan/t0_delays` | `(1, 256)` | float32 | s | Per-element transmit delays |
| `scan/tx_apodizations` | `(1, 256)` | float32 | n/a | Per-element transmit weights |
| `scan/focus_distances` | `(1,)` | float32 | m | Virtual-source distance (diverging wave, negative) |
| `scan/polar_angles` | `(1,)` | float32 | rad | Transmit steering (0) |
| `scan/azimuth_angles` | `(1,)` | float32 | rad | Transmit steering (0) |
| `scan/transmit_origins` | `(1, 3)` | float32 | m | Transmit origin |
| `scan/initial_times` | `(1,)` | float32 | s | ADC start time |
| `scan/tgc_gain_curve` | `(320,)` | float32 | n/a | Hardware TGC applied to `raw_data`; divide by it to undo (`reconstruct.py` does this before beamforming) |
| `scan/sampling_frequency` | scalar | float32 | Hz | 2031250 (post-DDC IQ rate) |
| `scan/center_frequency` | scalar | float32 | Hz | 2031250 |
| `scan/demodulation_frequency` | scalar | float32 | Hz | 2031250 |
| `scan/sound_speed` | scalar | float32 | m/s | 1540 |

## Subject Metadata

- Type: Phantom (CIRS 040GSE multi-purpose, multi-tissue imaging phantom)
- Contrast agent: None
- Motion: None (static scene)

## Data Validation

`reconstruct.py` first divides `raw_data` by `scan/tgc_gain_curve` (reverse TGC), then runs a standard `zea.Pipeline` (cast → DAS beamform → envelope → normalize → log-compress) defined in `pipeline.yaml` to reconstruct a B-mode from the IQ channel data. Because the probe is a 2D matrix array insonified by a single diverging-wave transmit, `reconstruct.py` beamforms on polar (sector) grids and renders two perpendicular sector B-modes, the x-z plane (y = 0) and the y-z plane (x = 0), side by side, as shown at the top of this card.

## Known Issues

- `raw_data` has the hardware TGC baked in; `scan/tgc_gain_curve` is that (non-linear) applied curve. The reconstruction script divides by the curve before beamforming; a downstream user reconstructing directly must divide by the curve too.
- `sampling_frequency ≈ center_frequency` because the data is DDC baseband IQ (see Dataset Characterization), not an RF acquisition.
- The proposed 3D phantom-geometry reference (known target positions for the CIRS 040GSE) is not yet included.

## Ethical Considerations

Phantom data: no human subjects, no ethical concerns.
