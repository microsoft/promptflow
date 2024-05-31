# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from unittest.mock import Mock, patch

import pytest

from promptflow.parallel import create_processor
from promptflow.parallel._metrics.sender import MetricsSender


def split_mini_batch(data, batch_size):
    for batch_index, r in enumerate(range(0, len(data), batch_size)):
        yield data[r : r + batch_size], Mock(minibatch_index=batch_index, global_row_index_lower_bound=r)


def write_output(output_dir, mini_batch_index, result: str):
    with open(output_dir / f"temp_{mini_batch_index}_x_parallel_run_step.jsonl", "a") as f:
        f.write(result)
        f.write("\n")


@pytest.mark.e2etest
@pytest.mark.parametrize("enable_processors", ["bulk_run_processor", "component_run_processor"], indirect=True)
def test_with_simple_flow_with_python_tool_and_aggregate(
    simple_flow_with_python_tool_and_aggregate, enable_processors, enable_debug
):
    wd, output_dir, data = simple_flow_with_python_tool_and_aggregate
    processor = create_processor(wd)
    processor.init()

    excepted_results = {int(d["num"] / 2) for d in data}
    for mini_batch, context in split_mini_batch(data, 3):
        results = processor.process(mini_batch, context)
        assert len(results) == len(mini_batch)

        for result_str in results:
            write_output(output_dir, context.minibatch_index, result_str)
            result = json.loads(result_str)
            output = result["output"]

            assert "line_number" in output
            assert "aggregation_inputs" in result
            assert "inputs" in result

            assert int(output["content"]) in excepted_results

    with patch.object(MetricsSender, "send"):
        processor.finalize()
