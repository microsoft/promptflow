import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow.runtime import PromptFlowRuntime
from promptflow.runtime._cli.prt import encode_connections
from promptflow.runtime.constants import PROMPTFLOW_ENCODED_CONNECTIONS, PROMPTFLOW_PROJECT_PATH
from promptflow.runtime.serving.app import PromptflowServingApp
from promptflow.runtime.serving.app import create_app as create_serving_app

PROMOTFLOW_ROOT = Path(__file__) / "../../.."
RUNTIME_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/runtime")
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
MODEL_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/e2e_samples")


@pytest.fixture
def use_secrets_config_file(mocker: MockerFixture):
    mocker.patch.dict(os.environ, {PROMPTFLOW_CONNECTIONS: CONNECTION_FILE})


@pytest.fixture
def serving_app_legacy(mocker: MockerFixture) -> PromptflowServingApp:
    PromptFlowRuntime._instance = None  # Clear the _instance as we have enterprise test
    model_path = (Path(MODEL_ROOT) / "qa_with_bing").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {PROMPTFLOW_PROJECT_PATH: model_path})
    mocker.patch.dict(os.environ, {PROMPTFLOW_ENCODED_CONNECTIONS: encode_connections(CONNECTION_FILE)})
    app = create_serving_app()
    app.init_executor_if_not_exist()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    yield app


@pytest.fixture
def serving_client_legacy(serving_app_legacy, mocker: MockerFixture):
    model_path = (Path(MODEL_ROOT) / "qa_with_bing").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {PROMPTFLOW_PROJECT_PATH: model_path})
    mocker.patch.dict(os.environ, {PROMPTFLOW_ENCODED_CONNECTIONS: encode_connections(CONNECTION_FILE)})
    return serving_app_legacy.test_client()


@pytest.fixture
def serving_client(mocker: MockerFixture):
    model_path = (Path(MODEL_ROOT) / "script_with_import").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {PROMPTFLOW_PROJECT_PATH: model_path})
    mocker.patch.dict(os.environ, {PROMPTFLOW_ENCODED_CONNECTIONS: encode_connections(CONNECTION_FILE)})
    app = create_serving_app()
    app.init_executor_if_not_exist()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


@pytest.fixture
def serving_client_multiple_inputs(mocker: MockerFixture):
    model_path = (Path(MODEL_ROOT) / "multiple_inputs").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {PROMPTFLOW_PROJECT_PATH: model_path})
    mocker.patch.dict(os.environ, {PROMPTFLOW_ENCODED_CONNECTIONS: encode_connections(CONNECTION_FILE)})
    app = create_serving_app()
    app.init_executor_if_not_exist()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


def create_client_by_model(model_name: str, mocker: MockerFixture):
    model_path = (Path(MODEL_ROOT) / model_name).resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {PROMPTFLOW_PROJECT_PATH: model_path})
    mocker.patch.dict(os.environ, {PROMPTFLOW_ENCODED_CONNECTIONS: encode_connections(CONNECTION_FILE)})
    app = create_serving_app()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


@pytest.fixture
def serving_client_llm_chat(mocker: MockerFixture):
    return create_client_by_model("llm_chat", mocker)


@pytest.fixture
def serving_client_llm_completion(mocker: MockerFixture):
    return create_client_by_model("llm_tools", mocker)


@pytest.fixture
def serving_client_python_stream_tools(mocker: MockerFixture):
    return create_client_by_model("python_stream_tools", mocker)
