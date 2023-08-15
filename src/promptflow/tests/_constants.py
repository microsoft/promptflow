from pathlib import Path

PROMOTFLOW_ROOT = Path(__file__).parent.parent
RUNTIME_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/runtime")
EXECUTOR_REQUESTS_ROOT = Path(
    PROMOTFLOW_ROOT / "tests/test_configs/executor_api_requests"
)
MODEL_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/e2e_samples")
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
ENV_FILE = (PROMOTFLOW_ROOT / ".env").resolve().absolute().as_posix()
