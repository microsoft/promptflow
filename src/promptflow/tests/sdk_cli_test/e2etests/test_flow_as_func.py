# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest

from promptflow import load_flow

FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
DATAS_DIR = "./tests/test_configs/datas"


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection")
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowAsFunc:
    def test_flow_as_a_func(self):
        f = load_flow(f"{FLOWS_DIR}/print_env_var")
        result = f(key="unknown")
        assert result["output"] is None

    def test_flow_as_a_func_with_connection_overwrite(self):
        from promptflow._sdk._errors import ConnectionNotFoundError

        flow_path = Path(f"{FLOWS_DIR}/web_classification").absolute()
        f = load_flow(
            flow_path,
            connections={"classify_with_llm": {"connection": "not_exist"}},
        )
        with pytest.raises(ConnectionNotFoundError) as e:
            f(url="https://www.youtube.com/watch?v=o5ZQyXaAv1g")
        assert "Connection 'not_exist' required for flow" in str(e.value)

    def test_flow_as_a_func_with_variant(self):
        flow_path = Path(f"{FLOWS_DIR}/web_classification").absolute()
        f = load_flow(
            flow_path,
            variant="${summarize_text_content.variant_0}",
        )

        f(url="https://www.youtube.com/watch?v=o5ZQyXaAv1g")
