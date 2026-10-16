---
name: colorado-boulder
pretty_name: "Tracked Swept Synthetic Aperture Ultrasound Datasets"
license: cc-by-4.0
task_categories:
  - generalized-reconstruction
tags:
  - ultrasound
  - rf
  - open-h-rf
  - 3d
language:
  - en
size_categories:
  - n<1K
---

# Tracked Swept Synthetic Aperture Ultrasound Datasets

| 2D ATS 539 phantom | 3D phantom | In-vivo quadriceps |
|:---:|:---:|:---:|
| ![Tracked SSA sweep through the 2D ATS 539 phantom](assets/ssa-sweep-phantom2d.gif) | ![Tracked SSA sweep through the 3D phantom](assets/ssa-sweep-phantom3d.gif) | ![Tracked SSA sweep along in-vivo quadriceps muscle](assets/ssa-sweep-invivo.gif) |
| [`Sub-dataset-1`](https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/colorado-boulder/Sub-dataset-1) | [`Sub-dataset-2`](https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/colorado-boulder/Sub-dataset-2) | [`Sub-dataset-3`](https://huggingface.co/datasets/nvidia/Open-H-RF/tree/main/colorado-boulder/Sub-dataset-3) |

*Motion-compensated tracked SSA reconstructions, one per sub-dataset. Each frame beamforms the raw RF channel data with its own tracked probe pose; a 40 mm window of frames is then coherently summed to synthesise a larger effective aperture, and the window slides along the freehand sweep.*

## Dataset Description

This dataset contains tracked swept synthetic aperture (SSA) ultrasound acquisitions from three targets: a 2D ATS 539 multipurpose imaging phantom, a 3D ultrasound imaging phantom, and in-vivo quadriceps muscle from healthy volunteer participants.

The data were acquired using a Verasonics Vantage research ultrasound system with a P4-2 phased array transducer. The dataset includes raw RF channel data, acquisition parameters, probe geometry, transmit information, and frame-wise tracked probe pose metadata.

The purpose of this dataset is to provide reproducible examples for generalized ultrasound reconstruction, with a particular focus on motion-compensated tracked SSA reconstruction using the zea/Open-H-RF data format.

The phantom acquisitions do not contain human subject data, animal data, or protected health information (PHI). The in-vivo acquisitions were collected from healthy volunteer participants and de-identified prior to release.

## Dataset Contributor(s)

- Anet Sanchez (University of Colorado Boulder, Bottenus Lab)
- Nick Bottenus (University of Colorado Boulder, Bottenus Lab)

## Dataset Creation Date

Data were collected between 08/23/2024 and 06/30/2026.

## License / Terms of Use

[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode.en). Retain attribution and identify modifications when reusing the data.

## Intended Usage

This dataset is intended for research on generalized ultrasound reconstruction, with a specific focus on tracked swept synthetic aperture imaging, motion-compensated beamforming, coherent compounding, and ultrasound image-quality evaluation.

For SSA reconstruction, each raw RF frame is beamformed using its corresponding tracked transducer pose. The resulting beamformed frames are placed on a common reconstruction grid and coherently summed to synthesize a larger effective aperture. Because the reconstruction relies on coherent compounding, summation is performed before envelope detection, normalization, and log compression.

## Dataset Characterization

The dataset includes acquisitions from three targets:

- 2D ATS 539 multipurpose imaging phantom
- 3D ultrasound imaging phantom
- In-vivo quadriceps muscle from healthy volunteer participants

The ATS 539 multipurpose imaging phantom contains:

- Wire targets
- Cylindrical lesions
- Tissue-mimicking speckle regions

These targets may be used to assess spatial resolution, contrast, lesion visibility, and speckle characteristics.

### Data Collection Method

Each acquisition consisted of a freehand sweep in the lateral direciton of the transducer. All 64 array elements were used during receive. Diverging waves were generated using a negative virtual source while activating the 20 central array elements during transmit. For in-vivo targets the transducer was manually swept along the longitudinal direction of the quadriceps while transmitting diverging waves at 400 Hz. The transducer was optically tracked using an NDI Polaris Vega® XT optical tracking system manufactured by Northern Digital Inc., Ontario, Canada.

### Labeling Method

None (N/A).

### Acquisition System

- Verasonics Vantage research ultrasound scanner
- Verasonics P4-2 phased array transducer
- 64 elements
- Reconstruction center frequency: 2.5 MHz
- Sampling frequency: 10 MHz
- Optical tracking: NDI Polaris Vega XT

## Processing the Dataset

The acquisitions can be processed with the `reconstruct.py` [script](https://github.com/open-h/Open-H-RF/blob/main/datasets/colorado-boulder/reconstruct.py) as provided in the [Open-H-RF GitHub repository](https://github.com/open-h/Open-H-RF), together with the `pipeline.yaml` definition in this folder and the [zea library](https://github.com/tue-bmd/zea). The script streams the data from the Hugging Face Hub.

The script selects tracked frames at roughly 1 mm lateral spacing and writes the reconstruction to `ssa_bmode.png`. Point `ZEA_FILE` at any acquisition in the corpus to reconstruct it. [`assets/main_bmode.png`](./assets/main_bmode.png) was produced this way, compounding the full sweep into one image; the loops at the top of this card slide a shorter aperture window along the sweep instead.

`reconstruct.py` defines the custom `apply_probe_pose` operation that `pipeline.yaml` refers to, which applies the frame-wise `metadata/probe_pose` to the probe geometry and transmit origins before beamforming.

## Dataset Format

[zea v0.1.7](https://github.com/tue-bmd/zea)

The dataset is distributed in the zea/Open-H-RF HDF5 format.

Each file includes:

- Raw RF channel data
- Sampling and center frequencies
- Transmit delays and apodization
- Transmit origins
- Probe geometry
- Sound-speed information
- Frame-wise tracked probe translations
- Frame-wise tracked probe rotations

The stored RF channel data have not been beamformed, demodulated, envelope detected, normalized, or log compressed. These processing steps are performed by the accompanying reconstruction pipeline.

## Dataset Quantification

- Number of phantom objects: 2
- Number of volunteer participants: 7
- Number of acquisitions: 62
- Number of RF frames per acquisition: 1200–1600
- Number of transmit events per frame: 1
- Number of receive elements: 64
- Number of active transmit elements: 20

### Per-acquisition contents

| Feature | Shape | Data type | Units | Description |
|---|---:|---|---|---|
| Raw RF data | `n_frames × n_tx × n_ax × n_elements × n_channels` | `float32` | acquisition units | Raw RF channel measurements |
| Probe translation | `n_frames × 3` | `float32` | m | Frame-wise tracked probe position |
| Probe rotation | `n_frames × 4` | `float32` | unit quaternion | Frame-wise tracked probe orientation in `xyzw` order |
| Probe geometry | `64 × 3` | `float32` | m | Array-element coordinates |
| Transmit origins | `n_tx × 3` | `float32` | m | Diverging-wave virtual-source coordinates |
| Transmit delays | `n_tx × 64` | `float32` | s | Per-element transmit delays |
| Transmit apodization | `n_tx × 64` | `float32` | unitless | Per-element transmit activation and weighting |

## Subject Metadata

This dataset contains acquisitions from two ultrasound imaging phantoms and healthy volunteer participants.

- Subject types: 2D imaging phantom, 3D phantom, and in-vivo human ultrasound data
- 2D phantom model: ATS 539
- 2D phantom target types: wires, cylindrical lesions, and tissue-mimicking speckle
- In-vivo anatomical region: quadriceps muscle
- Human participants: healthy volunteer participants for the in-vivo dataset
- Animal subjects: None
- Protected health information: None
- Scanner: Verasonics Vantage
- Probe: Verasonics P4-2 phased array

## Data Validation

The submission includes a `zea.Pipeline` that reconstructs representative tracked SSA B-mode images from the raw RF channel data.

The pipeline performs:

1. Frame-wise demodulation
2. Application of the tracked probe pose
3. Delay-and-sum beamforming onto a common reconstruction grid
4. Coherent SSA compounding
5. Envelope detection
6. Normalization
7. Log compression

## Known Issues

- Optical tracking measurements may contain small position and orientation uncertainties.
- Reconstruction quality depends on tracking calibration accuracy and coherent alignment between frames.
- The in-vivo dataset is intended for research use and has not been optimized for clinical workflows.

## Ethical Considerations

- **Phantom data:** phantom ultrasound acquisitions only — no human participants, animal subjects, personal identifiers or clinical records; consent and IRB approval are not applicable.
- **In-vivo data:** acquired from healthy volunteer participants with informed consent under IRB-approved protocol #24-0176, and de-identified prior to release.
- No protected health information (PHI) or participant-identifying metadata is included in the released files.
