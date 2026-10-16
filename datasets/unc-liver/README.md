---
name: unc-liver
pretty_name: "fullwave-abdominal-wall: Fullwave Abdominal Wall Simulation (UNC / NC State / Stanford)"
license: cc-by-4.0
task_categories:
  - image-segmentation
tags:
  - ultrasound
  - rf
  - open-h-rf
  - synthetic-aperture
  - curvilinear
  - sound-speed-estimation
  - aberration-correction
  - simulation
language:
  - en
size_categories:
  - 1K<n<10K
---

# fullwave-abdominal-wall: Fullwave Abdominal Wall Simulation Dataset

<p align="center">
  <img src="assets/main.png" alt="Scan-converted B-mode through a simulated abdominal wall" width="480">
</p>

*Scan-converted B-mode reconstructed from the full-synthetic-aperture channel data of one simulated acquisition in [`data/`](https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/unc-liver/data): the abdominal wall layers in the near field above the liver.*

## Dataset Description

Full-wave nonlinear acoustic simulations of transabdominal liver imaging through anatomically realistic numerical phantoms of the human abdominal wall. Each acquisition pairs **full synthetic aperture (multistatic) RF channel data** with the **exact ground-truth material maps that generated it**: speed of sound, density, absorption and the coefficient of nonlinearity, plus a per-pixel tissue segmentation.

The phantoms were segmented from Visible Human Project cryosection photography at 0.33 mm isotropic resolution and interpolated to 0.0825 mm. Wave propagation was simulated with Fullwave 2, which models reverberation, aberration and nonlinear propagation. The transducer modelled is a curvilinear C5-2v (Verasonics).

This is **simulated** data. Its distinguishing property is that the ground truth is exact rather than estimated: the sound-speed and attenuation maps are the simulation inputs, not a reconstruction, which makes it directly usable for training and quantitative evaluation of sound-speed estimation and aberration-correction methods.

## Dataset Contributor(s)

- Gianmarco Pinton <gia@email.unc.edu> (primary point of contact; Lampe Joint Department of Biomedical Engineering, UNC Chapel Hill and NC State University)
- University of North Carolina at Chapel Hill
- NC State University
- Stanford University

The underlying phantoms and simulations are described in Zhuang et al. (2026).

## Dataset Creation Date

03/19/2024.

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

- **Speed-of-sound estimation:** exact per-pixel ground-truth sound speed, randomised per tissue per simulation so the mapping is not memorisable from anatomy alone.
- **Aberration correction:** measured RMS arrival-time aberration is 138.9 ± 78.4 ns across the dataset.
- **Reverberation / clutter suppression:** the abdominal wall produces realistic diffuse reverberation (decay in the expected −12 to −10 dB/cm range).
- **Advanced beamforming:** the multistatic full synthetic aperture matrix supports retrospective synthesis of any transmit sequence (focused, plane wave, diverging).
- **Tissue segmentation** from channel data.

## Dataset Characterization

- **Data Collection Method:** synthetic (Fullwave 2 numerical simulation)
- **Labeling Method:** synthetic ground truth (simulation inputs)
- **Acquisition system:** simulated Verasonics **C5-2v curvilinear array**: 128 elements, 49.57 mm radius of curvature, 0.508 mm arc pitch, 3.7 MHz transmit centre frequency, 70% fractional bandwidth, 14.436 MHz sampling. Transmit pulse is a two-cycle Gaussian-enveloped sine at 0.1 MPa. No lens or matching layer is modelled.

## Source Attribution

The material distributed here (the RF channel data, the acoustic material maps, and the segmentations) is original scholarly output of the contributing institutions (simulations and phantom construction by the UNC / Stanford team) and is released under CC BY 4.0.

