# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

try:
    from azure.ai.ml._restclient.v2022_10_01_preview.models import DatastoreType
except ImportError:
    from azure.ai.ml._restclient.v2022_10_01.models import DatastoreType

__all__ = ["DatastoreType"]
