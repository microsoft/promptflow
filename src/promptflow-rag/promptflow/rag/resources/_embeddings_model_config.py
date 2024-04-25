# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# General todo: need to determine which args are required or optional when parsed out into groups like this.
# General todo: move these to more permanent locations?

# Defines stuff related to the resulting created index, like the index type.

from typing import Optional
from ._connection_config import ConnectionConfig


class EmbeddingsModelConfig:
    """Config class for a embedding model.

    :param model_name: The name of the embedding model.
    :type model_name: Optional[str]
    :param deployment_name: The deployment_name for the embedding model.
    :type deployment_name: Optional[ConnectionConfig]
    :param connection_config: The connection configuration for the embedding model.
    :type connection_config: Optional[ConnectionConfig]
    """

    def __init__(
        self,
        *,
        model_name: Optional[str] = None,
        deployment_name: Optional[str] = None,
        connection_config: Optional[ConnectionConfig] = None,
    ) -> None:
        self.model_name = model_name
        self.deployment_name = deployment_name
        self.connection_config = connection_config
