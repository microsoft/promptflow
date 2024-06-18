# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import datetime
import json
import logging
import multiprocessing
import threading
import time
import typing
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path

from google.protobuf.json_format import MessageToJson
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PBSpan
from opentelemetry.trace.span import format_span_id as otel_format_span_id
from opentelemetry.trace.span import format_trace_id as otel_format_trace_id

from promptflow._constants import (
    SpanAttributeFieldName,
    SpanContextFieldName,
    SpanEventFieldName,
    SpanFieldName,
    SpanLinkFieldName,
    SpanResourceAttributesFieldName,
    SpanResourceFieldName,
    SpanStatusFieldName,
)
from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR, AzureMLWorkspaceTriad
from promptflow._sdk._telemetry.telemetry import get_telemetry_logger
from promptflow._sdk._user_agent import USER_AGENT
from promptflow._sdk.entities._trace import Span
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.user_agent_utils import setup_user_agent_to_operation_context
from promptflow.core._errors import MissingRequiredPackage

from .general_utils import convert_time_unix_nano_to_timestamp, json_load

_logger = get_cli_sdk_logger()


# SCENARIO: OTLP trace collector
# prompt flow service, runtime parse OTLP trace
def format_span_id(span_id: bytes) -> str:
    """Format span id to hex string.
    Note that we need to add 0x since it is how opentelemetry-sdk does.
    Reference: https://github.com/open-telemetry/opentelemetry-python/blob/
    642f8dd18eea2737b4f8cd2f6f4d08a7e569c4b2/opentelemetry-sdk/src/opentelemetry/sdk/trace/__init__.py#L505
    """
    return f"0x{otel_format_span_id(int.from_bytes(span_id, byteorder='big', signed=False))}"


def format_trace_id(trace_id: bytes) -> str:
    """Format trace_id id to hex string.
    Note that we need to add 0x since it is how opentelemetry-sdk does.
    Reference: https://github.com/open-telemetry/opentelemetry-python/blob/
    642f8dd18eea2737b4f8cd2f6f4d08a7e569c4b2/opentelemetry-sdk/src/opentelemetry/sdk/trace/__init__.py#L505
    """
    return f"0x{otel_format_trace_id(int.from_bytes(trace_id, byteorder='big', signed=False))}"


def parse_kv_from_pb_attribute(attribute: typing.Dict) -> typing.Tuple[str, str]:
    attr_key = attribute["key"]
    # suppose all values are flattened here
    # so simply regard the first value as the attribute value
    attr_value = list(attribute["value"].values())[0]
    return attr_key, attr_value


def _flatten_pb_attributes(attributes: typing.List[typing.Dict]) -> typing.Dict:
    flattened_attributes = {}
    for attribute in attributes:
        attr_key, attr_value = parse_kv_from_pb_attribute(attribute)
        flattened_attributes[attr_key] = attr_value
    return flattened_attributes


def _parse_otel_span_status_code(value: int) -> str:
    # map int value to string
    # https://github.com/open-telemetry/opentelemetry-specification/blob/v1.22.0/specification/trace/api.md#set-status
    # https://github.com/open-telemetry/opentelemetry-python/blob/v1.22.0/opentelemetry-api/src/opentelemetry/trace/status.py#L22-L32
    if value == 0:
        return "Unset"
    elif value == 1:
        return "Ok"
    else:
        return "Error"


def parse_protobuf_events(obj: typing.List[PBSpan.Event], logger: logging.Logger) -> typing.List[typing.Dict]:
    events = []
    if len(obj) == 0:
        logger.debug("No events found in span")
        return events
    for pb_event in obj:
        event_dict: dict = json.loads(MessageToJson(pb_event))
        logger.debug("Received event: %s", json.dumps(event_dict))
        event = {
            SpanEventFieldName.NAME: pb_event.name,
            # .isoformat() here to make this dumpable to JSON
            SpanEventFieldName.TIMESTAMP: convert_time_unix_nano_to_timestamp(pb_event.time_unix_nano).isoformat(),
            SpanEventFieldName.ATTRIBUTES: _flatten_pb_attributes(
                event_dict.get(SpanEventFieldName.ATTRIBUTES, dict())
            ),
        }
        events.append(event)
    return events


def parse_protobuf_links(obj: typing.List[PBSpan.Link], logger: logging.Logger) -> typing.List[typing.Dict]:
    links = []
    if len(obj) == 0:
        logger.debug("No links found in span")
        return links
    for pb_link in obj:
        link_dict: dict = json.loads(MessageToJson(pb_link))
        logger.debug("Received link: %s", json.dumps(link_dict))
        link = {
            SpanLinkFieldName.CONTEXT: {
                SpanContextFieldName.TRACE_ID: format_trace_id(pb_link.trace_id),
                SpanContextFieldName.SPAN_ID: format_span_id(pb_link.span_id),
                SpanContextFieldName.TRACE_STATE: pb_link.trace_state,
            },
            SpanLinkFieldName.ATTRIBUTES: _flatten_pb_attributes(link_dict.get(SpanLinkFieldName.ATTRIBUTES, dict())),
        }
        links.append(link)
    return links


