# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


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
