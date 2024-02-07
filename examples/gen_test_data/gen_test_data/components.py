import json
from pathlib import Path

from common import clean_data, split_document
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
    documents_folder: Input(type="uri_folder"), chunk_size: int, chunk_overlap: int,
        document_node_output: Output(type="uri_folder")
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
    test_data_set_path = Path(test_data_set_folder) / "parallel_run_step.jsonl"

    with open(test_data_set_path, "r") as f:
        data = [json.loads(line) for line in f]

    test_data_output_path = test_data_output / Path("test_data_set.jsonl")
    clean_data(data, test_data_output_path)

    return str(test_data_output_path)
