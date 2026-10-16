---
name: technion-cardiac
pretty_name: "Technion Cardiac Pre-Beamformed Channel Data"
license: cc-by-4.0
task_categories:
  - image-to-image
tags:
  - ultrasound
  - iq
  - open-h-rf
  - beamforming
  - cardiac
  - 3d
language:
  - en
size_categories:
  - n<1K
---

# Technion Cardiac Pre-beamformed RF Channel Data (paired with DAS targets)

![Apical four-chamber view, one 32-frame cardiac cine loop](assets/cine.gif)

*Apical four-chamber view: one cine loop (32 frames) from [`data/c1.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/technion/cardiac/data/c1.hdf5).*

## Dataset Description

Real, **in-vivo human** pre-beamformed ultrasound **channel data** for cardiac imaging: per-element I/Q recorded before receive beamforming on a 64-element phased array — a sector scan of 140 transmit beams steered over ±37.5°, one image line per transmit (steering angles in `scan.polar_angles`). Each frame is **paired with its conventional delay-and-sum reconstruction** (stored as `beamformed_data`), making this a ready-made input→target set for learned reconstruction / beamforming. 777 frames across 25 cine loops from six subjects (a–f).

## Dataset Contributor(s)

- Sanketh Vedula <sanketh@campus.technion.ac.il> (primary contact)
- Ortal Senouf
- Dean Zadok
- Alex M. Bronstein (PI)
- Technion – Israel Institute of Technology

## Dataset Creation Date

Acquired 2018; converted to the Open-H-RF (zea) format 07/16/2026.

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

Primary: **generalized reconstruction** (§6.1) — learning to map raw per-element channel data to a focused image (learned receive/transmit beamforming, super-resolution, clutter suppression), trained and evaluated against the paired delay-and-sum target. Secondary: motion estimation across the cardiac cine loops (§6.4) and anatomy/cohort interpretation (§6.5).

## Dataset Characterization

- **Data Collection Method:** in-vivo human (research platform) — GE Vivid S70 scanner with raw per-element channel access.
- **Labeling Method:** derived ground truth — the paired `beamformed_data` is the conventional delay-and-sum reconstruction of each frame.
- **Acquisition system:** GE Vivid S70 scanner; GE 3Sc-RS 64-element phased-array probe, 0.30 mm pitch; sector scan, 140 acquisition lines over a ~75° sector (±37.5°); 2.5 MHz transmit; apical four-chamber view (A4C).

## Processing the Dataset

The acquisitions can be processed with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea).

`zea` streams the data from the Hugging Face Hub and processes it according to the pipeline. You can try it out with the following command:

```bash
zea process \
  --dataset hf://nvidia/Open-H-RF/technion/cardiac/data/c1.hdf5 \
  --config hf://nvidia/Open-H-RF/technion/cardiac/pipeline.yaml \
  --n-frames 32
```

Alternatively, you can use the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/technion/cardiac/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF).

## Dataset Format

[zea v0.1.4](https://github.com/tue-bmd/zea)

zea file format, one HDF5 file per cine loop (`data/<subject><clip>.hdf5`, e.g. `a1.hdf5` = subject a, clip 1; `f2.hdf5` = patient-set subject f). The source complex `int16` samples were repackaged to `float32` I/Q with I and Q on the final channel axis (`n_ch = 2`); values are otherwise verbatim. Each file carries `metadata/subject/{id,type=human}`, `metadata/credit`, and `metadata/annotations/{anatomy=cardiac, label=in vivo, view=apical four-chamber (A4C)}`. Probe model (`probe.name = GE 3Sc-RS`) and scanner (`us_machine = GE Vivid S70`) are stored too.

## Dataset Quantification

**Current Open-H-RF release:** 25 HDF5 files; 14.99 GB (14,992,998,400 bytes) stored; root `zea_version` **0.1.4**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- **Frames / cines / subjects:** 777 frames · 25 cine loops · 6 subjects (a–f).
- **Train / val / test split:** N/A (contributor to define; the `f2` patient set is a natural held-out cine).
- **Stored HDF5 size:** 14.99 GB (14,992,998,400 bytes).

| Field | Shape | dtype | Units | Description |
|---|---|---|---|---|
| `data/raw_data` | `(n_frames, 140, 680, 64, 2)` | float32 | a.u. | pre-BF channel IQ: frames × tx-lines × axial × elements × {I, Q} |
| `data/beamformed_data.values` | `(n_frames, 652, 140, 2)` | float32 | a.u. | paired delay-and-sum target (complex IQ): frames × depth × line × {I, Q} |
| `data/beamformed_data.coordinates` | `(652, 140, 3)` | float32 | m | per-pixel polar coordinates (⚠️ depth scale approximate) |
| `scan/sampling_frequency` | scalar | float32 | Hz | 6.0 MHz — **best estimate**, axial rate not stored (see Known Issues) |
| `scan/center_frequency`, `demodulation_frequency` | scalar | float32 | Hz | 2.5 MHz (cardiac fundamental) |
| `scan/sound_speed` | scalar | float32 | m/s | 1540 |
| `scan/polar_angles` | `(140,)` | float32 | rad | ±37.5° steered lines |
| `probe/probe_geometry` | `(64, 3)` | float32 | m | element positions, 0.30 mm pitch |

## Subject Metadata

Six subjects (a–e main set, f patient set), 777 frames across 25 cine loops. In-vivo human; no PHI stored (only `subject.id` a1…f2, `subject.type = human`, `anatomy = cardiac`, `view = apical four-chamber (A4C)`). Age and sex were not recorded for these acquisitions.

## Data Validation

`reconstruct.py` reconstructs a B-mode from `raw_data` using the `zea.Pipeline` defined in `pipeline.yaml`: delay-and-sum on a polar scanline grid (one image line per acquisition line, receive dynamic focusing) → envelope detection → normalization → log compression → sector scan conversion.

Reference output: `bmode.png` — frame 8 of `data/c1.hdf5` (in `assets/`). Each frame is also paired with its conventional delay-and-sum reconstruction in `beamformed_data` (the target for the raw→image learning task) — note its depth scale is approximate because the acquisition axial rate is not stored (see Known Issues).

## Known Issues

- **Axial sample rate not stored.** The consolidated source `.mat` files do not carry the acquisition header, so `sampling_frequency` (6.0 MHz) is a best estimate and the reconstructed depth scale is approximate. This applies both to the raw→image reconstruction and to the paired `beamformed_data` target (exact in value, approximate in depth axis).
- **Sector-angle convention.** Lines are stored as ±37.5° centred about boresight, the physically correct convention for a phased array.

## Ethical Considerations

**Privacy safeguards (HIPAA and GDPR).** Pre-beamformed RF channel data contains no facial or otherwise identifying imagery. All records are de-identified to the HIPAA Safe Harbor standard, with direct identifiers removed and any dates generalized to bands. As an EU institution we additionally comply with GDPR, holding any pseudonymized subject identifiers separately on access-controlled storage and never sharing them. The released data are de-identified and contain only the channel signals and acquisition metadata.

**Ethics.** The data were collected under ethical best practices on healthy volunteers.

The data is the contributors' own research acquisition, cleared for CC BY 4.0 with no third-party IP encumbrances.
