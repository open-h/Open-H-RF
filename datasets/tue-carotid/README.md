---
name: tue-carotid
pretty_name: "TU/e carotid 2023"
license: cc-by-4.0
zea_repo_id: zeahub/zea-carotid-2023
task_categories:
  - image-classification
tags:
  - ultrasound
  - rf
  - open-h-rf
  - carotid
  - in-vivo
language:
  - en
---


# TU/e Carotid 2023

![Longitudinal view of a carotid bifurcation](assets/5_long_bifur_R_0000.gif)

*One cardiac cycle of a longitudinal bifurcation scan, [`data/5_long_bifur_R_0000.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/tue-carotid/data/5_long_bifur_R_0000.hdf5).*


## Dataset Description

The dataset includes carotid artery scans from 10 subjects. Each file includes 150 frames, at least one cardiac cycle. The acquisition scheme it consists of 128 line scanning interleaved with 21 plane waves.

Included views:

- Bifurcation cross section
- Longitudinal bifurcation
- Cross section 2cm from bifurcation
- Cross section 1cm from bifurcation
- Longitudinal section 2cm from bifurcation
- Longitudinal section 1cm from bifurcation
- Longitudinal section

The acquisitions were performed with a Verasonics 256. The acquisitions were performed with a linear probe (Verasonics L11-5v). The same operator performed all acquisitions.

## Dataset Contributor(s)

- Wessel van Nierop <w.l.v.nierop@tue.nl>
- Tristan Stevens
- Oisín Nolan
- Simon Penninga
- Beatrice Federici
- Vincent van der Schaft
- Ben Luijten
- Ruud van Sloun

## Dataset Creation Date

Nov 2023

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

Image-quality / beamforming has both plane-wave (21) and focused acquisitions (128).

## Dataset Characterization

- Data Collection Method: In-vivo Human Data
- Labeling Method: acquisitions per view
- Acquisition system: see file

## Processing the Dataset

The acquisitions can be processed with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea).

`zea` streams the data from the Hugging Face Hub and processes it according to the pipeline. You can try it out with the following command:

```bash
zea process \
  --dataset hf://nvidia/Open-H-RF/tue-carotid/data/5_long_bifur_R_0000.hdf5 \
  --config hf://nvidia/Open-H-RF/tue-carotid/pipeline.yaml
```

Alternatively, you can use the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/tue-carotid/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF).

## Dataset Format

[zea v0.1.6](https://github.com/tue-bmd/zea)

## Dataset Quantification

**Open-H-RF release:** 80 HDF5 files; 435.40 GB (435,403,030,528 bytes) stored; root `zea_version` **0.1.6**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- **Samples / frames / acquisitions:** 80 acquisitions (one HDF5 file each) from 10 subjects, 150 frames per acquisition — 12,000 frames total.
- **Transmit events per frame:** 149 — 128 focused lines interleaved with 21 plane waves.
- **Train / validation / test split:** none; each file is a single acquisition.
- **Total size on disk:** 435.40 GB (435,403,030,528 bytes).

### Per-File Feature Summary

Every file has one track (`tracks/track_0`) with the same field structure; `n_frames = 150`, `n_tx = 149`, `n_ax = 2176`, `n_el = 128`.

| Field | Shape | Dtype | Units | Description |
|---|---|---|---|---|
| `tracks/track_0/data/raw_data` | `(150, 149, 2176, 128, 1)` | int16 | ADC counts | Raw per-element RF channel data: (frames, transmits, axial samples, elements, 1) |
| `tracks/track_0/scan/t0_delays` | `(149, 128)` | float32 | s | Per-transmit, per-element transmit delay |
| `tracks/track_0/scan/tx_apodizations` | `(149, 128)` | float32 | unitless [-1, 1] | Per-transmit, per-element transmit apodization weight |
| `tracks/track_0/scan/polar_angles` | `(149,)` | float32 | rad | Per-transmit polar steering angle |
| `tracks/track_0/scan/azimuth_angles` | `(149,)` | float32 | rad | Per-transmit azimuth steering angle |
| `tracks/track_0/scan/focus_distances` | `(149,)` | float32 | m | Per-transmit focal distance (`inf` for the 21 plane waves) |
| `tracks/track_0/scan/transmit_origins` | `(149, 3)` | float32 | m | Per-transmit beam origin (x, y, z) |
| `tracks/track_0/scan/initial_times` | `(149,)` | float32 | s | Per-transmit A/D start time |
| `tracks/track_0/scan/time_to_next_transmit` | `(150, 149)` | float32 | s | Per-frame, per-transmit inter-transmit interval |
| `probe/probe_geometry` | `(128, 3)` | float32 | m | Element positions (x, y, z) |

Scalars: `probe/name` = `verasonics_l11_5v` (linear, 128 elements), `probe/probe_center_frequency` = 6.25 MHz, `scan/center_frequency` = `scan/demodulation_frequency` = 7.8125 MHz, `scan/sampling_frequency` = 31.25 MHz, `scan/sound_speed` = 1540 m/s. `us_machine` = Verasonics Vantage 256. No derived data products are stored; `raw_data` is the only `data/` field.

## Subject Metadata

None

## Known Issues

None

## Ethical Considerations

Approval was obtained from the Ethical Review Board TU/e (Eindhoven University of Technology). See Approval Letter in this folder.

Reference: ERB2023EE7 Contact details for the Ethical Review Board TU/e: T +31 (0)40 247 6259 <ethics@tue.nl> <intranet.tue.nl/ethics>
