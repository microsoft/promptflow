# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

AZURE_AI_SEARCH_API_VERSION = "2023-07-01-preview"
OPEN_AI_PROTOCOL_TEMPLATE = "azure_open_ai://deployment/{}/model/{}"
CONNECTION_ID_TEMPLATE = "/subscriptions/{}/resourceGroups/{}/providers/Microsoft.MachineLearningServices/workspaces/{}/connections/{}"  # noqa: E501
CONNECTION_ID_FORMAT = CONNECTION_ID_TEMPLATE.format(".*", ".*", ".*", ".*")
STORAGE_URI_TO_MLINDEX_PATH_TEMPLATE = "azureml://subscriptions/{}/resourcegroups/{}/workspaces/{}/datastores/{}/paths/{}"  # noqa: E501
STORAGE_URI_TO_MLINDEX_PATH_FORMAT = STORAGE_URI_TO_MLINDEX_PATH_TEMPLATE.format(".*", ".*", ".*", ".*", ".*")


class IndexInputType(object):
    """An enumeration of values for the types of input data for an index."""
    GIT = "git"
    LOCAL = "local"
    AOAI = "aoai"
    """Azure OpenAI input data type."""


class IndexType(object):
    """An enumeration of values for the types of an index."""
    ACS = "acs"
    FAISS = "faiss"
