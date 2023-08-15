# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
from io import TextIOWrapper

from azure.storage.blob import BlobClient


class BlobStream(TextIOWrapper):
    def __init__(self, sas_uri: str, raise_exception=False):
        self._raise_exception = raise_exception
        try:
            self._blob_client = BlobClient.from_blob_url(sas_uri)
        except Exception as ex:
            logging.exception(
                f"Failed to create blob client from sas uri. Exception: {ex}"
            )
            if raise_exception:
                raise

    def write(self, s: str):
        """Override TextIOWrapper's write method."""
        try:
            self._blob_client.upload_blob(s, blob_type="AppendBlob")
        except Exception:
            if self._raise_exception:
                raise

    def flush(self):
        """Override TextIOWrapper's flush method."""
        pass
