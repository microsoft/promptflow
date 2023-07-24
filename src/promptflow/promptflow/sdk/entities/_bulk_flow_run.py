# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from typing import Any, Dict, Optional


class BulkFlowRun:
    def __init__(
        self,
        name: Optional[str] = None,
        flow_id: Optional[str] = None,
        input=None,
        output=None,
        detail: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.flow_id = flow_id
        self.input = input
        self.output = output
        self.detail = detail
        self._metrics = metrics
        self.evaluation_runs = []

    def __getitem__(self, key: str):
        if hasattr(self, key):
            return getattr(self, key)
        else:
            raise AttributeError(f"Attribute {key} is not supported.")

    @property
    def metrics(self):
        if self._metrics is None:
            return None
        updated_metrics = {}
        for k, v in self._metrics.items():
            if isinstance(v, list):
                updated_metrics[k] = v[0]["value"]
        return updated_metrics

    @metrics.setter
    def metrics(self, value):
        self._metrics = value

    @classmethod
    # pylint: disable=unused-argument
    def _resolve_cls_and_type(cls, data, params_override):
        """Resolve the class to use for deserializing the data. Return current class if no override is provided.
        :param data: Data to deserialize.
        :type data: dict
        :param params_override: Parameters to override, defaults to None
        :type params_override: typing.Optional[list]
        :return: Class to use for deserializing the data & its "type". Type will be None if no override is provided.
        :rtype: tuple[class, typing.Optional[str]]
        """
        return cls, "batch_run"

    def __repr__(self):
        return f"BulkFlowRun({json.dumps(self.__dict__, indent=4)})"
