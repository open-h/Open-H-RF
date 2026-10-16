---
name: vanderbilt
pretty_name: "Vanderbilt / Multi-Frame Focused Transmit Echocardiography Channel Dataset"
license: cc-by-4.0
task_categories:
  - image-reconstruction
tags:
  - ultrasound
  - rf
  - open-h-rf
  - echocardiography
  - cardiac
  - harmonic-imaging
  - phased-array
language:
  - en
size_categories:
  - n<1K
---

# Vanderbilt Multi-Frame Focused Transmit Echocardiography Channel Dataset

![Cineloop of the left atrial appendage](assets/118420_1_Focused_Uncoded_TX.gif)

*One cineloop of a fundamental focused-transmit acquisition, [`data/Fundamental/118420_1_Focused_Uncoded_TX.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/vanderbilt/data/Fundamental/118420_1_Focused_Uncoded_TX.hdf5).*

## Dataset Description

This multi-frame focused transmit echocardiography channel dataset contains over 2000 frames of fundamental and harmonic data acquired with the P4-2v probe on a Verasonics Vantage 128. This dataset was originally acquired to visualize the left atrial appendage in patients following transesophageal echocardiography. Some patients have atrial fibrillation, which can cause blood clots to form in the appendage.

Each dataset follows the naming convention of `subject_id`_`view_number`_`sequence_type`. `subject_id` is a six-digit random number. `view_number` distinguishes between multiple views acquired on the same subject. `sequence_type` is either Focused_Uncoded_TX or Harmonic_Focused_Uncoded_TX.

## Dataset Contributor(s)

- Brett Byram (PI)
- Christopher Khan
- Ying-Chun (Preston) Pan
- Zoe Marshall
- Vanderbilt University

## Dataset Creation Date

07/11/2026

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

This dataset could be useful for training a domain-adaptive network, as it captures a wide range of in vivo image quality. It might also be useful for training a model that converts fundamental to harmonic data — note that the harmonic and fundamental data are not matched (see Dataset Characterization). It contains view names provided by the physician at the time of acquisition, but these views were often slightly modified to accommodate the patient (see Subject Metadata). It could also be useful for identifying thrombus in the left atrial appendage, as ~10% of the dataset came from patients with a thrombus (see Subject Metadata).

## Dataset Characterization

- **Data Collection Method:** clinical
- **Labeling Method:** human-annotated
- **Acquisition System:** Verasonics Vantage 128, P4-2v (64 elements). Fundamental: 2.72 MHz; Harmonic: 2.08 MHz transmit / 4.16 MHz receive. Sampling rate: 10.88 MHz.
- **Frame rate:** Fundamental: 25 Hz (32 frames). Harmonic: 10 Hz (32 frames).
- Note that the fundamental and harmonic sequences are not matched or interleaved: the harmonic sequence was executed immediately after the fundamental sequence within the same Verasonics setup file.

## Processing the Dataset

The acquisitions can be processed with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea).

`zea` streams the data from the Hugging Face Hub and processes it according to the pipeline. You can try it out with the following command:

```bash
zea process \
  --dataset hf://nvidia/Open-H-RF/vanderbilt/data/Fundamental/118420_1_Focused_Uncoded_TX.hdf5 \
  --config hf://nvidia/Open-H-RF/vanderbilt/pipeline.yaml \
  --n-frames 10
```

Alternatively, you can use the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/vanderbilt/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF).

Set `ZEA_FILE` and `N_FRAMES` at the top of the script to pick a file and how many frames to beamform.

## Dataset Format

[zea v0.1.6](https://github.com/tue-bmd/zea)

All acquisitions are submitted in the *zea* file format as raw RF channel data, with no preprocessing applied.

| Group / field | Shape | Description |
|---|---|---|
| `tracks/track_0/data/raw_data` | `[n_frames, n_tx, n_ax, n_el, 1]` | Raw RF channel data (fundamental or harmonic, one file per cineloop) |

### zea 0.1.6 Migration

Files migrated with zea 0.1.6 store RF channel data at `tracks/track_0/data/raw_data`.

Two legacy scalar text fields are relocated because they are not standard zea 0.1.6 metadata fields:

| Original path | Migrated path |
|---|---|
| `metadata/imaging_view_name` | `custom/legacy_metadata/imaging_view_name` |
| `metadata/notes` | `custom/legacy_metadata/notes` |

The scalar text values, string dtypes, and original attributes are preserved. Each relocated field also has a `source_hdf5_path` attribute recording its original path. No text is reinterpreted or cleaned by this relocation. The RF data are re-saved, without intentional filtering, normalization, or other numerical preprocessing. This schema migration is not an additional de-identification pass.

The current release uses the migrated schema; inspect each file's root `zea_version` attribute and field paths when loading it. The descriptions in Subject Metadata below apply to both the original and migrated text fields.

## Dataset Quantification

**Current Open-H-RF release:** 165 HDF5 files; 185.58 GB (185,584,517,120 bytes) stored; root `zea_version` **0.1.6**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- **Samples:** 82 cineloops (32 frames each) from 30 patients — 2,624 fundamental frames
- Plus a matching set of 2,624 harmonic frames (same cineloops, harmonic sequence)
- Plus one CIRS phantom validation acquisition (`CIRS_validation/CIRS_fundamental.hdf5`, 32 frames), giving the 165 files and 5,280 frames of the current release
- **Train / validation / test split:** N/A

## Subject Metadata

- `imaging_view_name`: one of `{'apical two chamber', 'apical four chamber', 'parasternal short axis', 'parasternal long axis', 'subxiphoid', 'N/A'}`. Because acquisition occurred while patients were recovering from anesthesia, sonographers often deviated from standard view geometry to maximize image quality; as a result, these datasets should not be used to train a view classification network. The `'N/A'` label marks acquisitions that didn't approximate any standard view at all — in these cases, abandoning the standard geometry entirely was the only way to obtain reasonable image quality.
- `Notes`: unstructured free-text on patient condition and acquisition quality. Common content includes left atrial appendage occlusion devices (Watchman, Amulet, or Conformal), presence of thrombus, comorbidities such as COPD, and patient motion during acquisition.

## Data Validation

A `zea.Pipeline` (cast → demodulate → DAS beamforming → envelope detection → normalization → log compression → scan conversion) reconstructs the B-mode image from the raw channel data and is defined in `pipeline.yaml`.

## Known Issues

As mentioned in Subject Metadata, view names should only be used as a reference for interpreting the image and should not be used to train a view classification task.

## Ethical Considerations

The study was approved by Vanderbilt's IRB.
