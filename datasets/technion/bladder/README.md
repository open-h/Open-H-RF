---
name: technion-bladder
pretty_name: "Technion Bladder Pre-Beamformed Channel Data"
license: cc-by-4.0
task_categories:
  - image-to-image
tags:
  - ultrasound
  - iq
  - open-h-rf
  - beamforming
  - bladder
  - 3d
language:
  - en
size_categories:
  - 1K<n<10K
---

# Technion In-vivo Bladder Pre-beamformed RF Channel Data

![Transverse suprapubic view of the bladder, one 10-frame cine loop](assets/cine.gif)

*Transverse suprapubic view: one cine loop (10 frames) from [`data/a1.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/technion/bladder/data/a1.hdf5).*

## Dataset Description

Real, **in-vivo human** pre-beamformed ultrasound **channel data** for bladder imaging: per-element I/Q recorded before receive beamforming on a 64-element phased array — a sector scan of 180 transmit beams steered over ±45.13° (≈90°), one image line per transmit (steering angles in `scan.polar_angles`). 1,508 frames across 14 sweeps from seven subjects. Acquired on a GE research system in tissue-harmonic mode; the harmonic echo is demodulated to I/Q at 3.44 MHz and band-pass filtered. No paired image is supplied — the B-mode is reproduced from the channel data by the released beamformer.

## Dataset Contributor(s)

- Sanketh Vedula <sanketh@campus.technion.ac.il> (primary contact)
- Ortal Senouf
- Dean Zadok
- Alex M. Bronstein (PI)
- Technion – Israel Institute of Technology

## Dataset Creation Date

Source data 2018; converted to the Open-H-RF (zea) format 07/16/2026.

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

Primary: **generalized reconstruction** (§6.1) — learned receive beamforming and image reconstruction from raw channel data. The quasi-static bladder is also suited to multi-line-transmission (MLT) emulation and high-frame-rate research, and to anatomy/cohort interpretation (§6.5).

## Dataset Characterization

- **Data Collection Method:** in-vivo human (research platform) — GE Vivid S70 scanner with raw per-element channel access, tissue-harmonic mode.
- **Labeling Method:** N/A — no per-frame image label; the `zea.Pipeline` in `pipeline.yaml` reconstructs a B-mode from the channel data for validation.
- **Acquisition system:** GE Vivid S70 scanner; GE 3Sc-RS 64-element phased-array probe, 0.30 mm pitch; sector scan, 180 transmit beams steered over ±45.13° (≈90.25° FOV), one image line per transmit. Per proposal: 2.56-cycle 1.6 MHz transmit, no transmit apodization, tissue-harmonic mode, harmonic echo demodulated to I/Q at 3.44 MHz and filtered, ~18 fps; transversal plane with slow longitudinal probe sweep to decorrelate frames.

## Processing the Dataset

The acquisitions can be processed with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea).

`zea` streams the data from the Hugging Face Hub and processes it according to the pipeline. You can try it out with the following command:

```bash
zea process \
  --dataset hf://nvidia/Open-H-RF/technion/bladder/data/a1.hdf5 \
  --config hf://nvidia/Open-H-RF/technion/bladder/pipeline.yaml \
  --n-frames 10
```

Alternatively, you can use the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/technion/bladder/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF).

## Dataset Format

[zea v0.1.4](https://github.com/tue-bmd/zea)

zea file format, one HDF5 file per sweep (`data/<subject>.hdf5`, e.g. `a1.hdf5`, `ak.hdf5`, `s2.hdf5`). The source complex `double` samples were repackaged to `float32` I/Q with I and Q on the final channel axis (`n_ch = 2`); values are otherwise verbatim (band-pass filtered baseband IQ, as archived). Each file carries `metadata/subject/{id,type=human}`, `metadata/credit`, and `metadata/annotations/{anatomy=bladder, label=in vivo, view=transverse suprapubic pelvic ultrasound}`. Probe model (`probe.name = GE 3Sc-RS`) and scanner (`us_machine = GE Vivid S70`) are stored too.

## Dataset Quantification

**Current Open-H-RF release:** 14 HDF5 files; 83.71 GB (83,713,785,856 bytes) stored; root `zea_version` **0.1.4**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- **Frames / sweeps / subjects:** 1,508 frames · 14 sweeps · 7 subjects.
- **Train / val / test split:** N/A (contributor to define).
- **Stored HDF5 size:** 83.71 GB (83,713,785,856 bytes).

| Field | Shape | dtype | Units | Description |
|---|---|---|---|---|
| `data/raw_data` | `(n_frames, 180, 696, 64, 2)` | float32 | a.u. | pre-BF channel IQ: frames × tx-lines × axial × elements × {I, Q} |
| `scan/sampling_frequency` | scalar | float32 | Hz | 3.333 MHz (IQ sample rate, from `specs`) |
| `scan/center_frequency`, `demodulation_frequency` | scalar | float32 | Hz | 3.44 MHz (tissue-harmonic demod, from `specs`) |
| `scan/sound_speed` | scalar | float32 | m/s | 1540 |
| `scan/polar_angles` | `(180,)` | float32 | rad | ±45.13° steered lines (`thetaTX`) |
| `probe/probe_geometry` | `(64, 3)` | float32 | m | element positions, 0.30 mm pitch |

## Subject Metadata

**Seven in-vivo human volunteers**, 14 sweeps, 1,508 frames. (The proposal's "six" was an undercount; verified from the acquisitions to be seven distinct volunteers.) No phantom is included in this collection — the calibration phantom is a separate submission (`../phantom/`). No PHI stored: only anonymized `subject.id`, `subject.type = human`, and `annotations.anatomy = bladder`. Age and sex were not recorded for these acquisitions.

| Subject | Sweeps (files) | Frames |
|---|---|---|
| A | `a1`, `a2` | 215 |
| AK | `ak` | 107 |
| H | `h1`, `h2` | 216 |
| O | `o1` | 108 |
| OK | `ok1`, `ok2` | 216 |
| P | `p1a`, `p1b`, `p2a`, `p2b` | 430 |
| S | `s1`, `s2` | 216 |

## Data Validation

`reconstruct.py` reconstructs a B-mode from `raw_data` using the `zea.Pipeline` defined in `pipeline.yaml`: delay-and-sum beamforming on a polar scanline grid (one image line per transmit, receive dynamic focusing) → envelope detection → normalization → log compression → sector scan conversion.

Reference output: `bmode.png` — frame 30 of `data/a1.hdf5` (in `assets/`). The pipeline matches the acquisition's own receive-beamforming geometry (`code/processing/`), so the reconstruction reproduces the expected sector B-mode.

## Known Issues

- **No paired image target** (unlike the cardiac set); the B-mode is derived from the channel data, not supplied.
- **Transmit fundamental (1.6 MHz) not stored** — only the 3.44 MHz demodulation frequency is in the files, so `center_frequency` equals the demodulation frequency.

## Ethical Considerations

**Privacy safeguards (HIPAA and GDPR).** Pre-beamformed RF channel data contains no facial or otherwise identifying imagery. All records are de-identified to the HIPAA Safe Harbor standard, with direct identifiers removed and any dates generalized to bands. As an EU institution we additionally comply with GDPR, holding any pseudonymized subject identifiers separately on access-controlled storage and never sharing them. The released data are de-identified and contain only the channel signals and acquisition metadata.

**Ethics.** The data were collected under ethical best practices on healthy volunteers.

The contributors confirm intent to release under CC BY 4.0 with no third-party IP encumbrances (proposal §8).
