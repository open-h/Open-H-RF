# Metadata the site corrects

Metadata the site corrects at build time, pending a fix in the files or cards on the Hub.
Each entry says where the fix lives, to be removed once the source is fixed.

## Probe names (`PROBE_ALIASES` in `corpus.py`)

The probe chart, the probe count and the Probe filter count the same hardware under one name.
Each dataset still lists the names its files give. Evidence is the geometry stored in the
files.

| File spelling | Counted as | Dataset(s) | Files | Evidence |
|---|---|---|---|---|
| `P4-1` | `P4-2v` | `oslo/E_simulation`, `oslo/C_verasonics_phantom` | 5 | See below. |
| `P4-2` | `P4-2v` | `oslo/A_cardiac`, `oslo/C_verasonics_phantom` | 4 | 64 elements, 0.30 mm pitch. |
| `Verasonics P4-2v` | `P4-2v` | `vanderbilt` | 165 | Spelling only. |
| `custom_p4_2_64_element` | `P4-2v` | `colorado-boulder` | 62 | 64 elements, 2.5 MHz, but 0.32 mm pitch against the others' 0.30 mm. |
| `verasonics_c5_2v` | `C5-2v` | `unc-liver`, `tue-aaa` | 1921 | Spelling only. |
| `verasonics_l11_5v` | `L11-5v` | `tue-carotid`, `weizmann-sampl` | 110 | Spelling only. |
| `Elevation Focused Linear Array Transducer` | `L11-5v` | `concordia` | 2000 | 128 elements, 0.30 mm pitch, 5.2 MHz. An L11-4v has the same element count and pitch, so this is a guess. |
| `verasonics_l11_4v` | `L11-4v` | `twente-cavitation` | 19 | Spelling only. |
| `Simulated 10L4 Transducer` | `Siemens ACUSON 10L4` | `nv-raw2insights-us` | 923 | Simulation of the probe: 180 elements, 0.20 mm pitch, as in `siemens-healthineers`. |

Oslo's `P4-1` files store the geometry of a P4-2 (64 elements, 0.30 mm pitch, 18.9 mm
aperture), not of a P4-1 (96 elements, 28 mm aperture, as in `twente-microbubblesim`). Fix at
the source: correct `probe/name`.

## Probe type (`probe_class` and `paper_probe_class` in `corpus.py`)

`us4us` stores its ring array as `probe/type = curved`. A curved probe whose curve is as
deep as it is wide is counted as a ring. Fix at the source: store `ring`.

## Probe centre frequency (`probe_frequency` in `corpus.py`)

Some files have no `probe/probe_center_frequency`. For the elements-against-frequency figure
(on the site and in the paper), it is taken from the data card for `kaist-snubh-barreleye`,
`resolvestroke` and `wpi` (`DATA_CARD_HZ`), and from the middle of the maker's range for the
Waterloo probes (`NOMINAL_RANGE_HZ`). Everywhere else the site shows it as missing.
Fix at the source: store the probe's centre frequency in `probe/probe_center_frequency`.

## Transmit scheme (`transmit_kinds` and `PLACEHOLDER_TRANSMITS` in `corpus.py`)

The scheme is read from the focus distances and transmit apodizations. Where those say the
wrong thing:

- `unc-openpros` is a simulated ultrasound CT whose card calls the stored transmit fields
  placeholders. All its tracks are tomographic.
- A track labelled `hadamard` or `chirp` is coded (`CODED_LABELS`). `stanford-murine` stores
  its Hadamard track decoded, as one-hot single-element transmits, so it would otherwise
  read as synthetic aperture. `twente-vortexflow`'s chirp is in the waveform, not the
  apodization, so it would read as a plane wave.
- An array that never transmits only listens (`twente-cavitation`: passive), and a single
  element that is the whole probe is a rotating catheter (`mosaic-nuevosono`: other).
  Otherwise both would read as synthetic aperture.

Fix at the source: correct the `stanford-murine` card, which says the apodizations keep the
Hadamard polarity.

Not fixed: `colorado-boulder` and `tue-aaa` store their diverging waves with an infinite
focus distance, so they read as plane waves.

## Institutions (`datasets:` in `catalog.yaml`, and `institution_filters.csv`)

A dataset's institution comes from its card's contributors section. `catalog.yaml` overrides
it where that section leaves the institution out or names it in a form `cards.py` does not
read, and drops the other OpenPros affiliations from `unc-openpros`, since they are not
the affiliations of its authors.

The other affiliations of a dataset's authors are its `collaborating_institutions`:
NuevoSono (`mosaic-nuevosono`), Ruhr University Bochum (`politorino`), ImFusion
(`tumunich`), Mila (`ulmshare`), North Carolina State University (`unc-liver`) and Johns
Hopkins University, National Institutes of Health, Iowa State University and QT Imaging
(`unc-openpros`). The page does not show them, but
search and the institution filter find the dataset by them, and the institution count
counts them.

`institution_filters.csv` maps each affiliation in the authors list to the name the datasets
use, and lists the institutions datasets are from that are no author's affiliation.

Fix at the source: name the institutions in each card's contributors section as the authors
list does, including the collaborating ones.

## In-vivo subjects (`build()` in `corpus.py`)

Subject ids are not unique across datasets, so the total counts distinct ids per institution
(the Waterloo datasets share volunteers). The page does not show this total; the
per-dataset chart counts distinct ids within each dataset.

## Not fixed: anatomy `"none"`

`siemens-healthineers` stores `anatomy = "none"` in 60 files. The site's metadata coverage
counts it as present.
