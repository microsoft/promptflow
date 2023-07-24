import os
import typing
import uuid
from pathlib import Path

import pandas as pd
import pytest
from azure.ai.ml import MLClient

from promptflow.data import load_data, load_df
from promptflow.runtime import load_runtime_config
from promptflow.runtime.data import prepare_data
from promptflow.runtime.error_codes import InvalidDataUri

from .._azure_utils import get_azure_blob_service_client, get_cred, get_or_create_data, upload_data
from .._utils import get_config_file

# TODO add more tests on:
# - url_folder
# - adls datastore


@pytest.mark.unittest
def test_load_blob_url():
    # ensure data exists in remote storage
    storage_account = "promptflowint3254517137"
    container_name = "testdata1"
    local_file = get_config_file("requests/qa_with_bing.csv")
    cred = get_cred()
    client = get_azure_blob_service_client(
        storage_account_name=storage_account, container_name=container_name, credential=cred
    )
    upload_data(local_file, client)

    # test we can load back data
    uris = [
        f"wasbs://{container_name}@{storage_account}.blob.core.windows.net/qa_with_bing.csv",
    ]

    for uri in uris:
        destination = str(Path(local_file).resolve().parent / "downloaded")
        target_file = prepare_data(uri, destination, credential=cred)
        df = load_data(target_file)
        assert len(df) == 1

    uri = f"https://{storage_account}.blob.core.windows.net/{container_name}/qa_with_bing.csv"
    destination = "tmp"
    target_file = prepare_data(uri, destination, credential=cred)
    df = load_data(target_file)
    # blob storage will return an file with error message which has more lines
    assert len(df) != 1


@pytest.mark.unittest
def test_load_aml_url(ml_client: MLClient):
    data_name = "qa_with_bing_test"
    data_file = get_config_file("requests/qa_with_bing.csv")
    data = get_or_create_data(ml_client, data_name, data_file)
    assert data is not None
    assert data.path
    sub = ml_client.subscription_id
    rg = ml_client.resource_group_name
    ws = ml_client.workspace_name
    ds = "workspaceblobstore"
    path = data.path.split("paths/")[-1]
    version = data.version

    armid_prefix = (
        f"azureml:/subscriptions/{sub}/resourceGroups/{rg}/"
        + f"providers/Microsoft.MachineLearningServices/workspaces/{ws}"
    )
    uris = [
        data.path,
        f"azureml://datastores/{ds}/paths/{path}",
        f"azureml://subscriptions/{sub}/resourcegroups/{rg}/workspaces/{ws}/data/{data_name}/versions/{version}",
        f"azureml://subscriptions/{sub}/resourcegroups/{rg}/workspaces/{ws}/data/{data_name}/labels/latest",
        f"{armid_prefix}/data/{data_name}/versions/{version}",
        f"{armid_prefix}/{str(uuid.uuid4())}/{data_name}/versions/{version}",  # got this format from server
        f"azureml:{data_name}:{data.version}",
        f"azureml:{data_name}@latest",
    ]
    runtime_config = load_runtime_config()
    runtime_config.deployment.subscription_id = ml_client.subscription_id
    runtime_config.deployment.resource_group = ml_client.resource_group_name
    runtime_config.deployment.workspace_name = ml_client.workspace_name

    cred = get_cred()
    for idx, uri in enumerate(uris):
        destination = f"tmp/{idx}"
        target_file = f"{destination}/qa_with_bing.csv"
        if Path(target_file).exists():
            os.remove(target_file)
        prepare_data(uri, destination, credential=cred, runtime_config=runtime_config)
        df = load_data(target_file)
        assert len(df) == 1


@pytest.mark.unittest
def test_load_glob_like_aml_url(ml_client: MLClient):
    sub = ml_client.subscription_id
    rg = ml_client.resource_group_name
    ws = ml_client.workspace_name
    ds = "workspaceblobstore"
    # pre-created v1 tabular dataset
    path = "test/v1tabulardataset/"
    uri = f"azureml://subscriptions/{sub}/resourcegroups/{rg}/workspaces/{ws}/datastores/{ds}/paths/{path}**/"

    runtime_config = load_runtime_config()
    runtime_config.deployment.subscription_id = ml_client.subscription_id
    runtime_config.deployment.resource_group = ml_client.resource_group_name
    runtime_config.deployment.workspace_name = ml_client.workspace_name
    cred = get_cred()
    # prepare, load and assert
    destination = "tmp/v1-tabular-dataset"
    target_file = f"{destination}/batch_inputs.csv"
    if Path(target_file).exists():
        os.remove(target_file)
    prepare_data(uri, destination, credential=cred, runtime_config=load_runtime_config)
    df = load_data(target_file)
    assert len(df) == 2


