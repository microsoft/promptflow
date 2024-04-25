import json
import pytest
from pathlib import Path

from promptflow.rag.resources import EmbeddingsModelConfig, ConnectionConfig
PROMPTFLOW_ROOT = Path(__file__) / "../../../.."
CONNECTION_FILE = (PROMPTFLOW_ROOT / "src/promptflow-rag/connections.json").resolve().absolute().as_posix()
# RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "promptflow-recording/recordings/local").resolve()

@pytest.fixture
def embeddings_model_config() -> dict:
    model_config_name = "azure_openai_model_config"
    model_connection_name = "azure_openai_connection_config"

    with open(
        file=CONNECTION_FILE,
        mode="r",
    ) as f:
        dev_connections = json.load(f)

    if model_config_name not in dev_connections:
        raise ValueError(f"Connection '{model_config_name}' not found in dev connections.")
    
    if model_connection_name not in dev_connections:
        raise ValueError(f"Connection '{model_connection_name}' not found in dev connections.")

    model_connection = ConnectionConfig(**dev_connections[model_connection_name]["value"])
    model_config = EmbeddingsModelConfig(**dev_connections[model_config_name]["value"], connection_config=model_connection)

    EmbeddingsModelConfig.__repr__ = lambda self: "<sensitive data redacted>"

    return model_config

@pytest.fixture
def index_connection_config() -> dict:
    index_connection_name  = "azure_ai_search_connection_config"

    with open(
        file=CONNECTION_FILE,
        mode="r",
    ) as f:
        dev_connections = json.load(f)

    if index_connection_name not in dev_connections:
        raise ValueError(f"Connection '{index_connection_name}' not found in dev connections.")

    model_connection = ConnectionConfig(**dev_connections[index_connection_name]["value"])

    ConnectionConfig.__repr__ = lambda self: "<sensitive data redacted>"

    return model_connection