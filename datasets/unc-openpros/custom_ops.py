# SPDX-License-Identifier: Apache-2.0
"""Keras operations for converting OpenPROS array layouts."""

from keras.ops import abs, concatenate, log1p, sign, split
from zea.internal.registry import ops_registry
from zea.ops import Operation


# These ops are defined here, not in zea: a pipeline.yaml naming them resolves
# only once this module is imported. See https://github.com/open-h/Open-H-RF
@ops_registry("openpros.custom_ops.MyRearrange")
class MyRearrange(Operation):
    """Restore the original OpenPros ``data`` layout from the stored ``raw_data``."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def call(self, **kwargs):
        raw_data = kwargs[self.key]  # 20, 1000, 322, 1
        surface_tx, rectum_tx = split(raw_data, 2, axis=1)
        ss, sr = split(surface_tx, 2, axis=3)
        rs, rr = split(rectum_tx, 2, axis=3)
        data = concatenate((ss, sr, rr, rs), axis=1)

        return {self.output_key: data}


@ops_registry("openpros.custom_ops.LogTransform")
class LogTransform(Operation):
    """Apply a sign-perserved logarithmic transform to the input data."""

    ADD_OUTPUT_KEYS = ["input_range"]  # for follow-up normalization

    def __init__(self, k=1.0, c=0.0, data_min=None, data_max=None, **kwargs):
        super().__init__(**kwargs)
        self.k = k
        self.c = c
        self.data_min = data_min
        self.data_max = data_max

    def call(self, **kwargs):
        data = kwargs[self.key]
        data = (log1p(abs(self.k * data) + self.c)) * sign(data)
        if self.data_min is not None and self.data_max is not None:
            log_data_min = log1p(abs(self.k * self.data_min) + self.c) * sign(self.data_min)
            log_data_max = log1p(abs(self.k * self.data_max) + self.c) * sign(self.data_max)
            _input_range = (log_data_min, log_data_max)
        else:
            _input_range = None
        return {self.output_key: data, "input_range": _input_range}
