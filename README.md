<h1 align="center">
  <a href="https://open-h.github.io/OpenH-RF/"><img src="site/assets/img/logo/logo-glow-transparent.svg" alt="" height="56" align="absmiddle"></a> OpenH-RF
</h1>

<p align="center"><em>An open, large-scale, community-driven dataset of medical ultrasound channel capture data</em></p>

<div align="center">

[![Website](assets/badge-website.svg)](https://open-h.github.io/OpenH-RF/)
[![Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-OpenH--RF-FFD21E?style=for-the-badge)](https://huggingface.co/datasets/nvidia/OpenH-RF)
[![arXiv](https://img.shields.io/badge/arXiv-2610.13616-B31B1B?style=for-the-badge&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2610.13616)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-7289DA?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/gNTJeUsH2B)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=for-the-badge)](LICENSE)

</div>

## About

OpenH-RF is a collaborative initiative led by [Stanford University](https://med.stanford.edu/ultrasound.html), [Eindhoven University of Technology (TU/e)](https://www.tue.nl/en/research/research-groups/signal-processing-systems/biomedical-diagnostics) and [NVIDIA](https://www.nvidia.com/) to build a large-scale, openly licensed dataset of pre-beamformed (channel capture) medical ultrasound measurements. *The goal:* train general-purpose foundation models capable of multi-task *raw-to-insight* inference across echocardiography, general, fetal and transcranial imaging, blood flow measurement and ultrasound inverse problems.

The initial (v1.0) release of the dataset contains **19,336** real and synthetic channel capture measurements, spanning a wide variety of acquisition types, targets and downstream tasks, including reconstruction, flow, quantitative imaging, motion estimation and interpretation tasks, contributed by **38 institutions** across academia and industry. Released under [**CC BY 4.0**](https://creativecommons.org/licenses/by/4.0/).

The OpenH-RF format is implemented using the [zea](https://zea.readthedocs.io/en/latest/getting-started.html) ultrasound toolbox. Each file holds the raw per-element channel data together with the full transmit and receive geometry needed to beamform it. Where available, files also include derived images, maps, labels and auxiliary signals that help interpret the data.

> [!TIP]
> Explore the dataset on our [catalog page](https://open-h.github.io/OpenH-RF/) and filter by imaging target, acquisition type, downstream task, or contributor.

## 📣 Updates

- 📄 **October 2026** — [The OpenH-RF preprint is out on arXiv!](https://arxiv.org/abs/2610.13616)
- 🤗 **October 2026** — [OpenH-RF v1.0 is publicly released on Hugging Face!](https://huggingface.co/datasets/nvidia/OpenH-RF)
- 🚀 **September 2026** — [OpenH-RF v1.0 early-access pre-release is live on Hugging Face!](https://huggingface.co/datasets/nvidia/OpenH-RF)

## How to Participate

1. **Review the RFP** — Read the [Request for Proposals](assets/OpenH-RF%20Request%20for%20Proposals%20(RFP).pdf) for technical scope, eligibility and evaluation criteria.
2. **Submit a Proposal** — Prepare a concise proposal (≤ 5 pages) describing your dataset, collection methodology and target tasks. Submit to [this Google Form](https://forms.gle/tqiqYSnnar1AekB19).
3. **Contribute Data** — Once approved, prepare your dataset in the OpenH-RF format, implemented in [`zea`](https://github.com/tue-bmd/zea) as documented [here](https://zea.readthedocs.io/en/v0.1.0a3/data-acquisition.html), along with a datacard specifying the CC BY 4.0 license. Approved contributors are given a dedicated shared storage location (S3 or Google Drive) for delivery and a Discord channel for coordination.
4. **Co-author the Release** — Approved contributions are included in the public dataset and foundation model release — contributors are named co-authors in related publications upon project completion.

## Key Dates

| Milestone | Date |
|-----------|------|
| ~~RFP released~~ | ~~March 16, 2026~~ |
| ~~Proposal submission deadline~~ | ~~June 10, 2026~~ |
| ~~Data collection window~~ | ~~May – July 2026~~ |
| ~~Dataset delivery deadline~~ | ~~July 12, 2026~~ |
| ~~Dataset public release (v1.0)~~ | ~~October 4, 2026~~ |
| Model training & validation | Q4 2026 |
| Foundation model release | TBD |

## Steering Committee

| Role | Name | Affiliation |
|------|------|-------------|
| AI Lead | Prof. Ruud J.G. van Sloun | TU/e |
| Ultrasound Lead | Prof. Jeremy Dahl | Stanford University |
| Industry Lead | Dr. Walter Simson | NVIDIA |

## Dataset Format

The OpenH-RF format is implemented using the [`zea`](https://github.com/tue-bmd/zea) ultrasound toolbox. See the `zea` documentation for the [data specification](https://zea.readthedocs.io/en/v0.1.0a3/data-acquisition.html). The [`examples/templates/`](examples/templates/) directories are starting points for a submission — each has a `convert.py` (data → openh-rf `.hdf5`), a `reconstruct.py` (raw channel data → B-mode), and a `pipeline.yaml`:

| Example | Modality |
|---------|----------|
| [`echocardiography template`](examples/templates/echocardiography/convert.py) | Cardiac (phased array): focused transmits, ECG + clinical metadata, annotations |
| [`color-doppler template`](examples/templates/color-doppler/convert.py) | Linear array (plane-wave): B-mode + color Doppler velocity map, ECG, annotations |
| [`segmentation template`](examples/templates/segmentation/convert.py) | Raw RF data with per-frame segmentation masks and view labels |
| [`verasonics template`](examples/templates/verasonics/convert.py) | Converting a real Verasonics `.mat` workspace to OpenH-RF |
| [`nv-raw2insights-us/`](examples/nv-raw2insights-us/) | Worked example on a real public dataset: stream a sample from [NV-Raw2Insights-US](https://huggingface.co/datasets/nvidia/NV-Raw2Insights-US), convert to OpenH-RF, and beamform raw channel data back to a B-mode |
| [`pala-ulm-ratbrain/`](examples/pala-ulm-ratbrain/) | Converting [PALA](https://zenodo.org/records/7883227) rat-brain plane-wave channel data from Zenodo to OpenH-RF format and beamforming to a B-mode |
| [`tracked-cirs-phantom/`](examples/tracked-cirs-phantom/) | Converting a tracked CIRS phantom acquisition to OpenH-RF, reconstructing a B-mode, and visualizing the tracked probe trajectory |
| [`examples/reconstruct_example.py`](examples/reconstruct_example.py) | Reconstructing a B-mode image from raw RF channel data using the default `zea` pipeline |
| [`examples/save_pipeline_example.py`](examples/save_pipeline_example.py) | Saving a `zea` processing pipeline as a reusable YAML config |

For a submission usually one `pipeline.yaml` + `reconstruct.py` pair suffices. If your submission bundles multiple sub-datasets (distinct acquisition types or geometries) as separate folders under one submission root, please give each sub-dataset folder its own `pipeline.yaml` + `reconstruct.py` rather than sharing one pair at the root instead of growing branching logic to auto-detect which sub-dataset it's running on. A shared root-level pair is still perfectly fine when the pipeline is identical across all sub-datasets.

## Setup

This repo uses [`uv`](https://docs.astral.sh/uv/) for environment + dependency management. Install it once: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

```bash
git clone https://github.com/open-h/OpenH-RF
cd OpenH-RF
uv sync
export KERAS_BACKEND=jax
uv run python examples/save_pipeline_example.py
```

`uv sync` creates `.venv/` and installs dependencies listed in `pyproject.toml`. Run any script with `uv run python <script>.py`, or activate the venv with `source .venv/bin/activate`.

`zea` is pinned in `uv.lock` to a specific commit of the moving [`openh-rf-latest`](https://github.com/tue-bmd/zea/tree/openh-rf-latest) tag, so every clone builds against the same spec. When the spec advances and you want the newer `zea`, bump the pin with `uv lock --upgrade-package zea` and commit the updated `uv.lock`.

Pick a backend / accelerator with extras:

| Use case | Command |
|----------|---------|
| JAX (CPU, default)   | `uv sync` |
| JAX + CUDA           | `uv sync --extra gpu` |
| PyTorch              | `uv sync --extra torch` (Linux pip wheels include CUDA by default) |
| TensorFlow (CPU)     | `uv sync --extra tf` |
| TensorFlow + CUDA    | `uv sync --extra tf-gpu` |

Set the matching `KERAS_BACKEND` (`jax`, `torch`, or `tensorflow`) before running examples.

> [!NOTE]
> On Windows, use WSL2.

## Citation

If you use OpenH-RF in your research, please cite the [OpenH-RF paper](https://arxiv.org/abs/2610.13616):

```bibtex
@misc{stevens2026openhrf,
  title = {{OpenH-RF}: A Large-Scale Ultrasound Raw Channel Dataset Initiative},
  author = {T. S. W. Stevens and S. W. Penninga and W. L. van Nierop and O. Nolan and F. Duelmer and
            B. N. Frey and B. Federici and V. van Hal and L. D. van Harten and H. de Hoop and
            R. Lopata and B. Luijten and M. van Sambeek and V. van der Schaft and H.-M. Schwab and
            M. F. Azampour and N. Navab and R. Ali and A. Andrzejek and J. Baek and B. Boitnott and
            T. Brevett and H. Hashemi and D. Hyun and J. H. Park and A. V. Telichko and
            C. Thomas and L. Zhuang and Y. Aklilu and H. Arora and J. Barker and A. K. Mackanic and
            P. McDowall and L. McHugh and I. Pirozzi and S. Simon-Trench and A. M. Bronstein and
            O. Senouf and S. Vedula and D. Zadok and H. Rivaz and M. Sharifzadeh and S. Chen and
            G. P. Luke and S. Wang and Yujia Wu and J. Verde and R. G{\"o}bl and O. Zettinig and
            E. Boctor and Yixuan Wu and H.-M. Bae and M.-G. Kim and Y.-M. Kim and H. Lee and
            S.-H. Oh and P. Pinto and M. Berrada-Sounni and M. Carley and R. J. Fedewa and
            S. Gavin and N. Goldsmith and R. Kassayan and C. Low and R. Mehranfar and
            G. Bardoscia and M. Boccardo and A. Botter and M. Carbonaro and G. L. Cerone and
            E. Cesti and K. Meiburger and S. Seoni and F. Truscello and B. J. Raiteri and
            L. Caron and M. Gasse and N. Ghigo and O. Gulenko and A. Leconte and S. A. Lee and
            A. Malescot and E. Martineau and J. Por{\'e}e and J. Provost and G. Ramos-Palacios and
            B. Rauby and R. L. Rungta and A. F. Sadikot and A. Wu and P. Xing and A. Chavignon and
            C. Ferlay and V. Hingot and M. Reberol and A. Waelbroeck and H.-S. Kwon and
            J. Bucholz and I. Guracar and R. Loftman and C. Williams and T. Grutman and
            T. Ilovitsh and T. A. Aleef and P. B. Chen and W. Chen and Y. Chen and M. Frew and
            M. Honarvar and Y. C. Lee and Z. Li and H. Moradi and R. Rohling and S. E. Salcudean and
            Z. Wu and Q. Zeng and P. C. Cattin and S. El Hadramy and N. Bottenus and A. S. Perez and
            S. Feng and Y. Feng and P. Jin and Y. Lin and O. Ostras and G. Pinton and
            F. Santibanez and M. Sode and B. Turkbey and H. Wang and B. J. Wood and L. Zhang and
            S. Luo and J. Wiskin and A. Austeng and Y. Karabiyik and S. P. N{\"a}sholm and
            O. M. H. Rindal and D. Bustamante and M. Mehrmohammadi and H. Raeis and A. Hameddine and
            G. Lajoinie and H. de Roo and M. Versluis and R. Zorgdrager and J. S. Au and
            A. J. Y. Chee and J. Cohen and T. Gu and J. Y.-H. Hsu and S. Ling and M. Mourtzakis and
            H. Nahas and P. de la Torre and D. Xiao and A. C. H. Yu and E. Zafiris and
            P. Jarosik and P. Karwat and Z. Klimonda and M. Lewandowski and B. Byram and C. Khan and
            Z. Marshall and Y.-C. Pan and S. Liu and T. Sultan and C. Hoerig and J. Mamou and
            D. Auerbach and Y. C. Eldar and A. Wegerhoff and G. S. Fischer and S. Katayose and
            X. Ma and R. Murakami and Y. Tang and R. Tsumura and Y. Wang and H. K. Zhang and
            M. Azizian and S. Huver and J. J. Dahl and R. J. G. van Sloun and W. Simson},
  year = {2026},
  eprint = {2610.13616},
  archivePrefix = {arXiv},
  primaryClass = {eess.SP},
  doi = {10.48550/arXiv.2610.13616},
  url = {https://arxiv.org/abs/2610.13616}
}
```

## Contact

- **Technical questions** — [openh.data+rf@gmail.com](mailto:openh.data+rf@gmail.com), the [Hugging Face dataset community page](https://huggingface.co/datasets/nvidia/OpenH-RF/discussions), or the [`zea` community page](https://github.com/tue-bmd/zea/discussions)
- **Administrative questions** — [wsimson@nvidia.com](mailto:wsimson@nvidia.com)
- **Community** — [Join our Discord](https://discord.gg/gNTJeUsH2B)

## License

Code in this repository is licensed under the [Apache License 2.0](LICENSE). The released dataset (when published) will be licensed under CC BY 4.0.
