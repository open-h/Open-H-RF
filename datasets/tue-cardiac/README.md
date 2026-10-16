---
name: tue-cardiac
pretty_name: "TU/e Cardiac RF Multi-Transmit"
license: cc-by-4.0
task_categories:
  - other
tags:
  - ultrasound
  - rf
  - open-h-rf
  - echocardiography
  - cardiac
  - plax
  - beamforming
  - harmonic-imaging
  - plane-wave-imaging
  - synthetic-aperture
  - refocus
language:
  - en
size_categories:
  - n<1K
---

# TU/e Cardiac PLAX Multi-Transmit RF

<table width="100%">
  <tr>
    <td width="25%"><img src="assets/subject2_focused_harm_nb80.gif" alt="" width="100%"></td>
    <td width="25%"><img src="assets/subject4_wide_harm_nb80.gif" alt="" width="100%"></td>
    <td width="25%"><img src="assets/subject6_focused_harm_nb80.gif" alt="" width="100%"></td>
    <td width="25%"><img src="assets/subject9_wide_harm_nb80.gif" alt="" width="100%"></td>
  </tr>
</table>

*Parasternal long-axis cine loops of four volunteers, pulse-inversion harmonic tracks: focused ([`subject-002`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/tue-cardiac/data/subject-002.hdf5)), wide ([`subject-004`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/tue-cardiac/data/subject-004.hdf5)), focused ([`subject-006`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/tue-cardiac/data/subject-006.hdf5)) and wide ([`subject-009`](https://huggingface.co/datasets/nvidia/Open-H-RF/blob/main/tue-cardiac/data/subject-009.hdf5)).*

## Dataset Description

This dataset contains pre-beamformed radio-frequency (RF) channel data from in-vivo human cardiac ultrasound acquisitions of 12 distinct adult healthy volunteers, aged 26–33 years. The operator attempted a parasternal long-axis (PLAX) view for every participant. Each participant file contains eight separately acquired 100-frame tracks (3s,33Hz) that vary the transmit encoding: focused fundamental, focused pulse-inversion harmonic, wide fundamental, wide pulse-inversion harmonic, plane wave, diverging wave, Hadamard-coded aperture, and random binary-coded aperture.

The data were acquired on a Verasonics Vantage 256 research platform with a Philips S5-1 phased-array probe. The contribution is intended to support generalized reconstruction, transmit-encoding research, REFoCUS recovery, compressed sensing, and comparisons of fundamental and second-harmonic imaging.

## Dataset Contributor(s)

- Simon Penninga <s.w.penninga@tue.nl> (author; contact)
- Ruud van Sloun (author)
- Biomedical Diagnostics Lab, Eindhoven University of Technology (TU/e), the Netherlands

## Dataset Creation Date

The recordings were acquired in 2026.

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

Intended research uses include:

- raw-channel-to-B-mode reconstruction and beamforming;
- REFoCUS recovery of synthetic-transmit-aperture data;
- sparse or compressed transmit-sequence reconstruction;
- comparison of focused, wide, plane-wave, diverging, and coded transmissions;
- comparison of fundamental and pulse-inversion harmonic acquisitions; and
- development and evaluation of ultrasound inverse-problem methods.

The dataset must not be used as a clinically validated diagnostic product.

## Dataset Characterization

- **Data collection method:** in-vivo human cardiac ultrasound on a research platform.
- **Anatomy and view:** heart; attempted parasternal long-axis (PLAX) view.
- **Cohort:** 12 adult healthy volunteers, aged 26–33 years, recruited from among researcher colleagues. No known pathologies were reported.
- **Acquisition protocol:** the eight modes were acquired sequentially in the fixed order shown below. The probe was kept as steady as possible. Before each recording, the volunteer was instructed to breathe out.
- **Operator:** No ultrasound training or prior experience.
- **Acquisition system:** Verasonics Vantage 256 with a Philips S5-1 phased-array probe.
- **Probe:** phased-array, 80 active elements, nominal probe center frequency 3.125 MHz, and 128% fractional bandwidth.
- **Receive sampling:** 15.625 MHz; 2,304 axial samples; raw `int16` RF with one real channel. For pulse inversion imaging, the two acquisitions are summed in buffer.
- **Nominal sound speed:** 1,540 m/s.
- **Frame rate:** approximately 33 frames/s for each track.
- **Coordinate convention:** x = lateral, y = elevation, z = axial/depth.

| Order | Track label | Transmit family | Stored transmits/frame | Transmit center frequency | Notes |
|---:|---|---|---:|---:|---|
| 01 | `focused_fund` | Focused, ±45° | 80 | 3.90625 MHz | 60 mm transmit focus |
| 02 | `focused_harm` | Focused, ±45° | 80 | 1.953125 MHz | 160 receive events are pulse-inversion accumulated to 80 stored transmits; 3.90625 MHz demodulation |
| 03 | `wide_fund` | Wide focused, ±45° | 80 | 3.90625 MHz | 150 mm transmit focus |
| 04 | `wide_harm` | Wide focused, ±45° | 80 | 1.953125 MHz | 160 receive events are pulse-inversion accumulated to 80 stored transmits; 3.90625 MHz demodulation |
| 05 | `planewave` | Steered plane wave, ±45° | 80 | 3.90625 MHz | Infinite transmit focus |
| 06 | `diverging` | Diverging wave, ±45° | 80 | 3.90625 MHz | Negative virtual-focus distance varies with steering angle |
| 07 | `hadamard` | Full-aperture Hadamard code | 80 | 3.90625 MHz | Zero transmit delays and ±1 apodization; REFoCUS decoding required |
| 08 | `random` | Full-aperture fixed random binary code | 80 | 3.90625 MHz | Zero transmit delays and ±1 apodization; REFoCUS decoding required |

## Processing the Dataset

The acquisitions can be processed with the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/tue-cardiac/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF), together with the `pipelines/*.yaml` definitions in this folder and the [zea library](https://github.com/tue-bmd/zea). The script streams the data from the Hugging Face Hub.

Each file holds the eight transmit-encoding tracks. Set `ZEA_FILE`, `TRACK` and `FRAME` at the top of the script, together with the matching pipeline under `pipelines/` as `CONFIG` (`PIPELINE_FOR_TRACK` lists which track uses which; see also [Data Validation](#data-validation)). The image is written to `assets/`.

## Dataset Format

[zea v0.1.4](https://github.com/tue-bmd/zea)

The final dataset contains 12 zea HDF5 files under `data/`, one per pseudonymized participant:

```text
data/
  subject-001.hdf5
  ...
  subject-012.hdf5
```

Each file has one shared `/probe` group, one de-identified `/metadata` group, and eight entries under `/tracks`. Track labels identify the transmit encoding. Raw channel data for each track are stored at:

The source tensor order is preserved as `(n_frames, n_tx, n_ax, n_el, n_ch) = (100, 80, 2304, 80, 1)` with dtype `int16`. Values are uncalibrated Verasonics receive samples.

### Core per-file feature table

| Field | Shape | dtype | Units | Description |
|---|---|---|---|---|
| `/metadata/subject/id` | scalar | string | — | Sequential public pseudonym `subject-NNN`, not derived from a direct identifier |
| `/metadata/subject/type` | scalar | string | — | `human` |
| `/metadata/annotations/anatomy` | scalar | string | — | `heart` |
| `/metadata/annotations/view` | scalar | string | — | `parasternal_long_axis_attempt` |
| `/metadata/annotations/label` | scalar | string | — | `healthy_volunteer`; cohort classification, not a diagnosis |
| `/probe/type` | scalar | string | — | `phased` |
| `/probe/probe_geometry` | `(80, 3)` | float32 | m | Element positions in `(x, y, z)` order |
| `/probe/element_width` | scalar | float32 | m | Element width |
| `/probe/probe_center_frequency` | scalar | float32 | Hz | Nominal probe center frequency |
| `/tracks/track_N/data/raw_data` | `(100, 80, 2304, 80, 1)` | int16 | a.u. | Pre-beamformed RF channel data |
| `/tracks/track_N/scan/sampling_frequency` | scalar | float32 | Hz | RF sampling frequency |
| `/tracks/track_N/scan/center_frequency` | scalar | float32 | Hz | Transmit center frequency |
| `/tracks/track_N/scan/demodulation_frequency` | scalar | float32 | Hz | Receive demodulation frequency used by the reconstruction pipeline |
| `/tracks/track_N/scan/sound_speed` | scalar | float32 | m/s | Assumed propagation speed |
| `/tracks/track_N/scan/t0_delays` | `(80, 80)` | float32 | s | Per-transmit, per-element delays |
| `/tracks/track_N/scan/tx_apodizations` | `(80, 80)` | float32 | — | Per-transmit, per-element weights |
| `/tracks/track_N/scan/initial_times` | `(80,)` | float32 | s | Receive start time per stored transmit |
| `/tracks/track_N/scan/time_to_next_transmit` | usually `(100, 80)` | float32 | s | Relative transmit/frame timing when recoverable from the acquisition |
| `/tracks/track_N/scan/tgc_gain_curve` | `(2304,)` | float32 | — | Recorded time-gain-compensation curve |
| `/tracks/track_N/scan/waveforms_one_way` | track dependent | float32 | V | One-way transmit waveform model |
| `/tracks/track_N/scan/waveforms_two_way` | track dependent | float32 | V | Two-way transmit waveform model |

## Transmit Types

<table width="100%">
  <tr>
    <th>Focused fundamental</th>
    <th>Focused pulse-inversion harmonic</th>
    <th>Wide fundamental</th>
    <th>Wide pulse-inversion harmonic</th>
  </tr>
  <tr>
    <td><img src="assets/subject-002_focused_fund_frame-000.png" alt="Focused fundamental cardiac image"></td>
    <td><img src="assets/subject-002_focused_harm_frame-000.png" alt="Focused pulse-inversion harmonic cardiac image"></td>
    <td><img src="assets/subject-002_wide_fund_frame-000.png" alt="Wide fundamental cardiac image"></td>
    <td><img src="assets/subject-002_wide_harm_frame-000.png" alt="Wide pulse-inversion harmonic cardiac image"></td>
  </tr>
  <tr>
    <th>Plane wave</th>
    <th>Diverging wave</th>
    <th>Hadamard-coded aperture</th>
    <th>Random binary-coded aperture</th>
  </tr>
  <tr>
    <td><img src="assets/subject-002_planewave_frame-000.png" alt="Plane-wave cardiac image"></td>
    <td><img src="assets/subject-002_diverging_frame-000.png" alt="Diverging-wave cardiac image"></td>
    <td><img src="assets/subject-002_hadamard_frame-000.png" alt="Hadamard-coded aperture cardiac image"></td>
    <td><img src="assets/subject-002_random_frame-000.png" alt="Random binary-coded aperture cardiac image"></td>
  </tr>
  <tr>
    <td colspan="4"><small>Output images of <code>reconstruct.py</code> for every transmit type of subject 2.</small></td>
  </tr>
</table>

## Citation

Suggested citation for the dataset:

> Penninga, S. W., & van Sloun, R. J. G. (2026). *TU/e Cardiac RF Multi-Transmit* [Data set]. Eindhoven University of Technology, Open-H-RF.

```bibtex
@misc{penninga_tue_cardiac_plax_2026,
  title        = {TU/e Cardiac PLAX Multi-Transmit RF},
  author       = {Penninga, Simon W. and van Sloun, Ruud J. G.},
  year         = {2026},
  publisher    = {Biomedical Diagnostics Lab, Eindhoven University of Technology},
  howpublished = {Open-H-RF dataset},
}
```

## Dataset Quantification

**Current Open-H-RF release:** 12 HDF5 files; 199.18 GB (199,180,025,844 bytes) stored; root `zea_version` **0.1.4**.
- **Participants/files:** 12 distinct people represented by 12 HDF5 files.
- **Tracks/acquisitions:** 8 tracks per file; 96 acquisitions total.
- **Frames:** 100 per track; 9,600 frames total.
- **Raw-data tensor:** `(100, 80, 2304, 80, 1)` per track.

## Data Validation

Four saved zea pipeline configurations are provided under `pipelines/`:

| Pipeline | Tracks | Difference from general pipeline |
|---|---|---|
| `pipeline.yaml` | `focused_fund`, `wide_fund`, `planewave`, `diverging` | General RF-to-B-mode pipeline |
| `pipeline_harmonic.yaml` | `focused_harm`, `wide_harm` | Denser output grid for second-harmonic receive frequency |
| `pipeline_hadamard.yaml` | `hadamard` | Adjoint REFoCUS decoding before beamforming |
| `pipeline_random.yaml` | `random` | Tikhonov-regularized REFoCUS decoding before beamforming |

All configurations perform RF filtering, demodulation, delay-and-sum beamforming, envelope detection, normalization, log compression, and scan conversion.

## Known Issues

- A good PLAX view is not always available for all recordings.
- Some transmit types, like random apodization recordings, do not give a good quality B-mode. They are not intended to have the best quality, but for comparison.
- The two harmonic tracks are pulse-inversion-accumulated nonlinear measurements and should not be treated as linear equivalents of the fundamental tracks.
- Accumulated harmonic data may lack per-transmit timing arrays; the measured frame rate is documented instead.
- Hadamard and random tracks require REFoCUS decoding before conventional beamforming.
- A Verasonics scalar lens-delay correction is retained under `/custom` for provenance, but it is not equivalent to zea's refractive lens model.

## Ethical Considerations

Approval was obtained from the Ethical Review Board TU/e (Eindhoven University of Technology). Reference: ERB2023EE7 Contact details for the Ethical Review Board TU/e: T +31 (0)40 247 6259 <ethics@tue.nl> <intranet.tue.nl/ethics>
