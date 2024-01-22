from pathlib import Path

PROMOTFLOW_ROOT = Path(__file__).parent.parent
RUNTIME_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/runtime")
EXECUTOR_REQUESTS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/executor_api_requests")
MODEL_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/e2e_samples")
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
ENV_FILE = (PROMOTFLOW_ROOT / ".env").resolve().absolute().as_posix()

# below constants are used for pfazure and global config tests
DEFAULT_SUBSCRIPTION_ID = "96aede12-2f73-41cb-b983-6d11a904839b"
DEFAULT_RESOURCE_GROUP_NAME = "promptflow"
DEFAULT_WORKSPACE_NAME = "promptflow-eastus2euap"
DEFAULT_RUNTIME_NAME = "test-runtime-ci"
DEFAULT_REGISTRY_NAME = "promptflow-preview"
