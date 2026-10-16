---
name: dartmouth-uct
pretty_name: "2D Ring-Array USCT Waveforms from 2D- and 3D-k-Wave Simulations"
license: cc-by-4.0
task_categories:
  - other
tags:
  - ultrasound
  - rf
  - open-h-rf
  - usct
  - sound-speed-estimation
  - attenuation
  - breast
  - simulation
language:
  - en
size_categories:
  - 1K<n<10K
---

# 2D Ring-Array USCT Waveforms from 2D- and 3D-k-Wave Simulations

![Ring-array USCT reflectivity reconstruction of a digital breast phantom, next to its ground-truth sound-speed and attenuation maps](assets/phantom_179604449_z200.png)

*A 2D-sim breast cross-section, [`data/2d/phantom_179604449_z200.hdf5`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/dartmouth-uct/data/2d/phantom_179604449_z200.hdf5), reconstructed as a reflectivity image beside the ground-truth sound-speed and attenuation maps stored in the file.*

## Dataset Description

This sub-dataset provides **pre-beamformed channel-domain radio-frequency ultrasound waveforms** from simulated ring-array **ultrasound computed tomography (USCT)** acquisitions of digital breast phantoms. All data are two-dimensional: each acquisition is a 2D channel tensor (transmit × time × receiver) recorded at a 256-element ring as every element fires in turn, paired with 2D voxel-level ground-truth maps of **speed-of-sound (SOS)** and **acoustic attenuation** for a single breast cross-section.

What distinguishes the two collections is **the k-Wave simulation used to generate the RF**:

- **2D-sim** (2,149 acquisitions): RF computed with **2D** k-Wave (`kspaceFirstOrder2D`) on the breast cross-section.
- **3D-sim** (476 acquisitions): RF computed with **3D** k-Wave (`kspaceFirstOrder3D`) on the full breast volume, then recorded at the ring plane. The 3D simulation captures out-of-plane propagation and finite focused-element behaviour that a 2D simulation cannot represent.

Both collections are generated from the **same underlying digital breast phantoms** (derived from the open VICTRE breast model), enabling direct study of how 3D acoustic effects change the channel data relative to an idealized 2D simulation. All data are **synthetic (simulated)**; no human or animal subjects are involved.

## Dataset Contributor(s)

- Yujia Wu <yujia.wu.th@dartmouth.edu> (primary point of contact)
- Geoffrey P. Luke <Geoffrey.P.Luke@dartmouth.edu> (PI)
- Thayer School of Engineering, Dartmouth College
- University of Rochester Medical Center

## Dataset Creation Date

07/04/2026

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

- **Sound-speed estimation / imaging** (quantitative SOS reconstruction).
- **Acoustic-attenuation imaging.**
- **Ultrasound computed tomography (USCT)** reconstruction from full-ring channel data.
- **Compressed sensing** — sub-sampling along the transmit (Tx) or receive (Rx) axis and recovering missing channels.

## Dataset Characterization

- **Data Collection Method:** synthetic (k-Wave simulation).
- **Labeling Method:** synthetic ground truth (voxel-level SOS and attenuation maps are the exact simulation inputs; no annotation error).
- **Acquisition system** (the label denotes the k-Wave simulation dimensionality; the recorded data are 2D in both cases):

**2D-sim** (RF from 2D k-Wave)

| Parameter | Value |
|---|---|
| Simulation | `kspaceFirstOrder2D` |
| Geometry | 256-element ring, point elements (no element directivity) |
| Ring radius | 60 mm |
| Grid spacing | 0.30 mm |
| Center frequency | 1.0 MHz (Gaussian pulse, 0.75 fractional bandwidth) |
| Sampling rate (saved) | 6.67 MHz (decimated 3× from 20 MHz native) |
| Transmit events (Tx) | 256 (every element fires in turn) |
| Receive elements (Rx) | 256 |
| Time samples (T) | 867 |
| Record length | 130 µs |

**3D-sim** (RF from 3D k-Wave)

