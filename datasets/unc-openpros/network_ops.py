# SPDX-License-Identifier: Apache-2.0
"""Pipeline operation that runs the pretrained InversionNet model from ``zea``.

The network itself lives in :mod:`zea.models.inversionnet` and its weights are
downloaded from the Hugging Face Hub, so nothing model-related is vendored here.
"""

from keras import ops
from zea.internal.registry import ops_registry
from zea.models.inversionnet import InversionNet
from zea.ops import Operation


# These ops are defined here, not in zea: a pipeline.yaml naming them resolves
# only once this module is imported. See https://github.com/open-h/Open-H-RF
@ops_registry("openpros.network_ops.InversionNetInference")
class InversionNetInference(Operation):
    """Reconstruct a normalized speed-of-sound map from preprocessed waveforms."""

    def __init__(self, preset: str, **kwargs):
        super().__init__(**kwargs)
        self.preset = preset
        self.model = InversionNet.from_preset(preset)

    def call(self, **kwargs):
        data = kwargs[self.key]
        # MyRearrange leaves the data channels-first: (frames, 40, 1000, 161, 1).
        # zea models are channels-last, like the rest of Keras.
        data = ops.transpose(ops.squeeze(data, axis=-1), (0, 2, 3, 1))
        return {self.output_key: self.model(data)}
