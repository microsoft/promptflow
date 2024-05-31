# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow.parallel._model import Row


@pytest.mark.e2etest
@pytest.mark.parametrize("executor_gen", ["bulk_run_executor", "component_run_executor"], indirect=True)
def test_with_simple_hello_world(hello_world_flow_config, executor_gen):
    wd, config = hello_world_flow_config
    executor = executor_gen(wd, config)
    result = executor.execute(Row.from_dict({"name": "test"}, 0))
    # src/promptflow/tests/test_configs/flows/simple_hello_world/hello_world.py
    assert result.output.output["result"] == "Hello World test!"
