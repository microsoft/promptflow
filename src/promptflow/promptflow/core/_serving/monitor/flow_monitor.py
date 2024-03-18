# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import time
from typing import Dict

from flask import g, request

from promptflow._utils.exception_utils import ErrorResponse
from promptflow.core._serving.flow_result import FlowResult
from promptflow.core._serving.monitor.data_collector import FlowDataCollector
from promptflow.core._serving.monitor.metrics import MetricsRecorder, ResponseType
from promptflow.core._serving.monitor.streaming_monitor import StreamingMonitor
from promptflow.core._serving.utils import get_cost_up_to_now, streaming_response_required


class FlowMonitor:
    """FlowMonitor is used to collect metrics & data for promptflow serving."""

    def __init__(
        self,
        logger,
        default_flow_name,
        data_collector: FlowDataCollector,
        custom_dimensions: Dict[str, str],
        metric_exporters=None,
        trace_exporters=None,
    ):
        self.data_collector = data_collector
        self.logger = logger
        self.metrics_recorder = self.setup_metrics_recorder(custom_dimensions, metric_exporters)
        self.flow_name = default_flow_name
        self.setup_trace_exporters(trace_exporters)

    def setup_metrics_recorder(self, custom_dimensions, metric_exporters):
        if metric_exporters:
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

            exporter_names = [n.__class__.__name__ for n in metric_exporters]
            self.logger.info(f"Enable {len(metric_exporters)} metric exporters: {exporter_names}.")
            readers = []
            for exporter in metric_exporters:
                reader = PeriodicExportingMetricReader(exporter=exporter, export_interval_millis=60000)
                readers.append(reader)
            return MetricsRecorder(self.logger, readers=readers, common_dimensions=custom_dimensions)
        else:
            self.logger.warning("No metric exporter enabled.")
        return None

    def setup_trace_exporters(self, trace_exporters):
        if not trace_exporters:
            self.logger.warning("No trace exporter enabled.")
            return
        try:
            exporter_names = [n.__class__.__name__ for n in trace_exporters]
            self.logger.info(f"Enable {len(trace_exporters)} trace exporters: {exporter_names}.")
            from opentelemetry import trace
            from opentelemetry.sdk.resources import SERVICE_NAME, Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource(
                attributes={
                    SERVICE_NAME: "promptflow",
                }
            )
            trace.set_tracer_provider(TracerProvider(resource=resource))
            provider = trace.get_tracer_provider()
            for exporter in trace_exporters:
                provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception as e:
            self.logger.error(f"Setup trace exporters failed: {e}")

    def setup_streaming_monitor_if_needed(self, response_creator, data, output):
        g.streaming = response_creator.has_stream_field and response_creator.text_stream_specified_explicitly
        # set streaming callback functions if the response is streaming
        if g.streaming:
            streaming_monitor = StreamingMonitor(
                self.logger,
                flow_id=g.get("flow_id", self.flow_name),
                start_time=g.start_time,
                inputs=data,
                outputs=output,
                req_id=g.get("req_id", None),
                streaming_field_name=response_creator.stream_field_name,
                metric_recorder=self.metrics_recorder,
                data_collector=self.data_collector,
            )
            response_creator._on_stream_start = streaming_monitor.on_stream_start
            response_creator._on_stream_end = streaming_monitor.on_stream_end
            response_creator._on_stream_event = streaming_monitor.on_stream_event
            self.logger.info(f"Finish stream callback setup for flow with streaming={g.streaming}.")
        else:
            self.logger.info("Flow does not enable streaming response.")

    def handle_error(self, ex: Exception, resp_code: int):
        if self.metrics_recorder:
            flow_id = g.get("flow_id", self.flow_name)
            err_code = ErrorResponse.from_exception(ex).innermost_error_code
            streaming = g.get("streaming", False)
            self.metrics_recorder.record_flow_request(flow_id, resp_code, err_code, streaming)

    def start_monitoring(self):
        g.start_time = time.time()
        g.streaming = streaming_response_required()
        # if both request_id and client_request_id are provided, each will respect their own value.
        # if either one is provided, the provided one will be used for both request_id and client_request_id.
        # in aml deployment, request_id is provided by aml, user can only customize client_request_id.
        # in non-aml deployment, user can customize both request_id and client_request_id.
        g.req_id = request.headers.get("x-request-id", None)
        g.client_req_id = request.headers.get("x-ms-client-request-id", g.req_id)
        g.req_id = g.req_id or g.client_req_id
        self.logger.info(f"Start monitoring new request, request_id: {g.req_id}, client_request_id: {g.client_req_id}")

    def finish_monitoring(self, resp_status_code):
        data = g.get("data", None)
        flow_result: FlowResult = g.get("flow_result", None)
        req_id = g.get("req_id", None)
        client_req_id = g.get("client_req_id", req_id)
        flow_id = g.get("flow_id", self.flow_name)
        # collect non-streaming flow request/response data
        if self.data_collector and data and flow_result and flow_result.output and not g.streaming:
            self.data_collector.collect_flow_data(data, flow_result.output, req_id)

        if self.metrics_recorder:
            if flow_result:
                self.metrics_recorder.record_tracing_metrics(flow_result.run_info, flow_result.node_run_infos)
            err_code = g.get("err_code", "None")
            self.metrics_recorder.record_flow_request(flow_id, resp_status_code, err_code, g.streaming)
            # streaming metrics will be recorded in the streaming callback func
            if not g.streaming:
                latency = get_cost_up_to_now(g.start_time)
                self.metrics_recorder.record_flow_latency(
                    flow_id, resp_status_code, g.streaming, ResponseType.Default.value, latency
                )

        self.logger.info(f"Finish monitoring request, request_id: {req_id}, client_request_id: {client_req_id}.")
