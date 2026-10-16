---
name: nv-raw2insights-us
pretty_name: "NV-Raw2Insights-US (simulated FSA, sound-speed / aberration / segmentation)"
license: cc-by-4.0
task_categories:
  - other
tags:
  - ultrasound
  - rf
  - iq
  - open-h-rf
  - beamforming
  - sound-speed-estimation
  - phase-aberration
  - segmentation
  - simulation
language:
  - en
size_categories:
  - n<1K
---

# NV-Raw2Insights-US — Simulated FSA Channel Data with Sound-Speed, Aberration, and Segmentation Ground Truth

![DBUA B-mode reconstruction and estimated sound speed using NV-Raw2Insights-US data](assets/dbua-reconstruction.gif)

*DBUA results using synthetic validation sample [`data/nv_r2i_us_validation_0084.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/nv-raw2insights-us/data/nv_r2i_us_validation_0084.hdf5): B-mode (left) and estimated sound speed (right). Bulk-speed calibration is followed by 400 spatial-refinement iterations, with fixed display scales. These are DBUA reconstructions, not predictions from an NV-Raw2Insights-US model.*

<!-- assets/main.png is the unlabelled final B-mode panel from this run, for the dataset collage. -->

## Dataset Description

NV-Raw2Insights-US is a **simulated full-synthetic-aperture (FSA)** ultrasound dataset for training and evaluating neural networks on **sound-speed estimation**, **phase-aberration correction**, **tissue segmentation**, and **learned image reconstruction** from raw pre-beamformed channel data.

Each sample is a single-frame FSA acquisition from a **180-element linear array** simulated with **k-Wave** over a heterogeneous tissue phantom containing cysts. Every acquisition provides raw baseband **IQ channel data** alongside co-registered ground truth: a **speed-of-sound map**, a **binary cyst segmentation mask**, a **DAS B-mode** and a **focused-transmit B-mode**, and a per-sample **phase-aberration** value. All data are **synthetic**; no human or animal subjects are involved.

This is the **zea-format (Open-H-RF) release**; the same simulations are also published in a Hugging Face `datasets`/Arrow build at [`nvidia/NV-Raw2Insights-US`](https://huggingface.co/datasets/nvidia/NV-Raw2Insights-US).

## Dataset Contributor(s)

- NVIDIA Corporation

## Dataset Creation Date

12/01/2025.

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

Developing and benchmarking methods that operate on raw ultrasound channel data: learned/adaptive beamforming, sound-speed estimation, phase-aberration correction, and tissue segmentation. Because the sound-speed map, segmentation mask, and aberration value are exact simulation ground truth, the dataset supports fully-supervised training of channel-data-to-insight models.

## Dataset Characterization

- **Data Collection Method:** Synthetic — k-Wave acoustic simulation of a 180-element linear array over heterogeneous tissue phantoms with cysts.
- **Labeling Method:** Synthetic — ground truth taken directly from the simulation parameters (sound-speed map, cyst segmentation, aberration).
- **Acquisition model:** Full synthetic aperture (multi-static) — 180 single-element transmit events per frame, all 180 elements received; transmit centre frequency 6.5 MHz, baseband IQ sampled at 13.3 MHz, background sound speed 1540 m/s.

## Processing the Dataset

The acquisitions can be processed with the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/nv-raw2insights-us/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF), which uses the [zea library](https://github.com/tue-bmd/zea) and streams the data from the Hugging Face Hub. It reconstructs both a plain DAS B-mode (the `pipeline.yaml` in this folder) and a sound-speed-corrected B-mode using the ground-truth `sos_map`.

## Dataset Format

[zea v0.1.6](https://github.com/tue-bmd/zea)

Packaged in the **zea** file format (`zea_version` 0.1.6), **one HDF5 file per sample**, all under `data/`. The train/validation split is encoded in each filename (`nv_r2i_us_train_XXXX.hdf5`, `nv_r2i_us_validation_XXXX.hdf5`).

Per-file contents:

| Group / field | Shape | Dtype | Units | Description |
| --- | --- | --- | --- | --- |
| `tracks/track_0/data/raw_data` | `[1, 180, 1024, 180, 2]` | float32 | – | Baseband IQ channel data `[frame, transmit, fast-time, receive, (I,Q)]` |
| `tracks/track_0/data/image` (+ `coordinates`) | `[1, 507, 456]` | uint8 | – | Synthetic-aperture DAS B-mode reconstructed from `raw_data` |
| `tracks/track_0/data/bmode_focused` (+ `coordinates`) | `[1, 507, 456]` | uint8 | – | Focused-transmit B-mode |
| `tracks/track_0/data/sos_map` (+ `coordinates`, `unit`) | `[1, 32, 32]` | float32 | m/s | Ground-truth speed-of-sound map |
| `tracks/track_0/data/segmentation` (+ `coordinates`, `labels`) | `[1, 507, 456, 2]` | bool | – | Binary segmentation; `labels` name the classes (background tissue / cyst) |
| `metrics/common_midpoint_phase_error` | `[1]` | float32 | rad | Per-sample phase-aberration error |
| `tracks/track_0/scan/{sampling,center,demodulation}_frequency` | scalar | float32 | Hz | 13.3 MHz / 6.5 MHz / 6.5 MHz |
| `tracks/track_0/scan/sound_speed` | scalar | float32 | m/s | Background sound speed (1540) |
| `tracks/track_0/scan/{initial_times, t0_delays, tx_apodizations, transmit_origins, focus_distances, polar_angles, azimuth_angles}` | per-transmit | float32 | s / – / m / rad | Full-synthetic-aperture transmit description (single-element transmits) |
| `probe/probe_geometry` | `[180, 3]` | float32 | m | Element positions (x, y, z) |
| `probe/name` | str | – | – | Transducer identifier |
| `metadata/annotations/{anatomy, label}`, `metadata/subject/type`, `metadata/credit` | str | – | – | Aggregate/de-identified metadata (subject type = simulation) |

## Dataset Quantification

**Current Open-H-RF release:** 923 HDF5 files; 214.13 GB (214,133,178,368 bytes) stored; root `zea_version` **0.1.6**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- **923 samples (830 train / 93 validation)**, one HDF5 per sample, all in `data/`; the split is carried in the filename.
- Each sample is a single-frame FSA acquisition (frame index always 0).

## Subject Metadata

- **Synthetic only** — no human or animal subjects. Each sample is a k-Wave simulation over a digital tissue phantom containing cysts.
- No PHI; `subject/type` is a simulation label, not a patient identifier.

## Data Validation

Each file's `tracks/track_0/data/image` is a DAS B-mode reconstructed from `raw_data` by the zea pipeline (see `pipeline.yaml`), so the reconstruction is reproducible from the raw channel data and the recorded transmit description.

## Known Issues

- `sos_map` is a coarse `32 × 32` grid while the B-mode and segmentation are on the fine `507 × 456` grid; each carries its own `coordinates` for alignment.
- Cysts that touch the edge of the B-mode frame are not included in the segmentation mask.
- Some regions of gross reverberation artifact can be incorrectly segmented as cysts.

## Ethical Considerations

The data are entirely synthetic (k-Wave simulation of digital phantoms). There are no human participants, animal subjects, patient identifiers, or protected health information. Released under CC BY 4.0 for research and technical evaluation, not clinical decision-making.

## Source Dataset & Citation

This is the **zea-format conversion** of the original **NV-Raw2Insights-US** dataset published by NVIDIA on Hugging Face:
<https://huggingface.co/datasets/nvidia/NV-Raw2Insights-US>. The raw
simulations, ground-truth labels, and normalization statistics originate there; please cite the original dataset:

```bibtex
@misc{nv_raw2insights_us_2026,
  title={NV-Raw2Insights-US},
  author={{NVIDIA Corporation}},
  year={2026},
  publisher={NVIDIA Corporation},
  howpublished={\url{https://huggingface.co/datasets/nvidia/NV-Raw2Insights-US}},
  license={CC BY 4.0}
}
```