def parse_protobuf_span(span: PBSpan, resource: typing.Dict, logger: logging.Logger) -> Span:
    # Open Telemetry does not provide official way to parse Protocol Buffer Span object
    # so we need to parse it manually relying on `MessageToJson`
    # reference: https://github.com/open-telemetry/opentelemetry-python/issues/3700#issuecomment-2010704554
    span_dict: dict = json.loads(MessageToJson(span))
    logger.debug("Received span: %s, resource: %s", json.dumps(span_dict), json.dumps(resource))
    span_id = format_span_id(span.span_id)
    trace_id = format_trace_id(span.trace_id)
    parent_id = format_span_id(span.parent_span_id) if span.parent_span_id else None
    # we have observed in some scenarios, there is not `attributes` field
    attributes = _flatten_pb_attributes(span_dict.get(SpanFieldName.ATTRIBUTES, dict()))
    logger.debug("Parsed attributes: %s", json.dumps(attributes))
    links = parse_protobuf_links(span.links, logger)
    events = parse_protobuf_events(span.events, logger)

    return Span(
        trace_id=trace_id,
        span_id=span_id,
        name=span.name,
        context={
            SpanContextFieldName.TRACE_ID: trace_id,
            SpanContextFieldName.SPAN_ID: span_id,
            SpanContextFieldName.TRACE_STATE: span.trace_state,
        },
        kind=span.kind,
        parent_id=parent_id if parent_id else None,
        start_time=convert_time_unix_nano_to_timestamp(span.start_time_unix_nano),
        end_time=convert_time_unix_nano_to_timestamp(span.end_time_unix_nano),
        status={
            SpanStatusFieldName.STATUS_CODE: _parse_otel_span_status_code(span.status.code),
            SpanStatusFieldName.DESCRIPTION: span.status.message,
        },
        attributes=attributes,
        links=links,
        events=events,
        resource=resource,
    )


# SCENARIO: local to cloud
# distinguish Azure ML workspace and AI project
@dataclass
class WorkspaceKindLocalCache:
    subscription_id: str
    resource_group_name: str
    workspace_name: str
    kind: typing.Optional[str] = None
    timestamp: typing.Optional[datetime.datetime] = None

    SUBSCRIPTION_ID = "subscription_id"
    RESOURCE_GROUP_NAME = "resource_group_name"
    WORKSPACE_NAME = "workspace_name"
    KIND = "kind"
    TIMESTAMP = "timestamp"
    # class-related constants
    PF_DIR_TRACING = "tracing"
    WORKSPACE_KIND_LOCAL_CACHE_EXPIRE_DAYS = 1

    def __post_init__(self):
        if self.is_cache_exists:
            cache = json_load(self.cache_path)
            self.kind = cache[self.KIND]
            self.timestamp = datetime.datetime.fromisoformat(cache[self.TIMESTAMP])

    @property
    def cache_path(self) -> Path:
        tracing_dir = HOME_PROMPT_FLOW_DIR / self.PF_DIR_TRACING
        if not tracing_dir.exists():
            tracing_dir.mkdir(parents=True)
        filename = f"{self.subscription_id}_{self.resource_group_name}_{self.workspace_name}.json"
        return (tracing_dir / filename).resolve()

    @property
    def is_cache_exists(self) -> bool:
        return self.cache_path.is_file()

    @property
    def is_expired(self) -> bool:
        if not self.is_cache_exists:
            return True
        time_delta = datetime.datetime.now() - self.timestamp
        return time_delta.days > self.WORKSPACE_KIND_LOCAL_CACHE_EXPIRE_DAYS

    def get_kind(self) -> str:
        if not self.is_cache_exists or self.is_expired:
            _logger.debug(f"refreshing local cache for resource {self.workspace_name}...")
            self._refresh()
        _logger.debug(f"local cache kind for resource {self.workspace_name}: {self.kind}")
        return self.kind

    def _refresh(self) -> None:
        self.kind = self._get_workspace_kind_from_azure()
        self.timestamp = datetime.datetime.now()
        cache = {
            self.SUBSCRIPTION_ID: self.subscription_id,
            self.RESOURCE_GROUP_NAME: self.resource_group_name,
            self.WORKSPACE_NAME: self.workspace_name,
            self.KIND: self.kind,
            self.TIMESTAMP: self.timestamp.isoformat(),
        }
        with open(self.cache_path, "w") as f:
            f.write(json.dumps(cache))

    def _get_workspace_kind_from_azure(self) -> str:
        try:
            from azure.ai.ml import MLClient

            from promptflow.azure._cli._utils import get_credentials_for_cli
        except ImportError:
            error_message = "Please install 'promptflow-azure' to use Azure related tracing features."
            raise MissingRequiredPackage(message=error_message)

        _logger.debug("trying to get workspace from Azure...")
        ml_client = MLClient(
            credential=get_credentials_for_cli(),
            subscription_id=self.subscription_id,
            resource_group_name=self.resource_group_name,
            workspace_name=self.workspace_name,
        )
        ws = ml_client.workspaces.get(name=self.workspace_name)
        return ws._kind


