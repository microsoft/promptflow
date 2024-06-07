# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import random
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from promptflow.parallel import processor


@pytest.fixture
def simple_flow_with_python_tool_and_aggregate(flow_dir):
    wd = flow_dir / "simple_flow_with_python_tool_and_aggregate"
    data = [{"num": random.randint(i, i + 10)} for i in range(0, 100, 10)]
    with TemporaryDirectory() as input_dir, TemporaryDirectory() as output_dir:
        args = [
            "--amlbi_pf_model",
            str(wd),
            "--input_asset_data",
            str(input_dir),
            "--output",
            output_dir,
        ]
        with patch.object(sys, "argv", sys.argv + args):
            yield wd, Path(output_dir), data


@pytest.fixture
def enable_debug():
    with TemporaryDirectory() as debug_dir, patch.object(
        sys, "argv", sys.argv + ["--amlbi_pf_debug_info", debug_dir, "--logging_level", "DEBUG"]
    ):
        yield Path(debug_dir)


@pytest.fixture
def bulk_run_processor():
    with patch.object(sys, "argv", sys.argv + ["--amlbi_pf_run_mode", processor._Mode.bulk.value]):
        yield


@pytest.fixture
def component_run_processor():
    with patch.object(sys, "argv", sys.argv + ["--amlbi_pf_run_mode", processor._Mode.component.value]):
        yield


@pytest.fixture
def enable_processors(request):
    request.getfixturevalue(request.param)
    yield
