# flake8: noqa
import os

from promptflow import tool, flow

@tool
def create_data_from_uri_file(uri: str = "", data_asset_name: str = ""):
    # read data from uri
    data = None
    
    from promptflow.runtime.utils._token_utils import get_default_credential
    credential = get_default_credential(diagnostic=True)

    if uri:
        mltable_dir = f"{os.getcwd()}/{data_asset_name}"
        # avoid depend on mltable
        # paths = [{"file": uri}]
        # tbl = mltable.from_delimited_files(paths)
        # tbl.save(mltable_dir)

        # manual write mltable file
        from pathlib import Path
        mltable_file = Path(mltable_dir)/"MLTable"
        mltable_file.parent.mkdir(parents=True, exist_ok=True)
        mltable_file_pattern = """paths:
- file: FILE_PATH
transformations:
- read_delimited:
    delimiter: ','
    empty_as_string: false
    encoding: utf8
    header: all_files_same_headers
    include_path_column: false
    infer_column_types: true
    partition_size: 20971520
    path_column: Path
    support_multi_line: false
type: mltable
"""
        content = mltable_file_pattern.replace("FILE_PATH", uri)
        with open(mltable_file, "w", encoding="utf-8") as f:
            f.write(content)

        # import here to avoid circular import
        from promptflow.runtime.data import prepare_data
        from promptflow.data import load_data
        destination = 'data'
        local_file = prepare_data(uri, destination=destination, credential=credential)
        data = load_data(local_file)

        # this call requires user identity, get strange 409 error now
        # df = tbl.to_pandas_dataframe()
        # data = df.to_json()

    # create data asset
    asset_id = None
    if data_asset_name:
        from azure.ai.ml import MLClient
        from azure.ai.ml.entities import Data
        from azure.ai.ml.constants import AssetTypes

        sub_id = os.environ.get("SUBSCRIPTION_ID")
        resource_group = os.environ.get("RESOURCE_GROUP")
        workspace_name = os.environ.get("WORKSPACE_NAME")
        ml_client = MLClient(credential=credential, 
                             subscription_id=sub_id, 
                             resource_group_name=resource_group, 
                             workspace_name=workspace_name)

        my_data = Data(
            path=mltable_dir,
            type=AssetTypes.MLTABLE,
            description="test mltable data",
            name=data_asset_name,
        )
        my_data = ml_client.data.create_or_update(my_data)
        asset_id = my_data.id
    
    return {
        "data": data,
        "asset_id": asset_id
    }

@flow()
def data_input_flow(uri: str = "", data_asset_name: str = ""):
    create_data = create_data_from_uri_file(uri=uri, data_asset_name=data_asset_name)
    return create_data

# python -m promptflow.scripts.dump_flow --path .\flow.py --mode payload --target .
if __name__ == "__main__":
    os.environ["SUBSCRIPTION_ID"] = "96aede12-2f73-41cb-b983-6d11a904839b"
    os.environ["RESOURCE_GROUP"] = "promptflow"
    os.environ["WORKSPACE_NAME"] = "promptflow-eastus"

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # data_input_flow("./data/input1.csv", "test_data_01")
    # uri = "https://promptflowint3254517137.blob.core.windows.net/testdata/batch_input1.csv"
    uri = 'wasbs://testdata@promptfloweast4063704120.blob.core.windows.net/batch_input1.csv'
    result = data_input_flow(uri, "test_data_01")
    print(result)