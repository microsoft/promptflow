# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import platform
from datetime import datetime

import pytest
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from promptflow.core._serving.extension.extension_type import ExtensionType
from promptflow.core._serving.extension.otel_exporter_provider_factory import OTelExporterProviderFactory
from promptflow.core._serving.monitor.metrics import MetricsRecorder
from promptflow.core._utils import LoggerFactory


@pytest.mark.unittest
class TestMetrics:
    @pytest.mark.parametrize(
        "flow_run, node_run",
        [
            (
                FlowRunInfo(
                    run_id="run_id",
                    status=Status.Completed,
                    error=None,
                    inputs={"input": "input"},
                    output="output",
                    metrics=None,
                    request=None,
                    system_metrics=None,
                    parent_run_id="parent_run_id",
                    root_run_id="root_run_id",
                    source_run_id="source_run_id",
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    flow_id="test_flow",
                ),
                RunInfo(
                    node="test",
                    flow_run_id="flow_run_id",
                    run_id="run_id",
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
    def test_metrics_recorder(self, caplog, flow_run, node_run):
        logger = LoggerFactory.get_logger("test_metrics_recorder")
        logger.propagate = True

        caplog.set_level("WARNING")
        metric_exporters = OTelExporterProviderFactory.get_metrics_exporters(
            LoggerFactory.get_logger(__name__), ExtensionType.DEFAULT
        )
        readers = []
        for exporter in metric_exporters:
            reader = PeriodicExportingMetricReader(exporter=exporter, export_interval_millis=60000)
            readers.append(reader)
        metrics_recorder = MetricsRecorder(
            logger,
            readers=readers,
            common_dimensions={
                "python_version": platform.python_version(),
                "installation_id": "test_installation_id",
            },
        )
        metrics_recorder.record_tracing_metrics(flow_run, {"run1": node_run})
        assert "failed to record metrics:" not in caplog.text
