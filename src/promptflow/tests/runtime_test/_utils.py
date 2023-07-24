import json
from pathlib import Path

from promptflow.runtime.runtime import load_runtime_config

from .conftest import RUNTIME_TEST_CONFIGS_ROOT


def get_config_file(file, root=RUNTIME_TEST_CONFIGS_ROOT):
    """get config file from test config root"""
    return Path(root / file).resolve().absolute()


def read_json_file(file) -> dict:
    """read file content"""
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def assert_run_completed(result):
    assert result is not None
    assert "flow_runs" in result, f"get invalid result: {result}"
    run = result["flow_runs"][0]
    error = run.get("error")
    assert run["status"] == "Completed", f"Run failed. Error: {error}"


def get_runtime_config(**kwargs):
    config = load_runtime_config(**kwargs)
    return config


def write_csv(batch_inputs, target_file):
    import pandas as pd

    df = pd.DataFrame(batch_inputs)
    df.to_csv(target_file, index=False)
