# Open-H-RF — reconstructions

The code counterpart to [**Open-H-RF**](https://huggingface.co/datasets/nvidia/Open-H-RF) on the Hugging Face Hub. The data lives there; the reconstructions scripts are here.

Each directory consists of:

| File | |
|---|---|
| `reconstruct.py` | runnable reference reconstruction, input path at the top |
| `pipeline.yaml` | the processing recipe it runs |
| `README.md` | the data card, as published on the Hub |

## Running

From the repository root:

```bash
uv sync                    # installs zea and a JAX CPU backend
export KERAS_BACKEND=jax   # or torch, tensorflow if installed

python datasets/tue-carotid/reconstruct.py
```

Every script streams its input straight from the Hub, so there is nothing to download first. To reconstruct something else, change the `hf://` path at the top of the script.

Processing is done with [`zea`](https://github.com/tue-bmd/zea) (>= 0.1.6), which defines the HDF5 format the corpus is stored in. See its [installation docs](https://zea.readthedocs.io/en/latest/installation.html) for the other backends.
