# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# General todo: need to determine which args are required or optional when parsed out into groups like this.
# General todo: move these to more permanent locations?

# Defines stuff related to the resulting created index, like the index type.

from typing import Optional
from ._connection_config import ConnectionConfig
from promptflow.rag.constants._common import CONNECTION_ID_FORMAT


class EmbeddingsModelConfig:
    """Config class for a embedding model.

    :param model_name: The name of the embedding model.
    :type model_name: Optional[str]
    :param deployment_name: The deployment_name for the embedding model.
    :type deployment_name: Optional[str]
    :param connection_id: The connection id for the embedding model.
    :type connection_id: Optional[str]
    :param connection_config: The connection configuration for the embedding model.
    :type connection_config: Optional[ConnectionConfig]
    """

    def __init__(
        self,
        *,
        model_name: Optional[str] = None,
        deployment_name: Optional[str] = None,
        connection_id: Optional[str] = None,
        connection_config: Optional[ConnectionConfig] = None,
    ) -> None:
        self.model_name = model_name
        self.deployment_name = deployment_name
        self.connection_id = connection_id
        self.connection_config = connection_config

    def get_connection_id(self) -> Optional[str]:
        """Get connection id from connection config or connection id"""
        import re

        if self.connection_id:
            if not re.match(CONNECTION_ID_FORMAT, self.connection_id):
                raise ValueError(
                    "Your connection id doesn't have the correct format"
                )
            return self.connection_id
        if self.connection_config:
            return self.connection_config.build_connection_id()
        return None
