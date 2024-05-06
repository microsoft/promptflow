# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Optional


class IndexConfig:
    """Convenience class that contains all config values that for index creation that are
    NOT specific to the index source data or the created index type. Meant for internal use only
    to simplify function headers. The user-entry point is a function that
    should still contain all the fields in this class as individual function parameters.

    Params omitted for brevity and to avoid maintaining duplicate docs. See index creation function
    for actual parameter descriptions.
    """

    def __init__(
        self,
        *,
        output_index_name: str,
        vector_store: str,
        data_source_url: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        input_glob: Optional[str] = None,
        max_sample_files: Optional[int] = None,
        chunk_prepend_summary: Optional[bool] = None,
        document_path_replacement_regex: Optional[str] = None,
        embeddings_container: Optional[str] = None,
        embeddings_model: str,
        aoai_connection_id: str,
        _dry_run: bool = False
    ):
        self.output_index_name = output_index_name
        self.vector_store = vector_store
        self.data_source_url = data_source_url
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.input_glob = input_glob
        self.max_sample_files = max_sample_files
        self.chunk_prepend_summary = chunk_prepend_summary
        self.document_path_replacement_regex = document_path_replacement_regex
        self.embeddings_container = embeddings_container
        self.embeddings_model = embeddings_model
        self.aoai_connection_id = aoai_connection_id
        self._dry_run = _dry_run
