"""This file implements OTel preview Events API according to the document:
https://opentelemetry.io/docs/specs/otel/logs/event-api/
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

import httpx
from opentelemetry.attributes import BoundedAttributes
from opentelemetry.sdk.trace import Event as TraceEvent
from opentelemetry.sdk.trace import ReadableSpan, Span
from opentelemetry.sdk.util import ns_to_iso_str
from opentelemetry.trace import format_span_id, format_trace_id
from opentelemetry.util import types


class Event(TraceEvent):
    def __init__(
        self,
        name: str,
        trace_id: str,
        span_id: str,
        attributes: types.Attributes = None,
        timestamp: Optional[int] = None,
        index: Optional[int] = None,  # The index of the event in the span
    ) -> None:
        super().__init__(name, attributes=attributes, timestamp=timestamp)
        self.trace_id = trace_id
        self.span_id = span_id
        self.index = index

    def to_json(self) -> Dict[str, Any]:
        #  Copied from opentelemetry.sdk.trace.ReadableSpan._format_events
        event_json = {
            "name": self.name,
            "timestamp": ns_to_iso_str(self.timestamp),
            "attributes": ReadableSpan._format_attributes(self.attributes),  # pylint: disable=protected-access
        }
        if self.trace_id is not None:
            event_json["trace_id"] = self.trace_id
        if self.span_id is not None:
            event_json["span_id"] = self.span_id
        if self.index is not None:
            event_json["index"] = self.index
        return event_json


class EventLogger:
    def emit(
        self,
        event: Event,
    ):
        pass


class MultiDestinationEventLogger(EventLogger):
    def __init__(self, *event_loggers: EventLogger):
        self.event_loggers = list(event_loggers)

    def emit(
        self,
        event: Event,
    ):
        for event_logger in self.event_loggers:
            event_logger.emit(event)

    def add_event_logger(self, event_logger: EventLogger):
        if event_logger not in self.event_loggers:
            self.event_loggers.append(event_logger)


class EventLoggerProvider:
    def __init__(self):
        self._logger = MultiDestinationEventLogger()

    def get_event_logger(
        self,
        name: str,
    ) -> EventLogger:
        return self._logger

    def add_event_logger(self, event_logger: EventLogger):
        self._logger.add_event_logger(event_logger)


global_event_logger_provider = EventLoggerProvider()


def get_event_logger_provider() -> EventLoggerProvider:
    return global_event_logger_provider


class JsonlEventLogger(EventLogger):
    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)

    def emit(
        self,
        event: Event,
    ):
        with open(self.file_path, "a") as file:
            json_str = json.dumps(event.to_json())
            file.write(f"{json_str}\n")


class HTTPEventLogger(EventLogger):
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def emit(self, event: Event):
        events = [event.to_json()]
        with httpx.Client() as client:
            client.post(self.endpoint, json=events)


def add_event_with_logger(
    self: Span,
    name: str,
    attributes: types.Attributes = None,
    timestamp: Optional[int] = None,
):
    if not isinstance(self, Span):
        return
    attributes = BoundedAttributes(
        self._limits.max_event_attributes,
        attributes,
        max_value_len=self._limits.max_attribute_length,
    )
    otel_event = TraceEvent(name=name, attributes=attributes, timestamp=timestamp)
    self._add_event(otel_event)
    index = None if otel_event not in self._events else self._events.index(otel_event)
    trace_id = f"0x{format_trace_id(self.context.trace_id)}"
    span_id = f"0x{format_span_id(self.context.span_id)}"
    event = Event(
        name=name,
        trace_id=trace_id,
        span_id=span_id,
        attributes=attributes,
        timestamp=otel_event.timestamp,
        index=index,
    )
    get_event_logger_provider().get_event_logger("promptflow").emit(event=event)


def instrument_events_api():
    Span.add_event = add_event_with_logger
