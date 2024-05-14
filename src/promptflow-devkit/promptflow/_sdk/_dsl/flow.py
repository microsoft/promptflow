# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Union

from promptflow._sdk.entities._experiment import FlowNode
from promptflow._sdk.entities._flows.base import FlowBase


def flow(
    flow: Union[str, FlowBase],
):
    return FlowNode(flow=flow)
