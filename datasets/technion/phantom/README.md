---
name: technion-phantom
pretty_name: "Technion Phantom Pre-Beamformed Channel Data"
license: cc-by-4.0
task_categories:
  - image-to-image
tags:
  - ultrasound
  - iq
  - open-h-rf
  - beamforming
  - phantom
  - 3d
language:
  - en
size_categories:
  - n<1K
---

# Technion Tissue-mimicking Phantom Pre-beamformed RF Channel Data

![Tissue-mimicking phantom with point targets and an anechoic cyst](assets/bmode.png)

*Frame 6 of [`data/ph.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/technion/phantom/data/ph.hdf5), reconstructed by `reconstruct.py`.*

## Dataset Description

Pre-beamformed ultrasound **channel data** from a tissue-mimicking phantom, acquired on the same 64-element phased-array sector scheme as the in-vivo collection (180 transmit beams steered over ±45.13°, one image line per transmit), for **calibration and verification**. Contains resolvable point targets and an anechoic cyst — a clean reference for validating beamforming and reconstruction. 12 frames, one acquisition.

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

Calibration and end-to-end verification of the beamforming/reconstruction pipeline (point-target resolution, cyst contrast). Phantom tier (×1).

## Dataset Characterization

- **Data Collection Method:** phantom — tissue-mimicking phantom (Gammex 403GS LE, Gammex Inc., Middleton, WI, USA), acquired on the same scanner/probe as the in-vivo collection for calibration.
- **Labeling Method:** N/A (calibration target; known phantom geometry).
- **Acquisition system:** GE Vivid S70 scanner; GE 3Sc-RS 64-element phased-array probe, 0.30 mm pitch; sector scan, 180 transmit beams steered over ±45.13° (≈90.25° FOV), one image line per transmit; IQ demodulated at 3.44 MHz.

## Processing the Dataset

The acquisitions can be processed with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea).

`zea` streams the data from the Hugging Face Hub and processes it according to the pipeline. You can try it out with the following command:

```bash
zea process \
  --dataset hf://nvidia/Open-H-RF/technion/phantom/data/ph.hdf5 \
  --config hf://nvidia/Open-H-RF/technion/phantom/pipeline.yaml \
  --n-frames 1
```

Alternatively, you can use the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/technion/phantom/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF).

## Dataset Format

[zea v0.1.4](https://github.com/tue-bmd/zea)

zea file format, a single HDF5 file `data/ph.hdf5`. Source complex samples repackaged to `float32` I/Q (`n_ch = 2`), values verbatim. Carries `metadata/subject/{id=ph, type=phantom}`, `metadata/credit`, probe model (`probe.name = GE 3Sc-RS`) and scanner (`us_machine = GE Vivid S70`). ("phantom" is recorded only as `subject.type`, not as an anatomy or label.)

## Dataset Quantification

**Current Open-H-RF release:** 1 HDF5 file; 659.95 MB (659,947,520 bytes) stored; root `zea_version` **0.1.4**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- **Frames / acquisitions:** 12 frames · 1 acquisition.
- **Stored HDF5 size:** 659.95 MB (659,947,520 bytes).

| Field | Shape | dtype | Units | Description |
|---|---|---|---|---|
| `data/raw_data` | `(12, 180, 696, 64, 2)` | float32 | a.u. | pre-BF channel IQ: frames × tx-lines × axial × elements × {I, Q} |
| `scan/sampling_frequency` | scalar | float32 | Hz | 3.333 MHz |
| `scan/center_frequency`, `demodulation_frequency` | scalar | float32 | Hz | 3.44 MHz |
| `scan/sound_speed` | scalar | float32 | m/s | 1540 |
| `scan/polar_angles` | `(180,)` | float32 | rad | ±45.13° steered lines |
| `probe/probe_geometry` | `(64, 3)` | float32 | m | element positions, 0.30 mm pitch |

## Subject Metadata

N/A — inanimate phantom (GAMMEX 403GS LE); `subject.type = phantom`.

## Data Validation

`reconstruct.py` reconstructs a B-mode from `raw_data` using the `zea.Pipeline` in `pipeline.yaml` (delay-and-sum on a polar scanline grid → envelope → normalization → log compression → sector scan conversion).

Reference output: `bmode.png` — frame 6 of `data/ph.hdf5`, shown above: resolvable point targets and a well-defined anechoic cyst at ~65 mm.

## Known Issues

- Same scan scheme and probe as the in-vivo bladder collection (GE tissue-harmonic); acquired as its calibration reference. GAMMEX 403GS LE.

## Ethical Considerations

None — inanimate phantom, no human or animal subjects.
