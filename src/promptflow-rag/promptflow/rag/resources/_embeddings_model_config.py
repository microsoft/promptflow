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

    :param embeddings_model: The name of the embedding model.
    :type embeddings_model: Optional[str]
    :param connection_config: The connection configuration for the embedding model.
    :type connection_config: Optional[ConnectionConfig]
    """

    def __init__(
        self,
        *,
        embeddings_model: Optional[str] = None,
        connection_config: Optional[ConnectionConfig] = None,
    ) -> None:
        self.embeddings_model = embeddings_model
        self.connection_config = connection_config
