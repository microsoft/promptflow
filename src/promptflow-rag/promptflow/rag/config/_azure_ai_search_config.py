# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# General todo: need to determine which args are required or optional when parsed out into groups like this.
# General todo: move these to more permanent locations?

# Defines stuff related to the resulting created index, like the index type.

from typing import Optional
from promptflow.rag.constants._common import CONNECTION_ID_FORMAT
from ._connection_config import ConnectionConfig


class AzureAISearchConfig:
    """Config class for creating an Azure AI Search index.

    :param ai_search_index_name: The name of the Azure AI Search index.
    :type ai_search_index_name: Optional[str]
    :param ai_search_connection_id: The Azure AI Search connection Config.
    :type ai_search_connection_config: Optional[ConnectionConfig]
    :param ai_search_connection_id: The name of the Azure AI Search index.
    :type connection_id: Optional[str]
    """

    def __init__(
        self,
        *,
        ai_search_index_name: Optional[str] = None,
        ai_search_connection_config: Optional[ConnectionConfig] = None,
        connection_id: Optional[str] = None,
    ) -> None:
        self.ai_search_index_name = ai_search_index_name
        self.ai_search_connection_config = ai_search_connection_config
        self.connection_id = connection_id

    def get_connection_id(self) -> Optional[str]:
        """Get connection id from connection config or connection id"""
        import re

        if self.connection_id:
            if not re.match(CONNECTION_ID_FORMAT, self.connection_id):
                raise ValueError(
                    "Your connection id doesn't have the correct format"
                )
            return self.connection_id
        if self.ai_search_connection_config:
            return self.ai_search_connection_config.build_connection_id()
        return None
