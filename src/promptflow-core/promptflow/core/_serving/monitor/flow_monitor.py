# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
from typing import Dict

from promptflow._utils.exception_utils import ErrorResponse
from promptflow.core._serving.constants import PF_BUILTIN_TRACE_EXPORTERS_DISABLE
from promptflow.core._serving.monitor.context_data_provider import ContextDataProvider
from promptflow.core._serving.monitor.data_collector import FlowDataCollector
from promptflow.core._serving.monitor.metrics import MetricsRecorder, ResponseType
from promptflow.core._serving.monitor.streaming_monitor import StreamingMonitor
from promptflow.core._serving.utils import get_cost_up_to_now


class FlowMonitor:
    """FlowMonitor is used to collect metrics & data for promptflow serving."""

    def __init__(
        self,
        logger,
        default_flow_name,
        data_collector: FlowDataCollector,
        context_data_provider: ContextDataProvider,
        custom_dimensions: Dict[str, str],
        metric_exporters=None,
        trace_exporters=None,
        log_exporters=None,
    ):
        self.data_collector = data_collector
        self.logger = logger
        self.context_data_provider = context_data_provider
        self.metrics_recorder = self.setup_metrics_recorder(custom_dimensions, metric_exporters)
        self.flow_name = default_flow_name
        self.setup_trace_exporters(trace_exporters)
        self.setup_log_exporters(log_exporters)

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
        # This is to support customer customize their own spanprocessor, in that case customer can disable the built-in
        # trace exporters by setting the environment variable PF_BUILTIN_TRACE_EXPORTERS_DISABLE to true.
        disable_builtin_trace_exporters = os.environ.get(PF_BUILTIN_TRACE_EXPORTERS_DISABLE, "false").lower() == "true"
        if not trace_exporters or disable_builtin_trace_exporters:
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

    def setup_log_exporters(self, log_exporters):
        if not log_exporters:
            self.logger.warning("No log exporter enabled.")
            return
        exporter_names = [n.__class__.__name__ for n in log_exporters]
        self.logger.info(f"Enable {len(log_exporters)} log exporters: {exporter_names}.")
        import logging

        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource

        resource = Resource(attributes={SERVICE_NAME: "promptflow"})
        logger_provider = LoggerProvider(resource=resource)
        set_logger_provider(logger_provider)
        for exporter in log_exporters:
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
        from promptflow._utils.logger_utils import flow_logger, logger

        self.logger.addHandler(handler)
        flow_logger.addHandler(handler)
        logger.addHandler(handler)

    def setup_streaming_monitor_if_needed(self, response_creator):
        input_data = self.context_data_provider.get_request_data()
        flow_result = self.context_data_provider.get_flow_result()
        output = flow_result.output if flow_result else {}
        streaming = self.context_data_provider.is_response_streaming()
        req_id = self.context_data_provider.get_request_id()
        flow_id = self.context_data_provider.get_flow_id() or self.flow_name
        req_start_time = self.context_data_provider.get_request_start_time()
        # set streaming callback functions if the response is streaming
        if streaming:
            streaming_monitor = StreamingMonitor(
                self.logger,
                flow_id=flow_id,
                start_time=req_start_time,
                inputs=input_data,
                outputs=output,
                req_id=req_id,
                streaming_field_name=response_creator.stream_field_name,
                metric_recorder=self.metrics_recorder,
                data_collector=self.data_collector,
            )
            response_creator._on_stream_start = streaming_monitor.on_stream_start
            response_creator._on_stream_end = streaming_monitor.on_stream_end
            response_creator._on_stream_event = streaming_monitor.on_stream_event
            self.logger.info(f"Finish stream callback setup for flow with streaming={streaming}.")
        else:
            self.logger.info("Flow does not enable streaming response.")

    def handle_error(self, ex: Exception, resp_code: int):
        if self.metrics_recorder:
            flow_id = self.context_data_provider.get_flow_id() or self.flow_name
            streaming = self.context_data_provider.is_response_streaming()
            err_code = ErrorResponse.from_exception(ex).innermost_error_code
            self.metrics_recorder.record_flow_request(flow_id, resp_code, err_code, streaming)

    def start_monitoring(self):
        pass

    def finish_monitoring(self, resp_status_code):  # noqa: E501
        flow_id = self.context_data_provider.get_flow_id() or self.flow_name
        req_start_time = self.context_data_provider.get_request_start_time()
        input_data = self.context_data_provider.get_request_data()
        flow_result = self.context_data_provider.get_flow_result()
        streaming = self.context_data_provider.is_response_streaming()
        req_id = self.context_data_provider.get_request_id()
        # collect non-streaming flow request/response data
        if self.data_collector and input_data and flow_result and flow_result.output and not streaming:
            self.data_collector.collect_flow_data(input_data, flow_result.output, req_id)

        if self.metrics_recorder:
            if flow_result:
                self.metrics_recorder.record_tracing_metrics(flow_result.run_info, flow_result.node_run_infos)
            err_code = self.context_data_provider.get_exception_code()
            err_code = err_code if err_code else ""
            self.metrics_recorder.record_flow_request(flow_id, resp_status_code, err_code, streaming)
            # streaming metrics will be recorded in the streaming callback func
            if not streaming:
                latency = get_cost_up_to_now(req_start_time)
                self.metrics_recorder.record_flow_latency(
                    flow_id, resp_status_code, streaming, ResponseType.Default.value, latency
                )