The phantoms derive from the **Visible Human Project** (VHP) cryosection imagery of the U.S. National Library of Medicine. As of July 2019 the NLM Data License was replaced by open Terms and Conditions (<https://www.nlm.nih.gov/databases/download/terms_and_conditions.html>): no license agreement or registration is required, there is no restriction on commercial use, no royalties, and no share-alike or redistribution restriction, so nothing in the VHP terms conflicts with CC BY 4.0. NLM works are U.S. Government works and carry no copyright in the United States.

The one obligation carried over from the VHP terms is acknowledgement:

> **Courtesy of the U.S. National Library of Medicine.**

The NLM does not endorse this dataset, and nothing here should be read as implying such endorsement.

*This is a good-faith reading of the public terms, not legal advice; the contributor is the responsible party for the license declaration.*

## Processing the Dataset

The acquisitions can be processed with the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/unc-liver/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF), together with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea). The script streams the data from the Hugging Face Hub.

Set `ZEA_FILE` and `FRAME` at the top of the script to pick an acquisition. For current release files, use `zea==0.1.6` and any Keras backend (`reconstruct.py` falls back to torch if `KERAS_BACKEND` is unset, but respects whatever you have configured).

## Dataset Format

[zea v0.1.4](https://github.com/tue-bmd/zea)

All files are in the *zea* file format (current release `zea_version` 0.1.4), one HDF5 file per acquisition, single track.

**Pre-processing applied before packaging:** none to the channel data. It is the native simulator output at full rate. The simulation ran at 101.1 MHz and was decimated by 7 to the stored 14.436 MHz *by the simulator*, before this packaging.

Coordinate frame: `x` is lateral, `y ≡ 0` (the simulations are 2-D), `z` is depth. The **array apex is at z = 0** and the centre of curvature at `z = −49.57 mm`, matching zea's `polar_pixel_grid` convention. `probe_geometry`, `transmit_origins` and every map `coordinates` array share this frame, so the channel data and the maps are exactly registered.

Transmit sequence: **full synthetic aperture**: each element fires alone and all 128 elements receive. Hence `t0_delays` is all-zero, `tx_apodizations` is the identity, and `focus_distances` is zero. `initial_times` is **negative** (−79.17 ns): the simulator's transmit start time offset means sample 0 corresponds to a two-way time of flight of −t0.

Transmit and receive element positions differ slightly. `probe_geometry` holds the **receive** element positions and `scan/transmit_origins` the **transmit** element positions; the Fullwave simulation discretizes the transmit and receive apertures onto separate arcs of its grid that sit about 0.16 mm (≈ 0.4 wavelengths) apart. This is a property of the source simulation, not an error. When beamforming, use `transmit_origins` for the transmit leg and `probe_geometry` for the receive leg, as the shipped reference reconstruction does.

### Per-sample feature table

| Field | Shape | dtype | Unit | Description |
|---|---|---|---|---|
| `data/raw_data` | (1, 128, 1811, 128, 1) | float32 | – | Multistatic RF channel data, (frames, tx, samples, rx, ch) |
| `data/sos_map/values` | (1, 640, 128) | float32 | m/s | Ground-truth speed of sound |
| `data/attenuation_map/values` | (1, 640, 128) | float32 | dB/m/Hz | Ground-truth absorption (native dB/cm/MHz × 1e-4, power law exponent 1) |
| `data/density_map/values` | (1, 640, 128) | float32 | kg/m³ | Ground-truth mass density |
| `data/nonlinearity_map/values` | (1, 640, 128) | float32 | – | Coefficient of nonlinearity β = 1 + (B/A)/2 |
| `data/segmentation/values` | (1, 640, 128, 9) | bool | – | Per-pixel tissue class, one channel per label |
| `data/segmentation/labels` | (9,) | str | – | fat, liver, muscle, water_or_blood, skin, generic_soft_tissue, connective, epidermis, papillary_dermis |
| `data/phantom_region_map/values` | (1, 640, 128) | float32 | – | Original phantom region index (see Known Issues) |
| `data/beamformed_data/values` | (1, 640, 128, 2) | float32 | – | Reference DAS reconstruction, I/Q |
| `data/*/coordinates` | (640, 128, 3) | float32 | m | Per-pixel Cartesian (x, y, z) |
| `scan/sampling_frequency` | () | float32 | Hz | 14 435 695.54 |
| `scan/center_frequency` | () | float32 | Hz | 3 700 000 |
| `scan/demodulation_frequency` | () | float32 | Hz | 3 700 000 (RF) |
| `scan/sound_speed` | () | float32 | m/s | 1540 (reference for the shipped DAS) |
| `scan/initial_times` | (128,) | float32 | s | −7.9169e-08 |
| `scan/t0_delays` | (128, 128) | float32 | s | all zero (full synthetic aperture) |
| `scan/tx_apodizations` | (128, 128) | float32 | – | identity |
| `scan/focus_distances` | (128,) | float32 | m | all zero |
| `scan/transmit_origins` | (128, 3) | float32 | m | Transmitting element position |
| `scan/polar_angles` | (128,) | float32 | rad | Element normal angle, ±0.6507 |
| `probe/probe_geometry` | (128, 3) | float32 | m | Receive element positions on the arc |

All maps are on the polar reconstruction grid: 640 radial samples spanning 5.0–71.5 mm from the array surface, by 128 beams spanning ±0.3 rad.

## Dataset Quantification

**Current Open-H-RF release:** 1,906 HDF5 files; 202.69 GB (202,692,755,456 bytes) stored; root `zea_version` **0.1.4**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- **1906 acquisitions**, 1 frame each, 128 transmits × 128 receives per acquisition.
- **Stored HDF5 size:** 202.69 GB (202,692,755,456 bytes).
- Drawn from **14 distinct phantom volumes** derived from a single Visible Human subject: `vishuman_abdominal_cropped` (308), `vishuman_abdwall_153_h` (187), `vishuman_abdwall_cropped_7-153s` (148), `vishuman_abdwall_cropped_5left153s` (134), `vishuman_abdwall_cropped_7left153s` (133), `vishuman_abdwall_set_04` (123), `vishuman_abdwall_cropped_6left153s` (119), `vishuman_abdwall_set_13` (114), `vishuman_abdwall_set_05` (113), `vishuman_abdwall_set_12` (109), `vishuman_abdwall_set_07` (109), `vishuman_abdwall_set_10` (108), `vishuman_abdwall_set_06` (104), `vishuman_abdwall_set_11` (97).

### Splits

[`assets/dataset_split.csv`](assets/dataset_split.csv) assigns every acquisition to the splits below, one row per HDF5 file (`hdf5_filename`, `volume`, and a `<split>_train` / `<split>_valid` flag pair per split). Splits are **grouped by phantom volume** so that no volume appears in both train and validation. This avoids anatomical leakage, which matters because many acquisitions are different 2-D slices of the same volume.

| Split | Train | Validation |
|---|---|---|
| `half_half_1` | 1143 | 763 |
| `half_half_2` | 1071 | 835 |
| `fold1` | 1251 | 558 |
| `fold2` | 1257 | 540 |
| `fold3` | 1314 | 488 |
| `fold4` | 1328 | 465 |

Note the `fold*` splits are **not** complementary: between 97 and 113 acquisitions are in neither the train nor the validation set of a given fold.

## Subject Metadata

Aggregate only; no PHI. All phantoms derive from **one** Visible Human Project cadaveric subject (female), so the dataset represents a single anatomy sampled at many slice positions and orientations, with randomised abdominal wall thickness (5–71 mm, mean 41.0 mm, SD 8.9 mm) and randomised per-tissue acoustic properties.

Tissue composition varies by volume type; across the phantom volumes reported in the source publication, subcutaneous fat and muscle predominate (fat 56.5 ± 8.3%, muscle 22.2 ± 7.7%, connective 20.7 ± 4.2%, blood 0.6 ± 0.5% for wall-dominated volumes).

## Data Validation

`reconstruct.py` builds a `zea.Pipeline` (`Cast → Demodulate → Beamform(delay_and_sum) → EnvelopeDetect → Normalize → LogCompress`), reconstructs from the raw channel data on the polar grid, scan-converts to a physical sector and writes a PNG. The pipeline plus its grid parameters are saved in `pipeline.yaml`.

Reference outputs: `bmode_reference.png`.

**Geometry validation.** The zea reconstruction was checked against the reference delay-and-sum image shipped with the source dataset: radial registration lag **0 samples**, lateral lag **0 beams**, structural correlation 0.92–0.95 (8×8 and 16×16 smoothed). Residual speckle-level decorrelation is expected: the reference used a Hilbert analytic signal with bicubic interpolation, while the zea pipeline demodulates to baseband with its own interpolation and apodization.

## Known Issues

- **`fs / f0` = 14.436 / 3.7 = 3.90**, marginally below the ×4 heuristic often applied to RF. This is the simulator's native rate (101.1 MHz decimated by 7) and still satisfies Nyquist for the −6 dB bandwidth of a 70%-fractional-bandwidth 3.7 MHz pulse (band edge ≈ 5.0 MHz, Nyquist 7.2 MHz). No aliasing is present.
- **`segmentation` is derived, not stored.** The simulator's own integer segmentation is a *per-volume region index* whose index-to-tissue mapping differs between phantom volumes, so those indices are not comparable across acquisitions. It is preserved verbatim as `phantom_region_map` for provenance. The shipped `segmentation` is recovered per pixel from the exact (density, β, absorption) fingerprint of each tissue in the simulator's material table. These three properties are constants, whereas sound speed is randomly drawn per tissue per simulation and is therefore excluded from the classification. Pixels on tissue boundaries are softened by the simulator's Gaussian blur (σ = 1 pixel) and are assigned to the nearest pure tissue.
- **2-D simulations.** Elevational focusing and out-of-plane scattering are not modelled. The source publication argues this is acceptable for subcostal transabdominal scanning, where ribs do not obstruct the field.
- **Single subject.** All anatomy derives from one Visible Human cadaver, so anatomical variability is limited to slice position, orientation, wall-thickness scaling and randomised acoustic properties. Simulations overlap spatially due to random sampling within volumes; the `volume` column allows filtering for overlap.
- **Postmortem blood redistribution** in the supine source cadaver produces additional contrast of connective tissue in the posterior portions of the images and limits connective tissue visibility anteriorly.

## Ethical Considerations

The data is entirely synthetic. It contains no patient data, no PHI and no identifiable information. The underlying anatomy derives from the **Visible Human Project**, a publicly released cadaveric imaging dataset collected with documented donor consent by the U.S. National Library of Medicine; no living subjects are involved and no IRB approval is applicable to the simulation work. The VHP source imagery is provided under open NLM Terms and Conditions and is acknowledged as required (see License / Terms of Use). No patient consent or de-identification concerns arise because no patient data is present at any stage.

## Citation

> L. Zhuang, O. Ostras, M. Sode, W. Simson, D. Hyun, F. Santibanez, J. Dahl and G. Pinton, "Labeled Numerical Phantom of Abdominal Wall for Wave-Physics-Based Ultrasound Imaging: Applications to Image Reconstruction," *IEEE Transactions on Ultrasonics, Ferroelectrics, and Frequency Control*, vol. 73, no. 1, pp. 24–34, Jan. 2026. doi:10.1109/TUSON.2025.3638314

Related resources:

- Segmented phantom volumes and source RF: <https://cdr.lib.unc.edu/concern/data_sets/wh247369f>
- Fullwave 2 simulation code and examples: <https://github.com/pinton-lab/abdominal_phantom_applications>
