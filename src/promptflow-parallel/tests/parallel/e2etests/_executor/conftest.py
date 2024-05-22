# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

import pytest

from promptflow.parallel._config.model import ParallelRunConfig
from promptflow.parallel._executor.base import ParallelRunExecutor
from promptflow.parallel._executor.bulk_executor import BulkRunExecutor
from promptflow.parallel._executor.component_executor import ComponentRunExecutor


@pytest.fixture
def hello_world_flow_config(flow_dir):
    wd = flow_dir / "simple_hello_world"
    with TemporaryDirectory() as input_dir, TemporaryDirectory() as output_dir:
        yield wd, ParallelRunConfig(
            pf_model_dir=wd,
            input_dir=Path(input_dir),
            output_dir=Path(output_dir),
        )


@pytest.fixture
def bulk_run_executor():
    def gen(working_dir: Path, config: ParallelRunConfig) -> BulkRunExecutor:
        return BulkRunExecutor(working_dir, config)

    return gen


@pytest.fixture
def component_run_executor():
    def gen(working_dir: Path, config: ParallelRunConfig) -> ComponentRunExecutor:
        return ComponentRunExecutor(working_dir, config)

    return gen


@pytest.fixture
def executor_gen(request) -> Callable[[Path, ParallelRunConfig], ParallelRunExecutor]:
    def wrapper(working_dir: Path, config: ParallelRunConfig) -> ParallelRunExecutor:
        gen = request.getfixturevalue(request.param)
        executor = gen(working_dir, config)
        executor.init()
        return executor

    return wrapper
