---
name: oslo-f-motion
pretty_name: "USTB - Motion Estimation (SWE / ARFI, Verasonics L7-4)"
license: cc-by-4.0
task_categories:
  - image-to-image
language:
  - en
tags:
  - ultrasound
  - rf
  - open-h-rf
  - elastography
  - shear-wave
  - arfi
size_categories:
  - n<1K
---

# USTB - Motion Estimation (SWE / ARFI, Verasonics L7-4)

![Shear waves travelling outward after an acoustic push](assets/hero.gif)

*First push-track sequence (frames 1-49) of [`SWE_L7_type_III.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/oslo/F_motion/SWE_L7_type_III.hdf5): B-mode (left) and axial displacement between consecutive frames (right), a lag-one autocorrelation (Kasai) estimate on the IQ beamformed with `pipeline.yaml`. The displacement estimate is not part of the reference pipeline.*

## Dataset Description

Part of the **UltraSound ToolBox (USTB) Channel Capture Collection** (see the [collection card](../README.md)).

Shear-wave elastography (SWE) and acoustic-radiation-force-impulse (ARFI) push-tracking phantom acquisitions on a Verasonics Vantage 256 with an L7-4 linear array. Each acquisition contains many high-frame-rate tracking frames following an acoustic push, suitable for tissue-motion and shear-wave-velocity estimation.

## Dataset Contributor(s)

- Ole Marius Hoel Rindal <omrindal@ifi.uio.no> (primary contact)
- Yucel Karabiyik
- Sven Peter Nasholm
- Andreas Austeng
- University of Oslo (UiO), Department of Informatics

## Dataset Creation Date

06/23/2026 (packaging date; original acquisitions/simulations were produced between 2016 and 2023).

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

Motion estimation (RFP task 6.4): shear-wave velocity estimation, ARFI displacement tracking, and high-frame-rate motion reconstruction. (Open-H-RF RFP task 6.4 Motion Estimation).

## Dataset Characterization

- **Data Collection Method:** phantom
- **Labeling Method:** Derived (elastography phantom of known/typical stiffness classes).
- **Acquisition system:** probe(s) L7-4; element positions stored in `/probe/probe_geometry` (meters); center frequency, sampling frequency and sound speed stored per acquisition in `/scan` (see per-sample feature table).

## Processing the Dataset

The example acquisition can be processed with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea).

`zea` streams the data from the Hugging Face Hub and processes it according to the pipeline. You can try it out with the following command:

```bash
zea process \
  --dataset hf://nvidia/Open-H-RF/oslo/F_motion/SWE_L7_type_III.hdf5 \
  --config hf://nvidia/Open-H-RF/oslo/F_motion/pipeline.yaml
```

This `pipeline.yaml` holds the pipeline and display window of that acquisition. Alternatively, all acquisitions can be processed with the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/oslo/reconstruct.py) at the root of this collection, as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF), together with the `pipeline*.yaml` definitions at the collection root and the [zea library](https://github.com/tue-bmd/zea). The script streams the data from the Hugging Face Hub; `parameters.yaml` picks the pipeline, display window and dynamic range per acquisition (see the [collection card](../README.md#processing-the-dataset)). These plane-wave tracking acquisitions use the non-focused `compound` pipeline, and the reference reconstruction shows a single tracking frame.

## Dataset Format

[zea v0.1.6](https://github.com/tue-bmd/zea)

All acquisitions are stored in the **zea** HDF5 file format. Each `.hdf5` file is a single acquisition with raw channel data `/data/raw_data` of shape `(n_frames, n_tx, n_ax, n_el, n_ch)` and a fully populated `/scan` group describing the transmit sequence (delays, focus distances, steering angles, apodization, timing). Data type: RF (n_ch=1). No demodulation or decimation was applied during packaging beyond conversion from the USTB Ultrasound File Format (UFF) to zea; RF data is demodulated inside the reconstruction pipeline.

## Dataset Quantification

**Current Open-H-RF release:** 4 HDF5 files; 354.42 MB (354,418,688 bytes) stored; root `zea_version` **0.1.6**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- **Number of acquisitions:** 4
- **Total channel-capture frames:** 800
- **Train / validation / test split:** not predefined (research dataset).
- **Stored HDF5 size:** 354.42 MB (354,418,688 bytes).

Per-acquisition summary:

| Acquisition | frames | transmits | samples | elements | n_ch | fs (MHz) | fc (MHz) | size (MB) |
|---|---|---|---|---|---|---|---|---|
| `ARFI_dataset` | 200 | 1 | 1664 | 128 | 1 | 20.8 | 5.21 | 157.42 |
| `SWE_L7_type_I` | 200 | 1 | 1664 | 128 | 1 | 20.8 | 5.21 | 65.67 |
| `SWE_L7_type_III` | 200 | 1 | 1664 | 128 | 1 | 20.8 | 5.21 | 65.67 |
| `SWE_L7_type_IV` | 200 | 1 | 1664 | 128 | 1 | 20.8 | 5.21 | 65.67 |

Per-sample feature table:

| Field | Shape | Dtype | Units | Description |
|---|---|---|---|---|
| `data/raw_data` | `(n_frames, n_tx, n_ax, n_el, n_ch)` | float32 | a.u. | Raw pre-beamformed RF channel data |
| `scan/sampling_frequency` | `scalar` | float32 | Hz | A/D sampling frequency |
| `scan/center_frequency` | `scalar` | float32 | Hz | Transmit pulse center frequency |
| `scan/demodulation_frequency` | `scalar` | float32 | Hz | Demodulation (carrier) frequency |
| `scan/sound_speed` | `scalar` | float32 | m/s | Assumed medium speed of sound |
| `scan/initial_times` | `(n_tx,)` | float32 | s | A/D start time per transmit |
| `scan/t0_delays` | `(n_tx, n_el)` | float32 | s | Per-element transmit fire times |
| `scan/tx_apodizations` | `(n_tx, n_el)` | float32 | - | Per-element transmit apodization |
| `scan/focus_distances` | `(n_tx,)` | float32 | m | Focus distance per transmit (0 = plane wave) |
| `scan/polar_angles` | `(n_tx,)` | float32 | rad | Transmit steering (polar) angle |
| `scan/transmit_origins` | `(n_tx, 3)` | float32 | m | Transmit beam origin (x, y, z) |
| `probe/probe_geometry` | `(n_el, 3)` | float32 | m | Element positions (x, y, z) |

## Subject Metadata

No human or animal subjects. Elastography phantoms. Scanner: Verasonics Vantage 256. Probe: L7-4 linear array (128 elements).

## Data Validation

A Delay-And-Sum `zea.Pipeline` (`cast -> demodulate -> delay-and-sum beamform -> envelope detect -> normalize -> log compress`; RF is demodulated in-pipeline, IQ uses a baseband pipeline) reconstructs every acquisition as a portable check that the recorded geometry and timing are correct (see *Processing the Dataset*).

The reference B-mode images committed alongside the data (`<name>_bmode.png`) are produced with the UltraSound ToolBox (USTB) MATLAB Delay-And-Sum beamformer — the exact per-dataset reconstruction used in the public USTB dataset catalog (https://unioslo.github.io/USTB/datasets.html). These are the recommended reference reconstructions for visual verification.

## Known Issues

Push-track sequences contain many frames at a high frame rate; the B-mode reference reconstruction shows a single tracking frame. Displacement/velocity estimation requires frame-to-frame processing not included in the reference pipeline. The displacement estimation as implemented in the UltraSound ToolBox (USTB) can be provided/added for these motion datasets on request if needed.

## Ethical Considerations

Phantom acquisitions; no human or animal subjects. No ethical considerations beyond standard laboratory practice.

## Citation

Please cite the UltraSound ToolBox (USTB) Channel Capture Collection, University of Oslo (Zenodo record 20261898).
