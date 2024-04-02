# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# General todo: need to determine which args are required or optional when parsed out into groups like this.
# General todo: move these to more permanent locations?

# Defines stuff related to the resulting created index, like the index type.

from typing import Optional

class AzureAISearchConfig:
    """Config class for creating an Azure Cognitive Services index.

    :param acs_index_name: The name of the Azure Cognitive Services index.
    :type acs_index_name: Optional[str]
    :param acs_connection_id: The Azure Cognitive Services connection ID.
    :type acs_connection_id: Optional[str]
    """

    def __init__(
        self,
        *,
        acs_index_name: Optional[str] = None,
        acs_connection_id: Optional[str] = None,
    ) -> None:
        self.acs_index_name = acs_index_name
        self.acs_connection_id = acs_connection_id