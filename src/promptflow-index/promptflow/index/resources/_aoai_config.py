# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# General todo: need to determine which args are required or optional when parsed out into groups like this.
# General todo: move these to more permanent locations?

# Defines stuff related to the resulting created index, like the index type.

from typing import Optional

class EmbeddingsModelConfig:
    """Config class for a embedding model in AOAI.

    :param embeddings_model: The name of the Azure Cognitive Services index.
    :type embeddings_model: Optional[str]
    :param aoai_connection_id: The Azure Cognitive Services connection ID.
    :type aoai_connection_id: Optional[str]
    """

    def __init__(
        self,
        *,
        embeddings_model: Optional[str] = None,
        aoai_connection_id: Optional[str] = None,
    ) -> None:
        self.embeddings_model = embeddings_model
        self.aoai_connection_id = aoai_connection_id