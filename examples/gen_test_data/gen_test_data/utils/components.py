import json
import os
from pathlib import Path

from mldesigner import Input, Output, command_component
from common import split_document, clean_data_and_save
from constants import ENVIRONMENT_DICT_FIXED_VERSION


@command_component(
    name="document_split",
    version="1.0.4",
    display_name="split documents",
    description="Split documents into chunks.",
    environment=ENVIRONMENT_DICT_FIXED_VERSION,
)
def document_split(
        documents_folder: Input(type="uri_folder"), chunk_size: int, document_node_output: Output(type="uri_folder")
) -> str:
    """Split documents into chunks.

    Args:
        documents_folder: The folder containing documents to be split.
        chunk_size: The size of each chunk.
        document_node_output: The output folder

    Returns:
        The folder containing the split documents.
    """
    return split_document(chunk_size, documents_folder, document_node_output)


@command_component(
    name="clean_test_data_set",
    version="1.0.4",
    display_name="clean dataset",
    description="Clean test data set to remove empty lines.",
    environment=ENVIRONMENT_DICT_FIXED_VERSION,
)
def clean_test_data_set(
        test_data_set_folder: Input(type="uri_folder"), test_data_output: Output(type="uri_folder")
) -> str:
    test_data_set_path = Path(test_data_set_folder) / "parallel_run_step.jsonl"

    with open(test_data_set_path, "r") as f:
        data = [json.loads(line) for line in f]

    test_data_output_path = os.path.join(test_data_output, "test_data_set.jsonl")
    clean_data_and_save(data, test_data_output_path)

    return test_data_output_path
