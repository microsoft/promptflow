# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.core._serving.monitor.metrics import ResponseType
from promptflow.core._serving.utils import get_cost_up_to_now


class StreamingMonitor:
    """StreamingMonitor is used to collect metrics & data for streaming response."""

    def __init__(
        self,
        logger,
        flow_id: str,
        start_time: float,
        inputs: dict,
        outputs: dict,
        req_id: str,
        streaming_field_name: str,
        metric_recorder,
        data_collector,
    ) -> None:
        self.logger = logger
        self.flow_id = flow_id
        self.start_time = start_time
        self.inputs = inputs
        self.outputs = outputs
        self.streaming_field_name = streaming_field_name
        self.req_id = req_id
        self.metric_recorder = metric_recorder
        self.data_collector = data_collector
        self.response_message = []

    def on_stream_start(self):
        """stream start call back function, record flow latency when first byte received."""
        self.logger.info("start streaming response...")
        if self.metric_recorder:
            duration = get_cost_up_to_now(self.start_time)
            self.metric_recorder.record_flow_latency(self.flow_id, 200, True, ResponseType.FirstByte.value, duration)

    def on_stream_end(self, streaming_resp_duration: float):
        """stream end call back function, record flow latency and streaming response data when last byte received."""
        if self.metric_recorder:
            duration = get_cost_up_to_now(self.start_time)
            self.metric_recorder.record_flow_latency(self.flow_id, 200, True, ResponseType.LastByte.value, duration)
            self.metric_recorder.record_flow_streaming_response_duration(self.flow_id, streaming_resp_duration)
        if self.data_collector:
            response_content = "".join(self.response_message)
            if self.streaming_field_name in self.outputs:
                self.outputs[self.streaming_field_name] = response_content
            self.data_collector.collect_flow_data(self.inputs, self.outputs, self.req_id)
        self.logger.info("finish streaming response.")

    def on_stream_event(self, message: str):
        """stream event call back function, record streaming response data chunk."""
        self.response_message.append(message)