| Parameter | Value |
|---|---|
| Simulation | `kspaceFirstOrder3D` |
| Geometry | 256-element ring, PURE-calibrated positions; focused elements (0.558 mm × 19 mm, 75 mm elevation focus) |
| Ring radius | 110.9 mm (PURE calibration) |
| Grid spacing | 0.29 mm |
| Center frequency | 1.5 MHz (5-cycle toneburst) |
| Sampling rate (saved) | 12 MHz |
| Transmit events (Tx) | 64 (every 4th element) |
| Receive elements (Rx) | 256 |
| Time samples (T) | 2161 |
| Record length | ~180 µs |

## Processing the Dataset

The acquisitions can be processed with the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/dartmouth-uct/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF), together with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea). The script streams the data from the Hugging Face Hub.

Set `ZEA_FILE` at the top of the script and run `python reconstruct.py`; the figure at the top of this card is its output. `SOS_MAP = True` swaps the constant-sound-speed delays for a straight-ray integral through the ground-truth map.

## Dataset Format

[zea v0.1.6](https://github.com/tue-bmd/zea)

All data are packaged in the **`zea` HDF5 file format** (one `.hdf5` file per acquisition), written entirely through `zea.File.create`. Each file stores the raw channel data under `tracks/track_0/data/raw_data`, the acquisition parameters under `tracks/track_0/scan`, the ring geometry under `probe` (in the **XZ imaging plane**, y = elevation), and the voxel-level ground truth as native zea map fields `tracks/track_0/data/sos_map` and `tracks/track_0/data/attenuation_map` (each with per-pixel `coordinates`). Tissue class is stored in `metadata/annotations` (`anatomy`, `label`); only fields with no standard spec home (z-plane indices, element focus) are zea `CustomElement`s under the top-level `custom/` group. Files are laid out by simulation type: `data/2d/` (2D-sim) and `data/3d/` (3D-sim).

**Pre-processing applied before packaging:**
- 2D-sim: temporal decimation by 3× (20 MHz → 6.67 MHz native simulation rate). 3D-sim: saved at the native 12 MHz, no decimation.
- Time-zero is carried in `scan/initial_times`; the per-sample time vector is `initial_times[tx] + n / sampling_frequency`. In **both** sets `t = 0` is the emission centroid: `initial_times = -2.15e-6` (2D-sim) and `-1.625e-6` (3D-sim, the 5-cycle toneburst centroid). The 3D simulation saved its time vector from the pulse onset, so this centroid offset is applied during conversion.
- Single-element transmit events are described by `scan/tx_apodizations` with zero `scan/t0_delays`. **2D-sim:** all 256 elements fire (identity matrix). **3D-sim:** 64 events fire every 4th element (a `(64, 256)` stride-4 matrix).
- Per-acquisition channel data stored as `float32` (zea's `raw_data` spec allows only `float32` or `int16`). The 2D-sim RF was decimated and intermediately cached at fp16 precision, so its stored `float32` is bit-faithful to that source rather than carrying extra precision; the 3D-sim RF is the native `float32` simulation output.
- No demodulation or beamforming is applied — data are raw RF channel signals.

## Dataset Quantification

**Current Open-H-RF release:** 2,625 HDF5 files; 257.62 GB (257,619,787,776 bytes) stored; root `zea_version` **0.1.6**. Sizes include all HDF5 contents and use decimal units (MB = 10^6 bytes, GB = 10^9 bytes, TB = 10^12 bytes), not decoded-array memory or original-source download sizes.

- **Number of acquisitions:** **2,149 (2D-sim)** (1,859 dense + 290 fatty) + **476 (3D-sim)** = **2,625 acquisitions**.
- **Single-Tx channel-capture frames:** 2,149 × 256 (2D-sim) + 476 × 64 (3D-sim) ≈ **5.8 × 10⁵ frames**.
- **Train / val / test split:** suggested 80 / 10 / 10 by **source phantom** (so slices/z-planes from one phantom never cross splits — prevents leakage).
- **Stored HDF5 size:** 257.62 GB total; 198.10 GB (2D-sim) + 59.52 GB (3D-sim).

**Per-sample feature table — 2D-sim** (HDF5 keys per `.hdf5` acquisition):

| Key | Shape | Dtype | Units | Description |
|---|---|---|---|---|
| `tracks/track_0/data/raw_data` | `(1, 256, 867, 256, 1)` | float32 | a.u. (pressure) | Raw channel data, axis order `(n_frames, n_tx, n_ax, n_el, n_ch)` |
| `tracks/track_0/scan/sampling_frequency` | scalar | float32 | Hz | 6.67e6 |
| `tracks/track_0/scan/center_frequency` | scalar | float32 | Hz | 1.0e6 |
| `tracks/track_0/scan/sound_speed` | scalar | float32 | m/s | Reference (water) sound speed, 1500 |
| `tracks/track_0/scan/initial_times` | `(256,)` | float32 | s | First-sample time per Tx (`-2.15e-6`; `t=0` at pulse centroid) |
| `tracks/track_0/scan/tx_apodizations` | `(256, 256)` | float32 | – | Identity: transmit event *i* fires element *i* |
| `tracks/track_0/scan/t0_delays` | `(256, 256)` | float32 | s | Transmit delays (zeros — single-element transmits) |
| `tracks/track_0/scan/transmit_origins` | `(256, 3)` | float32 | m | Firing-element position per Tx |
| `probe/probe_geometry` | `(256, 3)` | float32 | m | Ring element coordinates `(x, y=0, z)` in the XZ plane, 60 mm radius |
| `tracks/track_0/data/sos_map/values` | `(1, 230, 230)` | float32 | m/s | Ground-truth SOS map |
| `tracks/track_0/data/sos_map/coordinates` | `(230, 230, 3)` | float32 | m | Per-pixel `[x, y=0, z]` (dx = 0.30 mm, centred on ring; x=cols, z=rows) |
| `tracks/track_0/data/attenuation_map/values` | `(1, 230, 230)` | float32 | dB/m/Hz | Ground-truth attenuation coefficient α₀ |
| `tracks/track_0/data/attenuation_map/gamma` | scalar | float32 | – | Power-law exponent γ (1.01; α(f)=α₀·fᵞ) |
| `metadata/annotations` | – | str | – | `anatomy="breast"`, `label="dense"`/`"fatty"` |
| `custom/z_slice` | scalar | int | – | Phantom z-slice index |

Attenuation is stored in the zea base unit **dB/m/Hz** (`1 dB/cm/MHz = 1e-4 dB/m/Hz`); the `sos_map`/`attenuation_map` `coordinates` carry the physical grid (so `dx` is implicit), and `scan/sound_speed` holds the water reference.

**Per-sample feature table — 3D-sim** (HDF5 keys per `.hdf5` acquisition):

| Key | Shape | Dtype | Units | Description |
|---|---|---|---|---|
| `tracks/track_0/data/raw_data` | `(1, 64, 2161, 256, 1)` | float32 | a.u. (pressure) | Raw channel data, `(n_frames, n_tx, n_ax, n_el, n_ch)` |
| `tracks/track_0/scan/sampling_frequency` | scalar | float32 | Hz | 12e6 |
| `tracks/track_0/scan/center_frequency` | scalar | float32 | Hz | 1.5e6 |
| `tracks/track_0/scan/sound_speed` | scalar | float32 | m/s | Reference (water) sound speed, ≈1500 |
| `tracks/track_0/scan/initial_times` | `(64,)` | float32 | s | First-sample time per Tx (`-1.625e-6`; `t=0` at toneburst centroid) |
| `tracks/track_0/scan/tx_apodizations` | `(64, 256)` | float32 | – | Stride-4 selection: transmit event *k* fires element `4k` |
| `tracks/track_0/scan/t0_delays` | `(64, 256)` | float32 | s | Transmit delays (zeros — single-element transmits) |
| `tracks/track_0/scan/transmit_origins` | `(64, 3)` | float32 | m | Firing-element position per Tx |
| `probe/probe_geometry` | `(256, 3)` | float32 | m | PURE-calibrated ring positions `(x, y=0, z)` in the XZ plane, 110.9 mm radius |
| `probe/element_width`, `probe/element_height` | scalar | float32 | m | 0.558 mm × 19 mm focused element |
| `tracks/track_0/data/sos_map/values` | `(1, 800, 800)` | float32 | m/s | Ground-truth SOS slice (sim-grid in-plane cross-section at the ring) |
| `tracks/track_0/data/sos_map/coordinates` | `(800, 800, 3)` | float32 | m | Per-pixel `[x, y=0, z]` (dx = 0.29 mm, centred on ring; x=cols, z=rows) |
| `tracks/track_0/data/attenuation_map/values` | `(1, 800, 800)` | float32 | dB/m/Hz | Ground-truth attenuation coefficient α₀ |
| `tracks/track_0/data/attenuation_map/gamma` | scalar | float32 | – | Power-law exponent γ (1.01) |
| `metadata/annotations` | – | str | – | `anatomy="breast"` (no dense/fatty label for the 3D set) |
| `custom/z_off`, `custom/phantom_z_idx`, `custom/element_focus` | scalar | int / float | – / m | Ring z-offset, phantom z-slice index, element focus (0.075 m) |

Attenuation is in the zea base unit **dB/m/Hz**; the map `coordinates` carry the physical grid (XZ plane, y = 0).

## Subject Metadata

Not applicable — all data are synthetic. Aggregate phantom statistics:

- **Anatomical region:** breast cross-sections. The 3D-sim set samples several z-planes per phantom (one 2D cross-section each).
- **Tissue classes represented:** fat, glandular, skin/connective, with continuous SOS/attenuation/density assignments.
- **No PHI.**

## Data Validation

A single reference reconstruction, `reconstruct.py` (see *Processing the Dataset*), serves **both** sub-datasets. It builds a `zea.Pipeline` whose beamforming stage is zea's dedicated `zea.ops.USCTReflectivityDAS` — a round-trip time-of-flight Delay-And-Sum that, for every pixel, coherently sums over all transmit/receive pairs, rejects the direct through-transmission arrival, and apodizes to keep only backscatter geometries. The pipeline is saved to [`pipeline.yaml`](pipeline.yaml).

The same code reconstructs the 2D-sim (256 transmits) and 3D-sim (64 transmits) files because everything it needs is read **back from the zea file**: element positions (`probe/probe_geometry`), the transmit selection (`scan/tx_apodizations`), sampling rate (`scan/sampling_frequency`), time-zero (`scan/initial_times`), and the imaging grid (from the ground-truth `coordinates`). The ring is stored in the XZ imaging plane, so `zea.File.load_parameters` + `pipeline.prepare_parameters` drive the reconstruction directly. A resulting image whose bright skin boundary traces the ground-truth contour confirms the geometry, timing, and transmit parameters were recorded correctly.

## Known Issues

- **2D-sim vs 3D-sim differ in geometry and sampling** — 60 mm vs 110.9 mm ring; 256 vs 64 transmits; 867 @ 6.67 MHz (130 µs) vs 2161 @ 12 MHz (~180 µs); 230² (0.30 mm) vs 800² (0.29 mm) GT maps. Users combining both must resample to a common grid.
- **2D-sim point elements vs 3D-sim focused elements:** the 2D-sim set idealizes elements as points (no element directivity), while the 3D-sim set models finite focused elements (0.558 mm × 19 mm, 75 mm elevation focus) and out-of-plane propagation.
- **Attenuation units:** stored in the zea base unit `dB/m/Hz` (converted from the simulation's `dB/cm/MHz`; `1 dB/cm/MHz = 1e-4 dB/m/Hz`). The k-Wave `alpha_power` is the `attenuation_map/gamma` field (α(f)=α₀·fᵞ, γ=1.01).
- **Time-zero convention:** in both sets `t = 0` is the emission centroid (carried in `scan/initial_times`), not the first recorded sample — important for time-of-flight methods.

## Ethical Considerations

Fully synthetic dataset. No human or animal subjects; no consent, IRB, or de-identification requirements apply. The VICTRE breast phantoms are publicly released by the U.S. FDA/NCI. No usage caveats beyond the CC BY 4.0 attribution requirement.

---

### Provenance / Citation

If you use this sub-dataset, please cite:

- Badano A, Graff CG, Badal A, Sharma D, Zeng R, Samuelson FW, Glick SJ, Myers KJ. *Evaluation of Digital Breast Tomosynthesis as Replacement of Full-Field Digital Mammography Using an In Silico Imaging Trial.* JAMA Network Open. 2018;1(7):e185474. doi:10.1001/jamanetworkopen.2018.5474
- Treeby BE, Cox BT. *k-Wave: MATLAB toolbox for the simulation and reconstruction of photoacoustic wave fields.* J Biomed Opt. 2010;15(2):021314.