@pytest.mark.unittest
def test_load_public_url():
    destination = "tmp"
    target_file = "tmp/Titanic.csv"

    uris = ["https://dprepdata.blob.core.windows.net/demo/Titanic.csv"]

    for uri in uris:
        if Path(target_file).exists():
            os.remove(target_file)
        prepare_data(uri, destination)
        df = load_data(target_file)
        assert len(df) > 1

    invalid_uris = ["https://unexist/demo/un_exist.csv"]
    for uri in invalid_uris:
        with pytest.raises(Exception) as ex:
            prepare_data(uri, destination)
        assert str(ex) is not None


@pytest.mark.unittest
def test_load_local_data():
    destination = "tmp"
    uris = [
        get_config_file("data/colors/colors.csv"),
        get_config_file("data/colors"),
    ]

    for uri in uris:
        target_file = prepare_data(uri, destination)
        df = load_data(target_file)
        assert len(df) > 1


@pytest.mark.unittest
def test_load_invalid_data_uri():
    destination = "tmp"
    uris = ["invalid://dprepdata.blob.core.windows.net/demo/Titanic.csv"]

    for uri in uris:
        with pytest.raises(InvalidDataUri) as ex:
            prepare_data(uri, destination)
        assert "Invalid data uri" in ex.value.message


def _assert_colors_data(data: typing.List[dict]):
    assert len(data) == 3
    # check data content to avoid reading incorrectly, sort first to assert with deterministic order
    data.sort(key=lambda x: x["id"])
    assert data == [
        {"id": 1, "name": "Red"},
        {"id": 2, "name": "Yellow"},
        {"id": 3, "name": "Blue"},
    ]


@pytest.mark.unittest
def test_load_different_format_data():
    supported_formats = ["csv", "json", "jsonl", "parquet", "tsv"]
    for supported_format in supported_formats:
        f = get_config_file(f"data/colors.{supported_format}")
        data = load_data(f)
        _assert_colors_data(data)


@pytest.mark.unittest
def test_load_df():
    supported_formats = ["csv", "json", "jsonl", "parquet", "tsv"]
    for supported_format in supported_formats:
        f = get_config_file(f"data/colors.{supported_format}")
        data = load_df(f)
        assert isinstance(data, type(pd.DataFrame()))
        assert data.shape == (3, 2)


@pytest.mark.unittest
def test_load_nested_data():
    # test cases from some real use cases
    files = [
        get_config_file("data/colors"),
        get_config_file("data/colors_multiple"),
        get_config_file("data/colors_nested_0"),  # valid data at depth 0
        get_config_file("data/colors_nested_1"),  # valid data at depth 1 (empty data at depth 0)
        get_config_file("data/colors_nested_2"),  # valid data at depth 2 (distributed at different folders)
    ]

    for f in files:
        data = load_data(f)
        _assert_colors_data(data)

    # empty folder
    empty_folder = get_config_file("data/colors_empty")
    data = load_data(empty_folder)
    assert len(data) == 0


@pytest.mark.unittest
def test_load_data_with_rows_limit():
    # load from file
    file = get_config_file("data/colors.jsonl")
    data = load_data(file)
    assert len(data) == 3
    data = load_data(file, max_rows_count=1)
    assert len(data) == 1

    # load from directory
    from promptflow.data.data import MAX_ROWS_COUNT

    colors_big = get_config_file("data/colors_big")
    data = load_data(colors_big)
    assert len(data) == MAX_ROWS_COUNT
    data = load_data(colors_big, max_rows_count=10)
    assert len(data) == 10


@pytest.mark.unittest
def test_load_data_ignore_not_supported():
    file = get_config_file("data/colors_ignore")
    data = load_data(file)
    _assert_colors_data(data)