def get_workspace_kind(ws_triad: AzureMLWorkspaceTriad) -> str:
    """Get workspace kind.

    Note that we will cache this result locally with timestamp, so that we don't
    really need to request every time, but need to check timestamp.
    """
    return WorkspaceKindLocalCache(
        subscription_id=ws_triad.subscription_id,
        resource_group_name=ws_triad.resource_group_name,
        workspace_name=ws_triad.workspace_name,
    ).get_kind()


# SCENARIO: local trace UI search experience
# append condition(s) to user specified query
def append_conditions(
    expression: str,
    collection: typing.Optional[str] = None,
    runs: typing.Optional[typing.Union[str, typing.List[str]]] = None,
    session_id: typing.Optional[str] = None,
    logger: typing.Optional[logging.Logger] = None,
) -> str:
    if logger is None:
        logger = _logger
    logger.debug("received original search expression: %s", expression)
    if collection is not None:
        logger.debug("received search parameter collection: %s", collection)
        expression += f" and collection == '{collection}'"
    if runs is not None:
        logger.debug("received search parameter runs: %s", runs)
        if isinstance(runs, str):
            expression += f" and run == '{runs}'"
        elif len(runs) == 1:
            expression += f" and run == '{runs[0]}'"
        else:
            runs_expr = " or ".join([f"run == '{run}'" for run in runs])
            expression += f" and ({runs_expr})"
    if session_id is not None:
        logger.debug("received search parameter session_id: %s", session_id)
        expression += f" and session_id == '{session_id}'"
    logger.debug("final search expression: %s", expression)
    return expression


# SCENARIO: trace count telemetry
TraceCountKey = namedtuple(
    "TraceKey", ["subscription_id", "resource_group", "workspace_name", "scenario", "execution_target"]
)


def aggregate_trace_count(all_spans: typing.List[Span]) -> typing.Dict[TraceCountKey, int]:
    """
    Aggregate the trace count based on workspace info, scenario, and execution target.
    """
    trace_count_summary = {}

    if not all_spans:
        return trace_count_summary

    # Iterate over all spans
    for span in all_spans:
        if span.attributes.get(SpanAttributeFieldName.IS_AGGREGATION, False):
            # Ignore aggregation span, because it does not represent a line execution.
            continue
        # Only count for root span, ignore span count telemetry for now.
        if span.parent_id is None:
            resource_attributes = span.resource.get(SpanResourceFieldName.ATTRIBUTES, {})
            subscription_id = resource_attributes.get(SpanResourceAttributesFieldName.SUBSCRIPTION_ID, None)
            resource_group = resource_attributes.get(SpanResourceAttributesFieldName.RESOURCE_GROUP_NAME, None)
            workspace_name = resource_attributes.get(SpanResourceAttributesFieldName.WORKSPACE_NAME, None)
            # We may need another field to indicate the language in the future, e.g. python, csharp.
            execution_target = span.attributes.get(SpanAttributeFieldName.EXECUTION_TARGET, "code")

            scenario = "script"
            if SpanAttributeFieldName.BATCH_RUN_ID in span.attributes:
                scenario = "batch"
            elif SpanAttributeFieldName.LINE_RUN_ID in span.attributes:
                scenario = "test"

            key = TraceCountKey(subscription_id, resource_group, workspace_name, scenario, execution_target)

            trace_count_summary[key] = trace_count_summary.get(key, 0) + 1

    return trace_count_summary


class TraceTelemetryHelper:
    """Helper class for trace telemetry in prompt flow service."""

    LOG_INTERVAL_SECONDS = 60
    TELEMETRY_ACTIVITY_NAME = "pf.telemetry.trace_count"
    CUSTOM_DIMENSIONS_TRACE_COUNT = "trace_count"

    def __init__(self):
        # `setup_user_agent_to_operation_context` will get user agent and return
        self._user_agent = setup_user_agent_to_operation_context(USER_AGENT)
        self._telemetry_logger = get_telemetry_logger()
        self._lock = multiprocessing.Lock()
        self._summary: typing.Dict[TraceCountKey, int] = dict()
        self._thread = threading.Thread(target=self._schedule_flush, daemon=True)
        self._thread.start()

    def _schedule_flush(self) -> None:
        while True:
            time.sleep(self.LOG_INTERVAL_SECONDS)
            self.log_telemetry()

    def append(self, summary: typing.Dict[TraceCountKey, int]) -> None:
        with self._lock:
            for key, count in summary.items():
                self._summary[key] = self._summary.get(key, 0) + count

    def log_telemetry(self) -> None:
        # only lock the process to operate the summary
        with self._lock:
            summary_to_log = copy.deepcopy(self._summary)
            self._summary = dict()
        for key, count in summary_to_log.items():
            custom_dimensions = key._asdict()
            custom_dimensions[self.CUSTOM_DIMENSIONS_TRACE_COUNT] = count
            custom_dimensions["user_agent"] = self._user_agent
            self._telemetry_logger.info(self.TELEMETRY_ACTIVITY_NAME, extra={"custom_dimensions": custom_dimensions})


_telemetry_helper = TraceTelemetryHelper()
