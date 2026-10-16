---
name: unc-openpros
pretty_name: "OpenPros Limited-View Prostate USCT"
license: cc-by-4.0
task_categories:
  - image-to-image
tags:
  - ultrasound
  - rf
  - open-h-rf
  - prostate
  - usct
  - speed-of-sound
  - full-waveform-inversion
  - simulation
language:
  - en
size_categories:
  - 100K<n<1M
---

# OpenPros - Limited-View Prostate Ultrasound Computed Tomography

<img width="100%" align="center" src="assets/comparison.png" 
  alt="Comparison of the ground truth speed-of-sound map of a prostate slice (left) and the prediction by InversionNet (right)"/>

<!-- ![Speed-of-sound map of a prostate slice, predicted by InversionNet](assets/main.png) -->

*Speed of sound predicted from the limited-view waveform data of the first acquisition in [`data/3_01_P_prostate_00.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/unc-openpros/data/3_01_P_prostate_00.hdf5) with the pretrained OpenPros InversionNet.*

## Dataset Description

[OpenPros](https://open-pros.github.io/) is a large-scale benchmark for limited-view prostate ultrasound computed tomography (USCT). Each example pairs simulated full-waveform RF data from transabdominal and transrectal acquisition paths with an anatomically realistic two-dimensional speed-of-sound (SOS) map. The source OpenPros phantoms are derived from expert-annotated clinical MRI/CT anatomy and experimental measurements of ex vivo prostate specimens; the RF measurements in this package are simulated rather than acquired in vivo. The intended research task is quantitative SOS reconstruction from limited-angle ultrasound data.

## Dataset Contributor(s)

OpenPros was created by:

- Hanchen Wang
- Yixuan Wu
- Yinan Feng
- Peng Jin
- Luoyuan Zhang
- Shihang Feng
- James Wiskin
- Baris Turkbey
- Peter A. Pinto
- Bradford J. Wood
- Songting Luo
- Yinpeng Chen
- Emad Boctor
- Youzuo Lin <yzlin@unc.edu> (corresponding author)

The affiliations include the University of North Carolina at Chapel Hill, Johns Hopkins University, the National Institutes of Health, the Pennsylvania State University, QT Imaging, Iowa State University, and Google DeepMind. Source repository: <https://github.com/hanchenwang/OpenPros>; dataset website: <https://open-pros.github.io/>.

## Dataset Creation Date

05/18/2025 (initial public release of OpenPros).

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data. 

The original license was [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/). The conversion of the license is under agreement of all the contributors.

## Intended Usage

- Training and evaluating limited-angle prostate USCT reconstruction methods.
- Reconstructing quantitative two-dimensional SOS maps from full-waveform data.
- Benchmarking learned, physics-guided, and operator-learning inverse methods.
- Studying robustness to noise and generalization across prostate specimens or patient-level anatomies.
- Reproducing inference with the pretrained OpenPros InversionNet baseline.

## Dataset Characterization

- **Data collection method:** Synthetic FDTD wave-propagation simulations through anatomically realistic digital prostate phantoms.
- **Ground-truth method:** SOS maps derived from expert-annotated MRI/CT anatomy, measured ex vivo prostate SOS values, and literature tissue properties.
- **Anatomy:** Prostate and surrounding male pelvic anatomy, including tissue heterogeneity and, depending on the slice, bony structures and lesions.
- **Acquisition geometry:** Limited-view configuration with 10 sources and 161 receivers on the abdominal/body-surface side and another 10 sources and 161 receivers on the transrectal side.
- **Excitation:** 1 MHz peak-frequency Ricker wavelet.
- **Sampling:** 10 MHz (`dt = 1e-7 s`), 1,000 samples, or 100 microseconds per waveform.
- **Image grid:** 401 axial by 161 lateral samples at 0.375 mm spacing, covering approximately 150 mm by 60 mm.

## Processing the Dataset

The acquisitions can be processed with the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/unc-openpros/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF), together with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea). The script streams the data from the Hugging Face Hub.

The reconstruction script checks the input shapes and writes two files: `pred_sos.png`, a side-by-side comparison of the predicted and ground-truth SOS maps, and [`assets/main.png`](assets/main.png), a clean, unlabeled hero image of just the prediction.

The custom pipeline operations live in `custom_ops.py` (layout and preprocessing) and `network_ops.py` (runs the pretrained InversionNet from `zea.models.inversionnet`, weights downloaded from the Hugging Face Hub) next to the script.

## Dataset Format

[zea v0.1.5](https://github.com/tue-bmd/zea)

The package uses the `zea` HDF5 format. The RF values are carried over from the original OpenPros NumPy arrays without demodulation, decimation, filtering, or normalization. The conversion adds a singleton channel dimension and changes the original four 10-transmit blocks into a physical `20 transmits × 322 receivers` representation:

| HDF5 region | Source side | Receiver side | Original transmit channels |
|---|---|---|---|
| `raw_data[:, 0:10, :, 0:161, :]` | Body surface | Body surface | `0:10` |
| `raw_data[:, 0:10, :, 161:322, :]` | Body surface | Rectum | `10:20` |
| `raw_data[:, 10:20, :, 161:322, :]` | Rectum | Rectum | `20:30` |
| `raw_data[:, 10:20, :, 0:161, :]` | Rectum | Body surface | `30:40` |

The file also stores source positions, probe geometry, scan parameters, subject identifiers, SOS values, and Cartesian SOS coordinates. Placeholder scan fields needed for format compatibility are described under **Known Issues**.

## Dataset Quantification

**Current Open-H-RF release:** 248 HDF5 files; 6.03 TB (6,031,699,279,872 bytes) stored; root `zea_version` **0.1.5**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

The original OpenPros source documentation reports 280,000 paired samples (approximately 6.8 TB) with an official split of 224,000 training, 28,000 validation, and 28,000 test samples. It is derived from four patient-level clinical anatomies and 62 ex vivo prostate specimens. Each published HDF5 file here holds 1,140 acquisitions.

| Field | Shape per file | dtype | Units | Description |
|---|---|---|---|---|
| `raw_data` | `(1140, 20, 1000, 322, 1)` | float32 | — | Simulated full-waveform pressure/RF data |
| `sos_map.values` | `(1140, 401, 161, 1)` | float32 | m/s | Ground-truth speed-of-sound map |
| `sos_map.coordinates` | `(401, 161, 3)` | float32 | m | Cartesian `(x, y, z)` grid coordinates |

## Subject Metadata

The converted release identifies its content as a simulation and stores composite subject IDs such as `1_prostate_00`, combining patient-level anatomy `3_01` with prostate-level index `prostate_00`. The release uses four patient-level anatomy IDs (`3_01` through `3_04`) and 62 prostate indices shared across acquisition positions.

## Data Validation

`reconstruct.py` loads [`pipeline.yaml`](pipeline.yaml) (also published on the Hub at [`hf://nvidia/Open-H-RF/unc-openpros/pipeline.yaml`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/unc-openpros/pipeline.yaml)), a `zea.Pipeline` that reproduces the OpenPros InversionNet preprocessing and postprocessing:

1. Restore the original acquisition-block order: body/body, body/rectum, rectum/rectum, and rectum/body.
2. Apply the sign-preserving logarithmic transform `sign(x) * log1p(abs(1e5 * x))`.
3. Min-max normalize the configured transformed input range to `[-1, 1]`.
4. Run the pretrained InversionNet model.
5. Denormalize its output from `[-1, 1]` to the physical SOS range `1300–3600 m/s`.

## Known Issues

- `focus_distances`, `t0_delays`, `tx_apodizations`, and related transmit fields are compatibility placeholders because the simulation uses external point sources rather than a conventional focused array transmission.

## Ethical Considerations

The packaged RF data and SOS labels are simulated and contain no directly identifying patient information.

## Citation

```bibtex
@inproceedings{wang2026openpros,
  title={Openpros: A large-scale dataset for limited view prostate ultrasound computed tomography},
  author={Wang, Hanchen and Wu, Yixuan and Feng, Yinan and Jin, Peng and Zhang, Luoyuan and Feng, Shihang and Wiskin, James and Turkbey, Baris and Pinto, Peter and Wood, Bradford and others},
  booktitle={International Conference on Learning Representations},
  volume={2026},
  pages={113741--113759},
  year={2026}
}
```