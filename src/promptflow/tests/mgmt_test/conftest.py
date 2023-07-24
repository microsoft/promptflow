import json
import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from promptflow import PFClient
from promptflow.sdk._serving.app import create_app as create_serving_app
from promptflow.sdk.entities._connection import _Connection

PROMOTFLOW_ROOT = Path(__file__) / "../../.."
RUNTIME_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/runtime")
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
MODEL_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/flows")


@pytest.fixture(scope="session")
def local_client() -> PFClient:
    return PFClient()


_connection_setup = False


@pytest.fixture
def setup_local_connection(local_client):
    global _connection_setup
    if _connection_setup:
        return
    connection_dict = json.loads(open(CONNECTION_FILE, "r").read())
    for name, _dct in connection_dict.items():
        if _dct["type"] == "BingConnection":
            continue
        local_client.connections.create_or_update(_Connection.from_execution_connection_dict(name=name, data=_dct))
    _connection_setup = True


@pytest.fixture
def flow_serving_client(mocker: MockerFixture):
    model_path = (Path(MODEL_ROOT) / "basic-with-connection").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    app = create_serving_app(environment_variables={"API_TYPE": "${azure_open_ai_connection.api_type}"})
    app.init_executor_if_not_exist()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


@pytest.fixture
def evaluation_flow_serving_client(mocker: MockerFixture):
    model_path = (Path(MODEL_ROOT) / "web_classification").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    app = create_serving_app()
    app.init_executor_if_not_exist()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()
