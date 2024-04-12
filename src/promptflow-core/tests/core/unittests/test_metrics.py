# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
from promptflow.core._serving.monitor.metrics import MetricsRecorder
from logging import logger
from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from datetime import datetime

metrics_enabled = True

@pytest.mark.unittest
class TestMetrics:
    @pytest.mark.parametrize(
        "metrics_recorder, flow_run, node_run",
        [
            (
                MetricsRecorder(logger),
                FlowRunInfo(
                    run_id="qrstuv",
                    status=Status.Completed,
                    error=None,
                    inputs={"input": "input"},
                    output="output",
                    metrics=None,
                    request=None,
                    system_metrics=None,
                ),
                RunInfo(
                    node="test",
                    flow_run_id="a1b2c3",
                    status=Status.Completed,
                    inputs={"question": "What is the meaning of life?", "chat_history": []},
                    output={"answer": "Baseball."},
                    metrics=None,
                    error=None,
                    parent_run_id=None,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                ),
            )
        ],
    )
    def test_metrics_recorder(self, metrics_recorder, flow_run, node_run):
        try:
            metrics_recorder.record_tracing_metrics(flow_run, node_run)
        except Exception:
            pytest.fail("record_tracing_metrics raised an exception")
