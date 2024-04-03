import json
from pathlib import Path

from common import clean_data, split_document, summarize_batch_run_res
from constants import NODES_FILE_NAME, PARALLEL_RUN_STEP_FILE_NAME, SUMMARY_FILE_NAME, TEST_DATA_FILE_NAME
from mldesigner import Input, Output, command_component

conda_file = Path(__file__).parent.parent / "conda.yml"
env_image = "mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04"


@command_component(
    name="split_document_component",
    display_name="split documents",
    description="Split documents into document nodes.",
    environment=dict(
        conda_file=conda_file,
        image=env_image,
    ),
)
def split_document_component(
    documents_folder: Input(type="uri_folder"),
    chunk_size: int,
    chunk_overlap: int,
    document_node_output: Output(type="uri_folder"),
) -> str:
    """Split documents into document nodes.

    Args:
        documents_folder: The folder containing documents to be split.
        chunk_size: The size of each chunk.
        document_node_output: The output folder
        chunk_overlap: The size of chunk overlap

    Returns:
        The folder containing the split documents.
    """
    return split_document(chunk_size, chunk_overlap, documents_folder, document_node_output)


@command_component(
    name="clean_data_component",
    display_name="clean dataset",
    description="Clean test data set to remove empty lines.",
    environment=dict(
        conda_file=conda_file,
        image=env_image,
    ),
)
def clean_data_component(
    test_data_set_folder: Input(type="uri_folder"), test_data_output: Output(type="uri_folder")
) -> str:
    test_data_set_path = Path(test_data_set_folder) / PARALLEL_RUN_STEP_FILE_NAME

    with open(test_data_set_path, "r") as f:
        data = [json.loads(line) for line in f]

    test_data_output_path = test_data_output / Path(TEST_DATA_FILE_NAME)
    clean_data(data, test_data_output_path)

    return str(test_data_output_path)


@command_component(
    name="summarize_generation_details_component",
    display_name="summarize generation details",
    description="Summarize generation details.",
    environment=dict(
        conda_file=conda_file,
        image=env_image,
    ),
)
def summarize_generation_details_component(
    document_node_output: Input(type="uri_folder"),
    test_data_set_folder: Input(type="uri_folder"),
    summary_output: Output(type="uri_folder"),
) -> str:
    test_data_set_path = Path(test_data_set_folder) / PARALLEL_RUN_STEP_FILE_NAME
    document_node_output_path = Path(document_node_output)

    summary_output_path = summary_output / Path(SUMMARY_FILE_NAME)
    if document_node_output_path.is_dir():
        document_node_output_path = document_node_output_path / NODES_FILE_NAME
    summarize_batch_run_res(
        gen_details_file_path=test_data_set_path,
        document_nodes_file_path=document_node_output_path,
        output_file_path=summary_output_path,
    )

    return str(summary_output_path)
