# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

AZURE_AI_SEARCH_API_VERSION = "2023-07-01-preview"


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
