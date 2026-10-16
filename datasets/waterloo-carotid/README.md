---
name: waterloo-carotid
pretty_name: UW-CarotidRF
license: cc-by-4.0
task_categories:
  - other
tags:
  - ultrasound
  - rf
  - open-h-rf
  - medical-imaging
  - in-vivo
  - carotid-artery
  - beamforming
  - vector-doppler
  - vector-flow-imaging
language:
  - en
size_categories:
  - n<4.5M
---

# UW-Carotid RF

![Reconstructed cineloop from Acq1.hdf5](assets/Acq1.gif)

*Cine loop of [`data/Acq1.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/waterloo-carotid/data/Acq1.hdf5), rendered using provided velocity fields.*

## Dataset Description

Raw RF frames (plane wave) and vector flow profiles of the human carotid arteries, acquired in vivo by the LITMUS research group at the University of Waterloo with a programmable research scanner configured for high-frame-rate vector flow imaging. The dataset holds longitudinal images of the common carotid artery and cross-sectional images of the internal carotid artery, recorded to study carotid hemodynamics at baseline and during physiological maneuvers (Valsalva maneuver, head-down tilt, and supine postures).

## Dataset Contributor(s)

- Hassan Nahas <hassan.nahas@uwaterloo.ca>
- Jason Y. -H. Hsu <jason.hsu@uwaterloo.ca>
- Theresa Gu <theresa.gu@uwaterloo.ca>
- Adrian J. Y. Chee <adrian.chee@uwaterloo.ca>
- Alfred C. H. Yu <alfred.yu@uwaterloo.ca>
- LITMUS, University of Waterloo

## Dataset Creation Date

07/16/2026

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

Developing, benchmarking, and evaluating methods for ultrasound image reconstruction, motion estimation, clutter filtering, multi-angle Doppler processing, and vector flow imaging (VFI) in carotid artery imaging.

## Dataset Characterization

- **Data Collection Method:** In vivo imaging of human carotid arteries (Common Carotid Artery and Internal Carotid Artery).
- **Labeling Method:** Categorized by target artery (Anatomy), view direction (Longitudinal or Cross-sectional), and physiological condition/maneuver (Baseline, Valsalva Maneuver, Valsalva Maneuver – Supine, Valsalva Maneuver – Head Down Tilt, Head Down Tilt).
- **Acquisition system:** Raw RF data was acquired from programmable research scanners (US4R/US4R-Lite, US4US, Warsaw, Poland) equipped with an L14-5 linear array transducer.

## Processing the Dataset

The acquisitions can be processed with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea).

`zea` streams the data from the Hugging Face Hub and processes it according to the pipeline. You can try it out with the following command:

```bash
zea process \
  --dataset hf://nvidia/Open-H-RF/waterloo-carotid/data/Acq1.hdf5 \
  --config hf://nvidia/Open-H-RF/waterloo-carotid/pipeline.yaml \
  --n-frames 1 \
  --save-as png
```

Alternatively, you can use the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/waterloo-carotid/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF).

Swap `--n-frames 1 --save-as png` for `--save-as gif` to get the cine loop. In the script, `ZEA_FILE`, `FRAME` and `POWER_THRESHOLD` (the power-Doppler mask threshold, in dB) at the top select what is reconstructed and overlaid.

## Dataset Format

[zea v0.1.4](https://github.com/tue-bmd/zea)

Submitted in the [`zea` file format](https://zea.readthedocs.io/en/latest/) (one HDF5 file per acquisition).

Per-sample contents of the converted HDF5:

| Group / field | Shape | Dtype | Units | Description |
|---|---|---|---|---|
| `metadata/credit` | `[]` | str | -- | Dataset attribution (LITMUS @ University of Waterloo) |
| `metadata/subject/id` | `[]` | str | -- | Participant ID (needed for subject-wise splits) |
| `metadata/subject/type` | `[]` | str | -- | Subject type (`human`) |
| `metadata/subject/age` | `[]` | uint8 | years | Subject age (`0` if not available) |
| `metadata/subject/sex` | `[]` | str | -- | Subject sex (`M` or `F`) |
| `metadata/annotations/anatomy` | `[]` | str | -- | Target artery (e.g., `Common Carotid Artery`, `Internal Carotid Artery`) |
| `metadata/annotations/view` | `[]` | str | -- | View orientation (`Longitudinal` or `Cross-sectional`) |
| `metadata/annotations/label` | `[]` | str | -- | Physiological condition (e.g., `Baseline`, `Valsalva Maneuver`) |
| `probe/name` | `[]` | str | -- | Probe identifier (`L14-5`) |
| `probe/type` | `[]` | str | -- | Probe structure type (`linear`) |
| `probe/probe_geometry` | `[128, 3]` | float32 | m | Transducer element Cartesian positions (x, y, z) |
| `data/raw_data` | `[n_frames, n_tx, n_ax, n_el, 1]` | float32 | -- | Raw RF channel data |
| `data/image` | `[n_frames, z, x]` (+ `coordinates` `[z, x, 3]`) | float32 | dB | Stored log-compressed B-mode intensity (relative to peak) |
| `data/vector_velocity_x` | `[n_frames, z, x]` (+ `coordinates` `[z, x, 3]`) | float32 | m/s | Lateral component of vector velocity ($v_x$) |
| `data/vector_velocity_z` | `[n_frames, z, x]` (+ `coordinates` `[z, x, 3]`) | float32 | m/s | Axial component of vector velocity ($v_z$) |
| `data/power_doppler` | `[n_frames, z, x]` (+ `coordinates` `[z, x, 3]`) | float32 | dB | Power Doppler intensity |
| `data/color_doppler` | `[n_frames, z, x]` (+ `coordinates` `[z, x, 3]`) | float32 | m/s | Color Doppler map |
| `scan/*` | -- | -- | -- | Probe geometry, sampling/center/demodulation frequency, t0 delays, sound speed, transmit angles, focus distances, transmit origins, apodizations, PRI... |

All `coordinates` arrays are per-pixel Cartesian positions in meters, last axis `[x, y, z]` (y = 0 for 2-D maps).

## Dataset Quantification

**Current Open-H-RF release:** 93 HDF5 files; 6.90 TB (6,902,089,770,179 bytes) stored; root `zea_version` **0.1.4**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

Data was collected from 8 participants, spanning carotid arteries (Common Carotid Artery and Internal Carotid Artery) in both longitudinal and cross-sectional views. In total, the dataset consists of 93 acquisitions, containing 30,000 or 36,000 frames of raw RF data per acquisition (47 acquisitions of 30,000 frames and 46 of 36,000 frames). 
Each common carotid artery frame comprises 2 steered plane-wave transmits (`n_tx = 2`), 2048 axial samples, and 128 receive channels. Each internal carotid artery frame comprises 1 steered plane-wave transmits (`n_tx = 1`), 1536 axial samples, and 128 receive channels.


## Subject Metadata

| Metric | Value |
| :--- | :--- |
| **Total Number of Subjects** | 8 |
| **Total Number of Files (Acquisitions)** | 93 |
| **Sex Composition** | M: 6 (75.0%), F: 2 (25.0%) |
| **Total RF Frames** | 3,066,000 |

## Known Issues

- Acquisitions made with US4R-lite include x2 receive multiplexing, so the full frame is constructed from two transmissions (receiving the first 64 channels first, then the second 64 channels).
- Participants may overlap with other UWaterloo submissions.
- Due to hardware, some acquisitions may have elevated Doppler noise on the right side of the image.
- Some acquisitions may have not hit the target view optimally, leading to poor flow detection.
- Due to the reduced PRF with the US4R-lite, some internal carotid artery acquisitions may contain sporadic/minor aliasing.

## Beamforming and Processing

1. **Pre-Filtering:** Channel RF data is pre-filtered using a 5 MHz bandpass filter before beamforming.
2. **GPU-Accelerated Beamforming (DAS):** Beamforming is carried out via a GPU-accelerated Delay-and-Sum (DAS) module.
   - **Aperture & Apodization:** 64-element Hanning window apodization and an F-number of 1.5.
   - **Dual Angle-Compounding:** Beamforming for B-mode and power Doppler is performed twice with opposite receive angles ($+15^{\circ}$ and $-15^{\circ}$). The final high-resolution beamformed image (HRI) is the average of these two acquisitions:
     $$HRI = \frac{HRI_{+15^{\circ}} + HRI_{-15^{\circ}}}{2}$$
   - **Reconstruction Grid:** Cartesian coordinates mapped by a `PixelMap` representing a lateral range of $[-19, 19]\text{ mm}$ and axial depth of $[0, 30]\text{ mm}$ at $0.1\text{ mm}$ spatial resolution.
3. **Clutter Filtering:** Clutter filtering is performed on the beamformed ensemble using a high-pass wall filter (normalized cut-off frequencies of 0.1 and 0.15, attenuation of 100 db).
4. **Multi-Angle Doppler Frequency Estimation:** Angle-specific Doppler frequencies are computed using an ensemble size of 64 frames with a step size of 1.
   - For acquisitions with 2 tx angles, we used the following Tx-Rx angles: Tx: [-10°, -10°, 10°, 10°]; Rx: [-10°, 10°, -10°, 10°]
   - For acquisitions with 1 tx angle: Tx: [-10°, -10°, -10°]; Rx: [-10°, 0°, 10°]
5. **Vector Doppler Velocity Estimation:** Lateral ($v_x$) and axial ($v_z$) velocity components are computed from the multi-angle Doppler frequency estimates using least-squares estimation.

The full LITMUS processing pipeline (GPU DAS beamforming + multi-angle vector Doppler) is documented by the contributors. That documentation is provided for provenance and reproducibility; it depends on the LITMUS core Python package and the raw acquisition frames, so it is not runnable from this folder alone.

Papers relevant to our pipeline:

Y. -H. Hsu (2025). High-frame-rate ultrasound characterization of carotid pulse waves to assess cerebrovascular resistance [Doctoral dissertation, University of Waterloo]. UWSpace. https://hdl.handle.net/10012/21738

H. Nahas, B. Y. S. Yiu, A. J. Y. Chee, T. Ishii and A. C. H. Yu, "Bedside Ultrasound Vector Doppler Imaging System With GPU Processing and Deep Learning," in IEEE Transactions on Ultrasonics, Ferroelectrics, and Frequency Control, vol. 72, no. 8, pp. 1079-1094, Aug. 2025, doi: 10.1109/TUFFC.2025.3582773

B. Y. S. Yiu and A. C. H. Yu, "Least-Squares Multi-Angle Doppler Estimators for Plane-Wave Vector Flow Imaging," in IEEE Transactions on Ultrasonics, Ferroelectrics, and Frequency Control, vol. 63, no. 11, pp. 1733-1744, Nov. 2016, doi: 10.1109/TUFFC.2016.2582514

## Data Validation

`reconstruct.py` builds a `zea.Pipeline` of DAS beamforming → envelope detection → normalization → log-compression **in code** and reconstructs a B-mode directly from `raw_data`, showing the raw-to-image flow without any config file. It also saves the pipeline to `pipeline.yaml` as a shareable recipe. Comparing the reconstruction against the stored (LITMUS) B-mode is a sanity check that the acquisition parameters and probe geometry are recorded correctly, and serves as a reproducible reference reconstruction.

When the vector-flow fields (`vector_velocity_x/z` + `power_doppler`) are present, a third panel overlays the vector velocity field on the stored B-mode. The overlay uses `draw_velocity_field`, a single self-contained (numpy + matplotlib) helper reproduced inside `reconstruct.py` from the LITMUS core Python package (`litmus.core_py.visualization`), so the script has no dependency on the full LITMUS GPU stack.

The result is written to `reconstruct_output.png`:

![reference reconstruction](assets/reconstruct_output.png)

## Ethical Considerations

All human studies were approved by the University of Waterloo’s Human Research Ethics Board (ORE #46278). All included data was acquired from participants who provided both written and verbal consent prior to participating in the study regarding public data sharing.

## Citation

```bibtex
@phdthesis{Hsu2025Carotid,
  title  = {High-frame-rate ultrasound characterization of carotid pulse waves to assess cerebrovascular resistance},
  author = {Hsu, Jason Y.-H.},
  school = {University of Waterloo},
  year   = {2025},
  note   = {UWSpace, https://hdl.handle.net/10012/21738},
}
```
