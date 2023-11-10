# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from functools import lru_cache

from promptflow._sdk.entities import FlowContext
from promptflow.executor import FlowExecutor

# Resolve flow context to executor
# Resolve flow according to flow context
#   Resolve connection, variant, overwrite, store in tmp file
# create executor based on resolved flow
# cache executor if flow context not changed (define hash function for flow context).


class FlowContextResolver:
    """Flow context resolver."""

    @lru_cache()
    @classmethod
    def resolve(cls, flow_context: FlowContext) -> FlowExecutor:
        """Resolve flow context to executor."""
